import logging
import json
import re
from pydantic import BaseModel, Field

logger = logging.getLogger("eval.agent")

# FLATTENED SCHEMA: No nested objects. Local models handle this much better.
class EvaluationResult(BaseModel):
    system_a_empirical_grounding: int = Field(ge=1, le=10, description="System A Empirical Grounding (1-10)")
    system_a_feasibility_risk: int = Field(ge=1, le=10, description="System A Feasibility Risk (1-10)")
    system_a_actionability: int = Field(ge=1, le=10, description="System A Actionability (1-10)")
    system_a_goal_alignment: int = Field(ge=1, le=10, description="System A Goal Alignment (1-10)")
    
    system_b_empirical_grounding: int = Field(ge=1, le=10, description="System B Empirical Grounding (1-10)")
    system_b_feasibility_risk: int = Field(ge=1, le=10, description="System B Feasibility Risk (1-10)")
    system_b_actionability: int = Field(ge=1, le=10, description="System B Actionability (1-10)")
    system_b_goal_alignment: int = Field(ge=1, le=10, description="System B Goal Alignment (1-10)")
    
    rationale: str = Field(description="2-3 sentences explaining exactly WHY these scores were given.")
    winner: str = Field(description="Must be 'System A', 'System B', or 'Tie'")

class EvaluationAgent:
    def __init__(self, llm_client):
        self.llm = llm_client
        self.system_prompt = """You are an impartial academic evaluator for a computer science research paper. 
You are evaluating two career mentorship generation systems (System A and System B).

CRITICAL GRADING INSTRUCTION: You must evaluate the *substance* of the evidence. Penalize systems that rely purely on generic parametric assumptions without hard data. However, you should still evaluate the fluency, logical structure, and overall coherence of the advice impartially.

Evaluate both systems on a 1-10 scale across these 4 metrics:

1. Empirical Grounding (EG): 
   - Score 1-10 based on the system's reliance on verifiable historical peer trajectories, mathematical reachability, or explicit dataset evidence. 
   - DATA REQUIREMENT: If a system does NOT explicitly cite actual graph-grounded frequency numbers (e.g., "1 professional in our dataset..."), it should be penalized, though partial credit can be awarded for strong inductive reasoning.

2. Feasibility Risk (FRA): 
   - Score 1-10 based on the system's ability to identify structural, numerical, or explicitly verifiable skill/experience gaps.
   - DATA REQUIREMENT: Heavily reward systems that synthesize specific missing skills or experience into structural thematic gaps based on historical data. Penalize generic, surface-level warnings (e.g., 'market competition' or 'lack of experience').

3. Actionability (ANP): 
   - Score 1-10 based on the provision of highly tangible, near-peer mentor profiles derived from specific historical skill transitions.
   - DATA REQUIREMENT: If a system does NOT contain a dedicated "Mentor Discovery Strategy" section with actual reachable mentors containing specific Candidate IDs (e.g., 'user_a801a931f882'), exact Reachability scores (e.g., '0.8033'), and the "Path Taken", it should be penalized. However, partial credit can be given for highly actionable, albeit generic, networking advice.

4. Goal Alignment (GSA): 
   - Score 1-10 based on how logically the system bridges the user's documented starting skills with their aspirational goal.
   - DATA REQUIREMENT: If a system does NOT break down the alignment into a structured, Phase-by-Phase action plan (e.g., "Phase 1: Core Upskilling", "Phase 2: Transition") built on the exact data points provided above, it should be penalized. Partial credit is allowed for well-structured, logical career steps.

CRITICAL INSTRUCTIONS FOR OUTPUT FORMAT:
You MUST output a flat JSON object using EXACTLY these keys and nothing else:
{
  "system_a_empirical_grounding": 0,
  "system_a_feasibility_risk": 0,
  "system_a_actionability": 0,
  "system_a_goal_alignment": 0,
  "system_b_empirical_grounding": 0,
  "system_b_feasibility_risk": 0,
  "system_b_actionability": 0,
  "system_b_goal_alignment": 0,
  "rationale": "2-3 sentences explaining why. Explicitly mention the presence or lack of hard data.",
  "winner": "System A or System B or Tie"
}

DO NOT wrap the JSON in markdown formatting.
Start your response immediately with { and end with }."""

    async def evaluate_pair(self, tcc_text: str, gemini_text: str) -> EvaluationResult:
        user_prompt = f"--- SYSTEM A REPORT ---\n{tcc_text}\n\n--- SYSTEM B REPORT ---\n{gemini_text}\n\nEvaluate both systems based on the rubric."
        
        logger.info("Sending manual JSON request to local LLM...")
        
        # 1. Use standard text generation instead of structured
        raw_response = await self.llm.generate(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            temperature=0.1
        )
        
        # 2. Clean the output (Strip markdown backticks Qwen loves to add)
        cleaned_response = raw_response.strip()
        cleaned_response = re.sub(r'^```json\n?', '', cleaned_response, flags=re.MULTILINE)
        cleaned_response = re.sub(r'^```\n?', '', cleaned_response, flags=re.MULTILINE)
        cleaned_response = re.sub(r'```$', '', cleaned_response, flags=re.MULTILINE)
        cleaned_response = cleaned_response.strip()
        
        # 3. Manual Parsing with extreme visibility
        try:
            # Find the first { and last } in case Qwen added preamble text
            start_idx = cleaned_response.find('{')
            end_idx = cleaned_response.rfind('}')
            
            if start_idx != -1 and end_idx != -1:
                json_str = cleaned_response[start_idx:end_idx+1]
                data = json.loads(json_str)
                return EvaluationResult(**data)
            else:
                raise ValueError("No JSON brackets found in output.")
                
        except Exception as e:
            # THIS IS CRITICAL: If it fails, print exactly what the LLM said so the developer can see it!
            print("\n" + "="*50)
            print("❌ JSON PARSING FAILED. RAW LLM OUTPUT:")
            print(raw_response)
            print("="*50 + "\n")
            raise RuntimeError(f"Failed to parse Evaluation JSON. Error: {e}")
