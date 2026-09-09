import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from src.app.state import AgentState
    from src.llm import LLMClient
    from src.llm.prompt_builder import PromptBuilder

logger = logging.getLogger("agents.base")

class BaseAgent(ABC):
    def __init__(self, llm_client: "LLMClient", prompt_builder: "PromptBuilder"):
        self.llm = llm_client
        self.prompts = prompt_builder

    @abstractmethod
    async def run(self, state: "AgentState") -> Dict[str, Any]:
        """
        Abstract method to be implemented by each agent.
        Returns a dictionary containing the delta to merge into the shared state.
        """
        pass

    def _log_completion(self, agent_name: str, state: "AgentState") -> Dict[str, Any]:
        """
        Helper to track agent completion in state.
        """
        completed = list(state.get("completed_agents", []))
        if agent_name not in completed:
            completed.append(agent_name)
        return {"completed_agents": completed}

    def _handle_error(self, agent_name: str, error: Exception, state: "AgentState") -> Dict[str, Any]:
        """
        Standard error handler for agent nodes.
        Logs the error and updates the state error list.
        """
        logger.error(f"Agent {agent_name} failed: {error}")
        errors = list(state.get("errors", []))
        errors.append(f"{agent_name}: {str(error)}")
        
        # Return partial state to ensure the key is initialized as None if it failed
        # Actual child agents should override this to set their specific key to None
        return {"errors": errors}

