import logging
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.agents.models import MentorRanking
from src.app.state import AgentState

logger = logging.getLogger("agents.mentor")

class MentorDiscoveryAgent(BaseAgent):
    """
    Agent 5: Ranks candidates by fitness as mentors.
    Produces MentorRanking.
    """
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        agent_name = "mentor_discovery"
        logger.info(f"Running Agent: {agent_name}")
        
        try:
            profile = state.get("user_profile")
            context = state.get("retrieval_context")
            
            if not profile or not context:
                raise ValueError("Missing profile or context for mentor discovery")

            # Build prompts
            system, user = self.prompts.for_mentor_discovery(context, profile)
            
            # Call LLM
            ranking = await self.llm.generate_structured(
                system_prompt=system,
                user_prompt=user,
                response_schema=MentorRanking,
                temperature=0.2 # Prefer ranking determinism
            )
            
            update = {"mentor_ranking": ranking}
            update.update(self._log_completion(agent_name, state))
            return update

        except Exception as e:
            update = self._handle_error(agent_name, e, state)
            update["mentor_ranking"] = None
            return update
