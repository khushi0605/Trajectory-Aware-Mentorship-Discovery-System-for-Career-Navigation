import logging
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.agents.models import CareerPathOptions
from src.app.state import AgentState

logger = logging.getLogger("agents.reasoning")

class CareerReasoningAgent(BaseAgent):
    """
    Agent 2: Reasons over trajectory_paths from RetrievalContext.
    Produces CareerPathOptions.
    """
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        agent_name = "career_reasoning"
        logger.info(f"Running Agent: {agent_name}")
        
        try:
            profile = state.get("user_profile")
            context = state.get("retrieval_context")
            
            if not profile or not context:
                raise ValueError("Missing profile or context for career reasoning")

            # Build prompts
            system, user = self.prompts.for_career_reasoning(context, profile)
            
            # Call LLM
            career_paths = await self.llm.generate_structured(
                system_prompt=system,
                user_prompt=user,
                response_schema=CareerPathOptions,
                temperature=0.3
            )
            
            update = {"career_paths": career_paths}
            update.update(self._log_completion(agent_name, state))
            return update

        except Exception as e:
            update = self._handle_error(agent_name, e, state)
            update["career_paths"] = None
            return update
