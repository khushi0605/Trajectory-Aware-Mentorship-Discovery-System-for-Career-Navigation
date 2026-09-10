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
        # 1. Narratives to top 5 (reduced for TPM)
        narratives = sorted(context.narrative_chunks, key=lambda x: x.relevance_score, reverse=True)[:5]
        
        # 2. Behavioral to top 10 (reduced for TPM)
        behavioral = context.behavioral_signals[:10]
        
        # 3. Paths (limit to top 15)
        paths = context.trajectory_paths[:15]
        
        # Assembly
        lines = []
        
        lines.append("=== CAREER TRAJECTORY PATHS ===")
        for i, p in enumerate(paths, 1):
            # Use exact Pydantic alias names as labels
            lines.append(f"[{i}] candidate_id: {p.candidate_id} | reachability: {p.reachability_score}")
            lines.append(f"  decision: \"{p.decision_text}\"")
            lines.append(f"  description: {p.target_role}") 
            
        lines.append("\n=== BEHAVIORAL SIGNALS ===")
        for s in behavioral:
            lines.append(f"[{s.signal_type}] {s.candidate_id}: \"{s.text}\"")
            
        lines.append("\n=== NARRATIVE EXPERIENCES ===")
        for i, n in enumerate(narratives, 1):
            lines.append(f"[chunk {i}] {n.role} in {n.domain}: \"{n.text}\"")
            
        return "\n".join(lines)

    def for_profile_understanding(self, raw_user_input: str, parsed_resume: str = "") -> Tuple[str, str]:
        system = """You are a highly precise structured data extractor for a career mentorship platform. 
Your job is to parse the user's input and resume into the exact JSON schema below.

CRITICAL RULES:
1. BACKGROUND vs GOAL: "background" is what the user is doing RIGHT NOW. "goal" is what they WANT to become. Never make them the same unless explicitly stated. If they do not state a current job, infer their background from their education or internships (e.g., "Computer Science Student").
2. GOAL NORMALIZATION: "goal" MUST map to ONE of these exact slugs: ml_engineer, data_scientist, data_engineer, software_engineer, research_scientist, frontend_developer, backend_developer, devops_engineer, cloud_engineer, computer_vision_engineer, nlp_engineer, ai_engineer, fullstack_developer, ios_mobile_app_engineer, android_developer, product_manager, security_engineer.
3. EXPERIENCE LEVEL DEFINITIONS:
   - "student": Currently in university or only has internship experience.
   - "junior": 0-2 years of full-time experience.
   - "mid": 3-5 years of full-time experience.
   - "senior": 5+ years of full-time experience.
4. SKILLS EXTRACTION: You must comprehensively extract all technical skills, programming languages, and frameworks mentioned in BOTH the user query and the resume context.

Return ONLY this JSON:
{
  "background": "string — current role, major, or education level",
  "skills": ["exhaustive list of explicitly mentioned skills"],
  "interest": "string — primary domain area (e.g. 'machine learning', 'computer vision')",
  "goal": "string — ONE normalized role slug from the allowed list",
  "confusion": "string or null — any expressed uncertainty",
  "experience_level": "student|junior|mid|senior"
}"""
        
        user = f"USER QUERY:\n\"{raw_user_input}\"\n\n"
        if parsed_resume:
            user += f"RESUME CONTEXT:\n\"{parsed_resume}\"\n"
            
        user += "\nParse this profile carefully according to the rules."
        return (system, user)

    def for_career_reasoning(self, context: RetrievalContext, profile: UserProfile) -> Tuple[str, str]:
        context_block = self._format_context(context)
        system = GROUNDING_BASE.format(context_block=context_block) + """
You are a strict JSON data mapper. Your ONLY job is to extract the TRAJECTORY PATHS from the CONTEXT and format them into the requested schema.

CRITICAL RULES:
1. NO FILTERING: You must extract the paths exactly as they appear in the CONTEXT. Do not ignore them just because they differ from the user's goal.
2. NO HALLUCINATION: Only use the candidate_ids, decisions, and descriptions explicitly listed in the CONTEXT.

FIELD MAPPING GUIDE:
- "recommended_paths": Array of paths extracted from CONTEXT.
  - "description": Combine the user's background with the context description (e.g., "[User Background] -> [description from context]").
  - "supporting_candidates": Array containing the exact "candidate_id" string from the CONTEXT.
  - "reachability": The numeric reachability score from the CONTEXT.
  - "decision": The exact decision text from the CONTEXT.
  - "hops": Set to 1.
- "reasoning": Write 1 sentence explaining that these are empirical paths retrieved based on skill overlap.
- "data_gaps": Write 1 sentence noting if the exact goal role was missing from the retrieved data.
- "data_sufficient": Set to true (boolean) if paths were retrieved.

Return ONLY valid JSON matching the schema. Do not include markdown formatting or explanations outside the JSON."""
        
        user = f"""User profile:
- Background: {profile.background}
- Goal: {profile.goal}

Extract the paths into the JSON schema."""

        return (system, user)

    def for_experience_analysis(self, context: RetrievalContext, background: str, goal: str) -> Tuple[str, str]:
        context_block = self._format_context(context)
        system = GROUNDING_BASE.format(context_block=context_block) + """
You are a strict data synthesizer. Your EXACT task is to group the BEHAVIORAL SIGNALS from the CONTEXT into the structured JSON format.

CRITICAL RULES:
1. ONLY use data from the "=== BEHAVIORAL SIGNALS ===" section. Do not use candidate IDs from the trajectory paths for struggles or learning patterns.
2. Group the items labeled `[struggle]` to populate the `common_struggles` array. 
3. Group the items labeled `[learning_pattern]` to populate the `common_learning_paths` array.

FIELD EXTRACTION GUIDE FOR INSIGHTS ARRAYS:
- "theme": Summarize the core issue (e.g., "Difficulty with Linux").
- "frequency": Count the number of candidate_ids exhibiting this theme.
- "resolution_pattern": State whether the context indicates this was resolved (true/false).
- "supporting_evidence": List the exact candidate_id strings associated with this theme.

GENERAL FIELDS:
- "key_skills_to_acquire": Extract specific technical skills mentioned in the learning patterns or debate context.
- "estimated_transition_time": If you cannot determine time, output "Continuous upskilling required."

Return ONLY valid JSON matching the ExperienceInsights schema."""
        
        user = f"""User background: {background}\nUser goal: {goal}\n\nSynthesize the empirical insights. You MUST populate the common_struggles and common_learning_paths arrays."""
        return (system, user)

    def for_mentor_discovery(self, context: RetrievalContext, profile: UserProfile) -> Tuple[str, str]:
        context_block = self._format_context(context)
        system = GROUNDING_BASE.format(context_block=context_block) + """
You are a strict mentor matching engine. Your job is to extract the best candidates from the CONTEXT and format them into the `top_mentors` JSON array.

CRITICAL RULES:
1. You MUST populate the `top_mentors` array with up to 3 candidates from the TRAJECTORY PATHS section. Do NOT leave it empty.
2. Only select candidates with a reachability_score >= 0.45.

FIELD EXTRACTION GUIDE FOR `top_mentors` ARRAY:
- "candidate_id": The exact ID of the mentor from the context (e.g., "user_a801a931f882").
- "reachability_score": The numeric score from the context.
- "skill_overlap": Array of skills they share with the user (infer based on the trigger/decision text).
- "path_taken": The target_role they achieved.
- "why_relevant": 1 sentence explaining why this candidate is a good mentor for the user.
- "contact_hook": Look in the BEHAVIORAL SIGNALS for this specific candidate_id. If they have a struggle or learning pattern, quote it here to use in the outreach email. If none, write "Your transition to this role."

- "ranking_rationale": Write 2-3 sentences explaining your overall selection strategy. Do NOT list the mentors here; put them in the array.

Return ONLY valid JSON matching the MentorRanking schema."""
        
        user = f"""User profile:
- Background: {profile.background}
- Skills: {', '.join(profile.skills)}
- Goal: {profile.goal}

Rank the best mentor matches and populate the top_mentors array."""
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
