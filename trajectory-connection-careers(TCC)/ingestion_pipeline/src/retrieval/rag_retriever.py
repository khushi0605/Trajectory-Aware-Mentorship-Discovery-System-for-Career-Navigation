from __future__ import annotations
import asyncio
import logging
import time
from typing import Dict, Any, List
from .base_retriever import BaseRetriever
from .models import RetrievalContext, RetrievalMetadata, TrajectoryPath, BehavioralSignal, NarrativeChunk
from .connectors.neo4j_connector import Neo4jConnector
from .connectors.chroma_connector import ChromaConnector
from .config.retriever_config import RetrieverConfig

logger = logging.getLogger("rag_retriever")

class RAGRetriever(BaseRetriever):
    def __init__(self, config: RetrieverConfig):
        self.config = config
        self.neo4j = Neo4jConnector(config.neo4j)
        self.chroma = ChromaConnector(config.chroma)

    async def retrieve(self, query_dict: Dict[str, Any]) -> RetrievalContext:
        """
        Main retrieval logic: Concurrent fetch from Neo4j and ChromaDB.
        """
        start_time = time.perf_counter()
        
        background = query_dict.get("background", "")
        skills = query_dict.get("skills", [])
        interest = query_dict.get("interest", "")
        goal = query_dict.get("goal", "")
        
        # Derived values for queries
        skills_str = " ".join(skills)
        chroma_query = f"{background} {skills_str} {interest}".strip()
        # Domain inference: fallback to goal if interest is empty
        domain = interest if interest else goal
        
        limit = self.config.params.neo4j_result_limit
        behavioral_limit = self.config.params.eacr_behavioral_limit
        k = self.config.params.top_k_chroma
        timeout = self.config.params.timeout_seconds
        
        failed_sources = []
        fallback_used = False
        
        # Async tasks
        tasks = [
            self._safe_call(self.neo4j.get_trajectory_paths(interest, goal, limit), "neo4j_paths"),
            self._safe_call(self.neo4j.get_behavioral_signals(domain, interest, behavioral_limit), "neo4j_signals"),
            self._safe_call(self.chroma.search(chroma_query, k), "chroma_search")
        ]
        
        try:
            # Execute with timeout
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
        except asyncio.TimeoutError:
            logger.error("RAG retrieval timed out.")
            results = [([], False), [], []] # Empty results on timeout
            failed_sources.append("overall_timeout")
        
        # Unpack results
        path_res = results[0] if results[0] is not None else ([], False)
        paths, fallback_used = path_res if isinstance(path_res, tuple) else ([], False)
        
        signals = results[1] if results[1] is not None else []
        chunks = results[2] if results[2] is not None else []
        
        if results[0] is None: failed_sources.append("neo4j_paths")
        if results[1] is None: failed_sources.append("neo4j_signals")
        if results[2] is None: failed_sources.append("chroma")
        
        latency = (time.perf_counter() - start_time) * 1000
        
        metadata = RetrievalMetadata(
            neo4j_path_count=len(paths),
            neo4j_behavioral_count=len(signals),
            chroma_count=len(chunks),
            neo4j_fallback_used=fallback_used,
            failed_sources=failed_sources,
            latency_ms=round(latency, 2)
        )
        
        return RetrievalContext(
            trajectory_paths=paths,
            behavioral_signals=signals,
            narrative_chunks=chunks,
            metadata=metadata
        )

    async def _safe_call(self, coro, source_name: str):
        """Helper to catch errors per source and return None instead of crashing gather."""
        try:
            return await coro
        except Exception as e:
            logger.error(f"Source '{source_name}' failed: {e}")
            return None

    def close(self):
        self.neo4j.close()
