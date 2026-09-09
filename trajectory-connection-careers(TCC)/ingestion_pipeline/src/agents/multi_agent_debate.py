import asyncio
import json
import logging
import re
from typing import Optional

from src.core.exceptions import LLMRateLimitError

# Direct module import to avoid circular dependency via src.agents.__init__
from src.agents.models import (
    OptimistStance, RealistStance, CriticStance, DebateVerdict, DebateOutput
)

logger = logging.getLogger("agents.debate")

# ─── Persona prompts ──────────────────────────────────────────────────────────

OPTIMIST_SYSTEM = """You are an ambitious career strategist. You identify the fastest realistic \
path to the user's target role. Focus on opportunities, momentum, and bold but achievable moves. \
Be specific about timelines.

Return ONLY valid JSON matching this schema:
{
  "recommended_path": "string — the fastest viable career trajectory",
  "rationale": "string — why this is achievable",
  "key_bets": ["list of bold but actionable moves with timelines"]
}"""

REALIST_SYSTEM = """You are a pragmatic career advisor. You recommend the safest, most grounded \
path with least risk to current compensation and stability. Prioritize internal moves and \
incremental skill-building.

Return ONLY valid JSON matching this schema:
{
  "recommended_path": "string — the safest career trajectory",
  "rationale": "string — why this path minimizes risk",
  "key_bets": ["list of incremental steps and internal opportunities"]
}"""

CRITIC_SYSTEM = """You are a skeptical career analyst. Your job is to identify every real risk, \
blocker, and assumption the other advisors are glossing over. Be specific about market conditions, \
credential gaps, and competition.

Return ONLY valid JSON matching this schema:
{
  "risks": ["list of real market risks and blockers"],
  "red_flags": ["list of credential gaps and competitive threats"]
}"""

SYNTHESIZER_SYSTEM = """You are a neutral career mediator. You have received three career \
recommendations from an Optimist, a Realist, and a Critic. Synthesize them into a single \
consensus recommendation.

Your task:
1. Identify where Optimist and Realist agree (boosts confidence).
2. Make sure the Critic's top risks are factored into the final recommendation.
3. Assign a confidence score (0.0 to 1.0) based on how much the agents agreed 
   (1.0 = all three aligned, 0.0 = complete disagreement).

Return ONLY valid JSON matching this schema:
{
  "consensus_path": "string — the balanced recommended path accounting for key risks",
  "confidence": 0.75,
  "reasoning": "string — how you resolved disagreements and weighed the stances",
  "debate_rounds": 2
}"""


def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` fences before parsing."""
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"```\s*$", "", cleaned)
    return cleaned.strip()


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
        self, system_prompt: str, user_prompt: str, max_retries: int = 3
    ) -> str:
        """LLM call with exponential backoff for rate limits (matches existing client pattern)."""
        for attempt in range(max_retries):
            try:
                return await self.llm.generate(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=2048,
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
        raise RuntimeError("Exhausted all retries in _call_with_retry")

    async def _run_optimist(self, trimmed_context: dict) -> OptimistStance:
        user_prompt = f"Career context:\n{json.dumps(trimmed_context, indent=2)}\n\nProvide your optimist recommendation."
        try:
            raw = await self._call_with_retry(OPTIMIST_SYSTEM, user_prompt)
            data = json.loads(_strip_json_fences(raw))
            return OptimistStance(**data)
        except Exception as e:
            logger.warning(f"[Debate] Optimist parsing failed: {e}. Using fallback.")
            return OptimistStance(
                recommended_path="Could not parse optimist response",
                rationale=str(e),
                key_bets=[]
            )

    async def _run_realist(self, trimmed_context: dict) -> RealistStance:
        user_prompt = f"Career context:\n{json.dumps(trimmed_context, indent=2)}\n\nProvide your realist recommendation."
        try:
            raw = await self._call_with_retry(REALIST_SYSTEM, user_prompt)
            data = json.loads(_strip_json_fences(raw))
            return RealistStance(**data)
        except Exception as e:
            logger.warning(f"[Debate] Realist parsing failed: {e}. Using fallback.")
            return RealistStance(
                recommended_path="Could not parse realist response",
                rationale=str(e),
                key_bets=[]
            )

    async def _run_critic(self, trimmed_context: dict) -> CriticStance:
        user_prompt = f"Career context:\n{json.dumps(trimmed_context, indent=2)}\n\nIdentify the key risks and red flags."
        try:
            raw = await self._call_with_retry(CRITIC_SYSTEM, user_prompt)
            data = json.loads(_strip_json_fences(raw))
            return CriticStance(**data)
        except Exception as e:
            logger.warning(f"[Debate] Critic parsing failed: {e}. Using fallback.")
            return CriticStance(
                risks=[f"Could not parse critic response: {e}"],
                red_flags=[]
            )

    async def _synthesize(
        self,
        optimist: OptimistStance,
        realist: RealistStance,
        critic: CriticStance,
        trimmed_context: dict,
    ) -> DebateVerdict:
        synthesis_input = {
            "career_context_summary": trimmed_context.get("reasoning", ""),
            "optimist": optimist.model_dump(),
            "realist": realist.model_dump(),
            "critic": critic.model_dump(),
        }
        user_prompt = (
            f"Debate results:\n{json.dumps(synthesis_input, indent=2)}\n\n"
            "Synthesize the three stances into a final consensus verdict."
        )
        try:
            raw = await self._call_with_retry(SYNTHESIZER_SYSTEM, user_prompt)
            data = json.loads(_strip_json_fences(raw))
            return DebateVerdict(**data)
        except Exception as e:
            logger.warning(f"[Debate] Synthesizer parsing failed: {e}. Using fallback.")
            # Simple heuristic: pick realist path when synthesis fails
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

        trimmed_context = _trim_career_context(career_context)

        try:
            # 1. Start sub-agents concurrently (with slight staggered delay to help free tier quota)
            # We still use gather for parallel execution, but wait slightly before each call inside some agents
            # or just stagger them here. Staggering here is safer for RPM limits.
            
            logger.info("[Debate] Starting staggered sub-agent calls to respect API limits...")
            
            # Sub-agent 1: Optimist
            optimist_task = self._run_optimist(trimmed_context)
            await asyncio.sleep(2) # Wait 2s for quota
            
            # Sub-agent 2: Realist
            realist_task = self._run_realist(trimmed_context)
            await asyncio.sleep(2) # Wait 2s for quota
            
            # Sub-agent 3: Critic
            critic_task = self._run_critic(trimmed_context)
            
            # Gather stances
            optimist, realist, critic = await asyncio.gather(
                optimist_task, realist_task, critic_task
            )
            
            await asyncio.sleep(2) # Wait 2s before synthesis
            
            # 2. Synthesize verdict
            verdict = await self._synthesize(optimist, realist, critic, trimmed_context)

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
