import asyncio
import json
import logging
import re
from typing import Optional, Any

from src.core.exceptions import LLMRateLimitError

# Direct module import to avoid circular dependency via src.agents.__init__
from src.agents.models import (
    OptimistStance, RealistStance, CriticStance, DebateVerdict, DebateOutput
)

logger = logging.getLogger("agents.debate")

# ─── Persona prompts ──────────────────────────────────────────────────────────

OPTIMIST_SYSTEM = """You are an ambitious career strategist. Analyze the user's profile and the retrieved empirical paths. 
Your job is to champion the highest-ceiling, most ambitious trajectory from the data.

RULES:
1. ONLY recommend a path from the provided context.
2. Formulate 'key_bets' that aggressively bridge the gap between the user's current skills and the target role. 
3. Focus on momentum—how can their existing skills act as a springboard? Be specific about the transition strategy."""

REALIST_SYSTEM = """You are a pragmatic career advisor. Analyze the user's profile and the retrieved empirical paths.
Your job is to champion the safest, most stable trajectory from the data, prioritizing high reachability and minimal hops.

RULES:
1. ONLY recommend a path from the provided context.
2. Formulate 'key_bets' that are highly incremental and safe. Focus on closing immediate skill gaps before attempting a role transition.
3. Emphasize utilizing their current background and explicitly listed skills to minimize transition risk."""

CRITIC_SYSTEM = """You are a rigorous, adversarial career feasibility critic. Your exact job is to prevent "feasibility hallucination."
Compare the user's current profile (skills, experience_level) against the proposed empirical paths. 

RULES (NO MACROECONOMIC HALLUCINATIONS):
1. Do not invent generic risks (e.g., 'market volatility').
2. FIND CREDENTIAL GAPS: If the user is a 'student' or 'intern' but the path leads to a senior architect role, you MUST severely flag the experience gap and unrealistic hops.
3. FIND SKILL GAPS: Compare the user's current skills to the realities of the target role. What specific technical prerequisites are they missing?
4. Call out low reachability scores as empirical proof of high transition friction."""

SYNTHESIZER_SYSTEM = """You are the final career architect. You must synthesize the Optimist's ambition, the Realist's pragmatism, and the Critic's harsh feasibility gap analysis.

RULES:
1. The 'consensus_path' MUST be one of the paths originally provided in the context.
2. The 'reasoning' MUST explicitly address how to mitigate the Critic's red flags using the strategic stepping-stones proposed by the Optimist/Realist. Do not ignore the Critic.
3. Assign a 'confidence' score (0.0 to 1.0). If the Critic found massive credential gaps (e.g., an Intern jumping directly to Architect), the confidence MUST be low (< 0.5) to reflect transition risk."""


def _trim_career_context(career_context: dict) -> dict:
    """
    Only pass fields relevant to debate sub-agents.
    Keeps total prompt well under 1500 tokens.
    """
    return {
        "recommended_paths": career_context.get("recommended_paths", []),
        "reasoning": career_context.get("reasoning", ""),
        "data_gaps": career_context.get("data_gaps", []),
    }


def _fallback_output() -> DebateOutput:
    return DebateOutput(
        optimist_stance=OptimistStance(
            recommended_path="Insufficient data",
            rationale="Career context was missing or parsing failed.",
            key_bets=[]
        ),
        realist_stance=RealistStance(
            recommended_path="Insufficient data",
            rationale="Career context was missing or parsing failed.",
            key_bets=[]
        ),
        critic_stance=CriticStance(
            risks=["Career context unavailable — cannot assess risks."],
            red_flags=[]
        ),
        final_verdict=DebateVerdict(
            consensus_path="Insufficient data for debate",
            confidence=0.0,
            reasoning="Debate could not complete due to missing career context.",
            debate_rounds=0
        )
    )


