from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Any
from src.retrieval.models import RetrievalContext

class BaseRetriever(ABC):
    """
    Abstract base class for all retrievers.
    Defines the contract for the context retrieval operation.
    """
    
    @abstractmethod
    async def retrieve(self, query_dict: Dict[str, Any]) -> RetrievalContext:
        """
        Main retrieval method to be implemented by subclasses.
        Args:
            query_dict: Contains 'background', 'skills', 'interest', and 'goal'.
        Returns:
            A populated RetrievalContext object.
        """
        pass
