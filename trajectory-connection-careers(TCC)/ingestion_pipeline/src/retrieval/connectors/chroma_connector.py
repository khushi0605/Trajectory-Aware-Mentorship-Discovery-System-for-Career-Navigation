from __future__ import annotations
import logging
from typing import List
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from ..models import NarrativeChunk
from ..config.retriever_config import ChromaConfig

logger = logging.getLogger("chroma_connector")

class ChromaConnector:
    def __init__(self, config: ChromaConfig):
        # Using HuggingFaceEmbeddings as specified in the config's embedding_model
        # We assume the model name matches a HuggingFace model or a path
        self.embeddings = HuggingFaceEmbeddings(model_name=config.embedding_model)
        
        self.vectorstore = Chroma(
            persist_directory=config.persist_directory,
            collection_name=config.collection_name,
            embedding_function=self.embeddings
        )

    async def search(self, query: str, k: int) -> List[NarrativeChunk]:
        """
        Semantic similarity search over the 'career_experiences' collection.
        Returns a list of NarrativeChunk models.
        """
        chunks = []
        try:
            # chroma.similarity_search_with_relevance_scores is more precise
            results = self.vectorstore.similarity_search_with_relevance_scores(query, k=k)
            
            for doc, score in results:
                chunks.append(NarrativeChunk(
                    text=doc.page_content,
                    source_profile_id=doc.metadata.get("source_profile_id", "unknown"),
                    role=doc.metadata.get("role", "unknown"),
                    domain=doc.metadata.get("domain", "unknown"),
                    relevance_score=float(score)
                ))
        except Exception as e:
            logger.error(f"Chroma search failed: {e}")
            raise
            
        return chunks
