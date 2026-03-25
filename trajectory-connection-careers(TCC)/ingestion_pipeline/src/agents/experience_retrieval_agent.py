import logging
from typing import Dict, Any
from src.agents.base_agent import BaseAgent
from src.retrieval.rag_retriever import RAGRetriever
from src.app.state import AgentState

logger = logging.getLogger("agents.retrieval")

class ExperienceRetrievalAgent(BaseAgent):
    """
    Agent 3: Pure data fetcher. Calls RAGRetriever directly.
    Zero LLM calls.
    """
    
    def __init__(self, llm_client, prompt_builder, retriever: RAGRetriever):
        super().__init__(llm_client, prompt_builder)
        self.retriever = retriever

    async def run(self, state: AgentState) -> Dict[str, Any]:
        agent_name = "experience_retrieval"
        logger.info(f"Running Agent: {agent_name}")
        
        try:
            profile = state.get("user_profile")
            if not profile:
                raise ValueError("No user_profile found in state for retrieval")

            # Build query dict for retriever
            query_dict = {
                "background": profile.background,
                "skills": profile.skills,
                "interest": profile.interest,
                "goal": profile.goal
            }
            
            # Execute retrieval
            context = await self.retriever.retrieve(query_dict)
            
            update = {"retrieval_context": context}
            update.update(self._log_completion(agent_name, state))
            return update

        except Exception as e:
            update = self._handle_error(agent_name, e, state)
            update["retrieval_context"] = None
            return update