class MultiAgentDebateAgent:
    """
    Runs 3 specialized sub-agents concurrently that debate career recommendations:
    - Optimist: fastest growth path
    - Realist:  safest/grounded path
    - Critic:   identifies risks and blockers
    Then a Synthesizer produces the final verdict.
    """

    def __init__(self, llm_client):
        self.llm = llm_client

    async def _call_with_retry(
        self, system_prompt: str, user_prompt: str, response_schema: Any, max_retries: int = 3
    ) -> Any:
        """LLM call with exponential backoff for rate limits, enforcing structured output."""
        for attempt in range(max_retries):
            try:
                return await self.llm.generate_structured(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    response_schema=response_schema,
                    temperature=0.3
                )
            except LLMRateLimitError:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 30
                    logger.warning(
                        f"[Debate] Rate limit hit. Waiting {wait_time}s before retry "
                        f"{attempt + 1}/{max_retries}..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise
            except Exception as e:
                # Catch structured parsing errors and retry
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2)
        raise RuntimeError("Exhausted all retries in _call_with_retry")

    async def _run_optimist(self, debate_payload: dict) -> OptimistStance:
        user_prompt = f"Career context:\n{json.dumps(debate_payload, indent=2)}\n\nProvide your optimist recommendation."
        try:
            return await self._call_with_retry(OPTIMIST_SYSTEM, user_prompt, OptimistStance)
        except Exception as e:
            logger.warning(f"[Debate] Optimist failed: {e}. Using fallback.")
            return OptimistStance(
                recommended_path="Could not process optimist response",
                rationale=str(e),
                key_bets=[]
            )

    async def _run_realist(self, debate_payload: dict) -> RealistStance:
        user_prompt = f"Career context:\n{json.dumps(debate_payload, indent=2)}\n\nProvide your realist recommendation."
        try:
            return await self._call_with_retry(REALIST_SYSTEM, user_prompt, RealistStance)
        except Exception as e:
            logger.warning(f"[Debate] Realist failed: {e}. Using fallback.")
            return RealistStance(
                recommended_path="Could not process realist response",
                rationale=str(e),
                key_bets=[]
            )

    async def _run_critic(self, debate_payload: dict) -> CriticStance:
        user_prompt = f"Career context:\n{json.dumps(debate_payload, indent=2)}\n\nIdentify the key risks and red flags."
        try:
            return await self._call_with_retry(CRITIC_SYSTEM, user_prompt, CriticStance)
        except Exception as e:
            logger.warning(f"[Debate] Critic failed: {e}. Using fallback.")
            return CriticStance(
                risks=[f"Could not process critic response: {e}"],
                red_flags=[]
            )

    async def _synthesize(
        self,
        optimist: OptimistStance,
        realist: RealistStance,
        critic: CriticStance,
        debate_payload: dict,
    ) -> DebateVerdict:
        synthesis_input = {
            "career_context_summary": debate_payload.get("retrieved_empirical_paths", {}).get("reasoning", ""),
            "optimist": optimist.model_dump(),
            "realist": realist.model_dump(),
            "critic": critic.model_dump(),
        }
        user_prompt = (
            f"Debate results:\n{json.dumps(synthesis_input, indent=2)}\n\n"
            "Synthesize the three stances into a final consensus verdict."
        )
        try:
            return await self._call_with_retry(SYNTHESIZER_SYSTEM, user_prompt, DebateVerdict)
        except Exception as e:
            logger.warning(f"[Debate] Synthesizer failed: {e}. Using fallback.")
            return DebateVerdict(
                consensus_path=realist.recommended_path or optimist.recommended_path,
                confidence=0.4,
                reasoning=f"Fallback: synthesis failed ({e}). Defaulted to realist path.",
                debate_rounds=2
            )

    async def run(self, state: dict) -> dict:
        """
        LangGraph node entry point.
        Reads career_paths from state, runs the three debate agents concurrently,
        synthesizes, and returns debate_result for downstream agents.
        """
        logger.info("Running Agent: multi_agent_debate")

        career_paths_obj = state.get("career_paths")
        if career_paths_obj is None:
            logger.warning(
                "[Debate] No career_paths found in state. Skipping debate and passing through."
            )
            return {}

        # Convert Pydantic model to dict if needed
        if hasattr(career_paths_obj, "model_dump"):
            career_context = career_paths_obj.model_dump()
        elif isinstance(career_paths_obj, dict):
            career_context = career_paths_obj
        else:
            logger.warning("[Debate] career_paths is neither dict nor Pydantic model. Skipping.")
            return {}

        # CRITICAL FIX: Inject user profile into the debate context so the Critic can find gaps
        user_profile_obj = state.get("user_profile", {})
        user_profile_data = user_profile_obj.model_dump() if hasattr(user_profile_obj, "model_dump") else dict(user_profile_obj)

        trimmed_context = _trim_career_context(career_context)
        
        # Combine them into a single debate payload
        debate_payload = {
            "user_current_profile": user_profile_data,
            "retrieved_empirical_paths": trimmed_context
        }

        try:
            # 1. Start sub-agents concurrently (with slight staggered delay to help free tier quota)
            # We still use gather for parallel execution, but wait slightly before each call inside some agents
            # or just stagger them here. Staggering here is safer for RPM limits.
            
            logger.info("[Debate] Starting staggered sub-agent calls to respect API limits...")
            
            # Sub-agent 1: Optimist
            optimist_task = self._run_optimist(debate_payload)
            await asyncio.sleep(2) # Wait 2s for quota
            
            # Sub-agent 2: Realist
            realist_task = self._run_realist(debate_payload)
            await asyncio.sleep(2) # Wait 2s for quota
            
            # Sub-agent 3: Critic
            critic_task = self._run_critic(debate_payload)
            
            # Gather stances
            optimist, realist, critic = await asyncio.gather(
                optimist_task, realist_task, critic_task
            )
            
            await asyncio.sleep(2) # Wait 2s before synthesis
            
            # 2. Synthesize verdict
            verdict = await self._synthesize(optimist, realist, critic, debate_payload)

            output = DebateOutput(
                optimist_stance=optimist,
                realist_stance=realist,
                critic_stance=critic,
                final_verdict=verdict,
            )

            logger.info(
                f"[Debate] Completed. Consensus: '{verdict.consensus_path}' "
                f"(confidence={verdict.confidence:.0%})"
            )
            
            # --- IMPLICIT STATE OVERWRITE ---
            # Parse the consensus back into the global CareerPathOptions
            # so downstream agents (ExperienceAnalysis, MentorDiscovery) use it!
            from src.agents.models import CareerPathOptions
            
            orig_paths = career_context.get("recommended_paths", [])
            new_paths = []
            
            if orig_paths:
                # Merge the consensus into the top path's structure to retain metadata (reachability, candidates)
                top_path_data = orig_paths[0].copy() if isinstance(orig_paths[0], dict) else dict(orig_paths[0])
                top_path_data["path_description"] = verdict.consensus_path
                new_paths.append(top_path_data)
            else:
                new_paths.append({
                    "path_description": verdict.consensus_path,
                    "avg_reachability": 0.0,
                    "key_decision": "Debate Consensus",
                    "estimated_hops": 0
                })

            updated_reasoning = f"DEBATE CONSENSUS (Confidence: {verdict.confidence:.0%}): {verdict.reasoning}\n\nCritic Risks: {', '.join(critic.risks)}"
            
            updated_career_paths = {
                "recommended_paths": new_paths,
                "reasoning": updated_reasoning,
                "data_gaps": career_context.get("data_gaps", []) + critic.risks,
                "data_sufficient": career_context.get("data_sufficient", True)
            }
            
            updated_career_paths_obj = CareerPathOptions(**updated_career_paths)
            
            return {
                "debate_result": output.model_dump(),
                "career_paths": updated_career_paths_obj
            }

        except Exception as e:
            logger.error(f"[Debate] Debate agent failed: {e}. Returning fallback output.")
            return {"debate_result": _fallback_output().model_dump()}


def format_debate_summary(debate_result: dict) -> str:
    """Human-readable summary of the debate for final output."""
    v = debate_result.get("final_verdict", {})
    o = debate_result.get("optimist_stance", {})
    r = debate_result.get("realist_stance", {})
    c = debate_result.get("critic_stance", {})
    return f"""
## Career Path Debate

**Optimist path:** {o.get('recommended_path')}
{chr(10).join(f'  • {b}' for b in o.get('key_bets', []))}

**Realist path:** {r.get('recommended_path')}
{chr(10).join(f'  • {b}' for b in r.get('key_bets', []))}

**Critic flags:**
{chr(10).join(f'  ⚠ {risk}' for risk in c.get('risks', []))}

**Consensus recommendation** (confidence: {v.get('confidence', 0):.0%}):
{v.get('consensus_path')}

_{v.get('reasoning')}_
"""
