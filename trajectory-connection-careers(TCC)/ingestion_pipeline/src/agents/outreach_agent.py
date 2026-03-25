import logging
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.agents.models import OutreachDraft
from src.app.state import AgentState

logger = logging.getLogger("agents.outreach")

class OutreachAgent(BaseAgent):
    """
    Agent 6: Generates personalized outreach drafts for top mentors.
    Produces List[OutreachDraft].
    """
    
    async def run(self, state: AgentState) -> Dict[str, Any]:
        agent_name = "outreach"
        logger.info(f"Running Agent: {agent_name}")
        
        try:
            profile = state.get("user_profile")
            ranking = state.get("mentor_ranking")
            
            if not profile or not ranking or not ranking.top_mentors:
                logger.warning("No mentors found to generate outreach drafts for.")
                return self._log_completion(agent_name, state)

            drafts = []
            
            # Generate one draft per mentor (max 3 as per ranking)
            for mentor in ranking.top_mentors:
                system, user = self.prompts.for_outreach(
                    contact_hook=mentor.contact_hook,
                    mentor_path=mentor.path_taken,
                    background=profile.background,
                    goal=profile.goal,
                    experience_level=profile.experience_level,
                    candidate_id=mentor.candidate_id
                )
                
                # Outreach is plain text generative
                body = await self.llm.generate(
                    system_prompt=system,
                    user_prompt=user,
                    temperature=0.7 # Allow variation
                )
                
                drafts.append(OutreachDraft(
                    mentor_candidate_id=mentor.candidate_id,
                    subject_line=f"Inquiry about your transition to {profile.goal}",
                    message_body=body,
                    personalisation_hooks=[mentor.contact_hook]
                ))
            
            update = {"outreach_drafts": drafts}
            update.update(self._log_completion(agent_name, state))
            return update

        except Exception as e:
            update = self._handle_error(agent_name, e, state)
            update["outreach_drafts"] = []
            return update
