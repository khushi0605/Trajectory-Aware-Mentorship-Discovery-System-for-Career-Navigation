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
        # 1. Narratives to top 10
        narratives = sorted(context.narrative_chunks, key=lambda x: x.relevance_score, reverse=True)[:10]
        
        # 2. Behavioral to top 20
        behavioral = context.behavioral_signals[:20]
        
        # 3. Paths (never truncated by count)
        paths = context.trajectory_paths
        
        # Assembly
        lines = []
        
        lines.append("=== CAREER TRAJECTORY PATHS ===")
        for i, p in enumerate(paths, 1):
            # Reasoning truncation logic: if we were over budget (simulated by length check)
            # For now, let's just stick to the requested format
            lines.append(f"[{i}] candidate_id: {p.candidate_id} | avg_reachability: {p.reachability_score}")
            lines.append(f"    key_decision: \"{p.decision_text}\"")
            lines.append(f"    trigger: \"{p.trigger}\"")
            lines.append(f"    path_description: {p.target_role}") # Simplified path for now as per model
            
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
        system = """You are a structured data extractor. Parse the user's input into the exact JSON schema below.

CRITICAL RULE FOR "goal" FIELD: You MUST map the user's intent to ONE normalized role slug from this list:
ml_engineer, data_scientist, data_engineer, software_engineer, research_scientist,
frontend_developer, backend_developer, devops_engineer, cloud_engineer,
computer_vision_engineer, nlp_engineer, ai_engineer, fullstack_developer,
ios_mobile_app_engineer, android_developer, product_manager, security_engineer

If the user says "not sure" or "help me connect", infer the closest role from their interest.
If they mention multiple options (e.g. "healthcare tech or big data"), pick the most specific one.
NEVER put a full sentence in "goal". Only a role slug like "ml_engineer".

RESUME HANDLING: If a RESUME CONTEXT section is present in the input, extract skills,
background, and experience level from it. Prioritise explicit facts from the resume
over inferred facts from the query alone. The USER QUERY contains the stated goal.

Return ONLY this JSON:
{
  "background": "string — current role or education level",
  "skills": ["list of explicitly mentioned skills"],
  "interest": "string — primary domain or technology area (e.g. 'machine learning', 'computer vision')",
  "goal": "string — ONE normalized role slug from the list above",
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
2. For each path, cite the candidate_id(s) that support it in supporting_candidate_ids.
3. Order paths by avg_reachability score (highest first).
4. If fewer than 2 paths exist in context, set "data_sufficient": false.

FIELD EXTRACTION GUIDE (non-negotiable):
- "avg_reachability": Use the value after "avg_reachability:" in the CONTEXT for each candidate. Average it across supporting candidates.
- "key_decision": Use the text after "key_decision:" in the CONTEXT. Never set this to "unknown" if the key_decision field is present in CONTEXT.
- "path_description": Summarise the role transition shown in path_description field of CONTEXT.
- "estimated_hops": Count the number of "->" separators in the path_description, then add 1. If the path has 2 roles, hops = 1. If you cannot determine this, use 1 as the default.
- "supporting_candidate_ids": List the candidate_id values of ALL candidates whose avg_reachability you averaged.

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
1. reachability_score >= 0.45 (near-peer constraint — calibrated to graph data distribution)
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
