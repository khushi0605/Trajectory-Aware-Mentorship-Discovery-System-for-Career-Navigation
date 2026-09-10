import logging
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.agents.models import UserProfile
from src.app.state import AgentState

logger = logging.getLogger("agents.profile")

class ProfileUnderstandingAgent(BaseAgent):
    """
    Agent 1: Extracts structured UserProfile from raw user input.
    Operates without RAG context.
    """
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        agent_name = "profile_understanding"
        logger.info(f"Running Agent: {agent_name}")
        
        try:
            raw_input = state.get("raw_user_input")
            if not raw_input:
                raise ValueError("No raw_user_input found in state")
                
            parsed_resume = state.get("parsed_resume_text", "")

            # Build prompts
            system, user = self.prompts.for_profile_understanding(raw_input, parsed_resume)
            
            # Call LLM for structured output
            profile = await self.llm.generate_structured(
                system_prompt=system,
                user_prompt=user,
                response_schema=UserProfile,
                temperature=0.1 # Determinism over creativity
            )
            
            update = {"user_profile": profile}
            update.update(self._log_completion(agent_name, state))
            return update

        except Exception as e:
            update = self._handle_error(agent_name, e, state)
            update["user_profile"] = None
            return update
