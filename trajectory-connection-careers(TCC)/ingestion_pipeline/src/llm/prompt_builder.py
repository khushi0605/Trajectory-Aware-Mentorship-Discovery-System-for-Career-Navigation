import logging
from typing import Dict, Any, List, Tuple
from src.retrieval.models import RetrievalContext
from src.agents.models import UserProfile, MentorMatch

logger = logging.getLogger("llm.prompt_builder")

# Grounding Constraint Constant
GROUNDING_BASE = """
You are a career reasoning engine for a mentorship discovery system.

RULES (non-negotiable):
1. You reason ONLY over data in the CONTEXT block below.
2. You do not suggest career paths, people, or experiences not present in CONTEXT.
3. If context is insufficient, return the schema with empty arrays and set
   "data_sufficient": false.
4. Return ONLY valid JSON matching the schema specified. No preamble, no
   markdown fences, no explanation outside the JSON.
5. When making claims about people, always cite their candidate_id.

CONTEXT:
{context_block}
"""

class PromptBuilder:
    
    def _format_context(self, context: RetrievalContext) -> str:
        """
        Formats RetrievalContext into the strict labelled human-readable format.
        Implements token budget truncation logic.
        """
        # Truncation logic (order: narratives -> behavioral -> reasoning)
        # 1. Narratives to top 3
        narratives = sorted(context.narrative_chunks, key=lambda x: x.relevance_score, reverse=True)[:3]
        
        # 2. Behavioral to top 5 (simulating domain match by keeping first 5)
        behavioral = context.behavioral_signals[:5]
        
        # 3. Paths (never truncated by count)
        paths = context.trajectory_paths
        
        # Assembly
        lines = []
        
        lines.append("=== CAREER TRAJECTORY PATHS ===")
        for i, p in enumerate(paths, 1):
            # Reasoning truncation logic: if we were over budget (simulated by length check)
            # For now, let's just stick to the requested format
            lines.append(f"[{i}] candidate_id: {p.candidate_id} | reachability: {p.reachability_score}")
            lines.append(f"    decision: \"{p.decision_text}\"")
            lines.append(f"    trigger: \"{p.trigger}\"")
            lines.append(f"    path: {p.target_role}") # Simplified path for now as per model
            
        lines.append("\n=== BEHAVIORAL SIGNALS ===")
        for s in behavioral:
            lines.append(f"[{s.signal_type}] {s.candidate_id} | domain: {s.domain} | resolved: {s.resolved}")
            lines.append(f"  \"{s.text}\"")
            
        lines.append("\n=== NARRATIVE EXPERIENCES ===")
        for i, n in enumerate(narratives, 1):
            lines.append(f"[chunk {i}] role: {n.role} | domain: {n.domain} | relevance: {n.relevance_score}")
            lines.append(f"  \"{n.text}\"")
            
        return "\n".join(lines)

    def for_profile_understanding(self, raw_user_input: str) -> Tuple[str, str]:
        system = """You are a structured data extractor. Parse the user's input into the exact
JSON schema below. Extract what is explicitly stated. Do not infer or expand.

Return ONLY this JSON:
{
  "background": "string — current role or education level",
  "skills": ["list of explicitly mentioned skills"],
  "interest": "string — domain or technology area of interest",
  "goal": "string — target role, outcome, or options being considered (e.g. 'research or industry')",
  "confusion": "string or null — any expressed uncertainty",
  "experience_level": "student|junior|mid|senior"
}"""
        user = f"Parse this career query:\n\"{raw_user_input}\""
        return (system, user)

    def for_career_reasoning(self, context: RetrievalContext, profile: UserProfile) -> Tuple[str, str]:
        context_block = self._format_context(context)
        system = GROUNDING_BASE.format(context_block=context_block) + """
You are a career path analyst. You will receive career trajectory data and a
user profile. Your task is to describe the career paths supported by the data.

RULES:
1. Only describe paths present in TRAJECTORY PATHS section of CONTEXT.
2. For each path, cite the candidate_id(s) that support it.
3. Order paths by average reachability score (highest first).
4. If fewer than 2 paths exist in context, set "data_sufficient": false.

Return ONLY this JSON schema: CareerPathOptions"""
        
        user = f"""User profile:
- Background: {profile.background}
- Skills: {', '.join(profile.skills)}
- Interest: {profile.interest}
- Goal: {profile.goal}

Describe the career paths available based on the context above."""
        return (system, user)

    def for_experience_analysis(self, context: RetrievalContext, background: str, goal: str) -> Tuple[str, str]:
        context_block = self._format_context(context)
        system = GROUNDING_BASE.format(context_block=context_block) + """
You are an experience analyst. Synthesise the behavioral signals and narrative
experiences in CONTEXT into actionable insights for someone with the user's
background trying to reach their goal.

RULES:
1. Every insight must cite at least one candidate_id or chunk from CONTEXT.
2. "frequency" = number of distinct candidates exhibiting this pattern in CONTEXT.
3. "resolution_pattern" must be grounded in the BEHAVIORAL SIGNALS, not invented.
4. "estimated_transition_time" must be derived from the number of hops in paths,
   not fabricated. If you cannot estimate it, return "insufficient data".

Return ONLY this JSON schema: ExperienceInsights"""
        
        user = f"""User background: {background}
User goal: {goal}

Synthesise the insights from the context above."""
        return (system, user)

    def for_mentor_discovery(self, context: RetrievalContext, profile: UserProfile) -> Tuple[str, str]:
        context_block = self._format_context(context)
        system = GROUNDING_BASE.format(context_block=context_block) + """
You are a mentor matching engine. Rank the candidates in CONTEXT as potential
mentors for the user described below.

RANKING CRITERIA (in order of priority):
1. reachability_score >= 0.6 (near-peer constraint)
2. Path alignment: how closely their trajectory matches the user's goal
3. Skill overlap with the user's current skills
4. Presence of resolved struggles in the user's target domain

RULES:
1. Only rank candidates present in CONTEXT TRAJECTORY PATHS.
2. Deprioritise candidates whose path is more than 3 hops ahead of the user.
3. "contact_hook" must reference a SPECIFIC struggle or learning pattern from
   CONTEXT.
4. Return maximum 3 mentors.

Return ONLY this JSON schema: MentorRanking"""
        
        user = f"""User profile:
- Background: {profile.background}
- Skills: {', '.join(profile.skills)}
- Goal: {profile.goal}

Rank the best mentor matches."""
        return (system, user)

    def for_outreach(self, contact_hook: str, mentor_path: str, background: str, goal: str, experience_level: str, candidate_id: str) -> Tuple[str, str]:
        # Outreach is generative, not structured - no GROUNDING_BASE needed per spec
        system = f"You are a professional outreach writer for a career mentorship platform."
        system += f"\n\nWrite a personalised connection request from a {experience_level} in {background} to a potential mentor who has reached {mentor_path}."
        system += """
RULES:
1. The message MUST reference the specific experience in PERSONALISATION HOOK below.
2. Maximum 150 words.
3. Do not use generic openers.
4. The sender should ask ONE specific question.
5. Do not mention the AI system.
6. Tone: respectful, direct, specific. Not sycophantic.
"""
        user = f"""PERSONALISATION HOOK (use this — do not invent):
{contact_hook}

Mentor's path: {mentor_path}

Write the outreach message from:
  Sender: {background}, interested in {goal}
  Recipient: candidate {candidate_id}, path: {mentor_path}"""
        return (system, user)

    def for_feedback_integration(self, previous_output_summary: str, raw_feedback: str) -> Tuple[str, str]:
        system = """You are a feedback routing engine. A user has reviewed the system's output
and provided feedback. Classify what they want changed.

Return ONLY this JSON:
{
  "target_agent": "career_reasoning|experience_analysis|mentor_discovery|outreach|end",
  "refinement_instruction": "string — specific instruction for that agent"
}

"end" means the user is satisfied and the session should close."""
        user = f"""Previous output summary:
{previous_output_summary}

User feedback:
"{raw_feedback}"

Classify what should be changed."""
        return (system, user)
