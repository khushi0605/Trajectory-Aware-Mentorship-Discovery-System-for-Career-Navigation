import logging
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.agents.models import ExperienceInsights
from src.app.state import AgentState

logger = logging.getLogger("agents.analysis")

class ExperienceAnalysisAgent(BaseAgent):
    """
    Agent 4: Synthesizes behavioral_signals and narrative_chunks.
    Produces ExperienceInsights.
    """
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        agent_name = "experience_analysis"
        logger.info(f"Running Agent: {agent_name}")
        
        try:
            profile = state.get("user_profile")
            context = state.get("retrieval_context")
            
            if not profile or not context:
                raise ValueError("Missing profile or context for experience analysis")

            # Build prompts
            system, user = self.prompts.for_experience_analysis(
                context, 
                profile.background, 
                profile.goal
            )
            
            # Call LLM
            insights = await self.llm.generate_structured(
                system_prompt=system,
                user_prompt=user,
                response_schema=ExperienceInsights,
                temperature=0.3
            )
            
            update = {"experience_insights": insights}
            update.update(self._log_completion(agent_name, state))
            return update

        except Exception as e:
            update = self._handle_error(agent_name, e, state)
            update["experience_insights"] = None
            return update
