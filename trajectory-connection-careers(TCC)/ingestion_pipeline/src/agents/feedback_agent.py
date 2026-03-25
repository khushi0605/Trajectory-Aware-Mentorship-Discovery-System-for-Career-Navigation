import logging
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.agents.models import FeedbackSignal
from src.app.state import AgentState

logger = logging.getLogger("agents.feedback")

class FeedbackAgent(BaseAgent):
    """
    Agent 7: Analyzes human feedback and routes it to the target agent.
    Produces FeedbackSignal and increments loop count.
    """
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        agent_name = "feedback"
        logger.info(f"Running Agent: {agent_name}")
        
        try:
            raw_feedback = state.get("feedback_input") # We'll expect this in state from runner
            if not raw_feedback:
                # If no feedback provided yet, we might be at the end of the first run
                return {}

            # Summarize previous output (simple string for now)
            summary = "Summary of previous career reasoning, experience analysis, and mentor matches."
            
            # Build prompts
            system, user = self.prompts.for_feedback_integration(summary, raw_feedback)
            
            # Call LLM
            signal = await self.llm.generate_structured(
                system_prompt=system,
                user_prompt=user,
                response_schema=FeedbackSignal,
                temperature=0.2
            )
            
            current_loops = state.get("feedback_loop_count", 0)
            
            update = {
                "feedback": signal,
                "feedback_target_agent": signal.target_agent,
                "feedback_loop_count": current_loops + 1
            }
            update.update(self._log_completion(agent_name, state))
            return update

        except Exception as e:
            update = self._handle_error(agent_name, e, state)
            update["feedback"] = None
            update["feedback_target_agent"] = "end"
            return update
