from __future__ import annotations
from pydantic import BaseModel
from typing import List, Literal

class TrajectoryPath(BaseModel):
    candidate_id: str
    reachability_score: float
    decision_text: str
    trigger: str
    target_role: str

class BehavioralSignal(BaseModel):
    candidate_id: str
    text: str
    resolved: bool
    domain: str
    signal_type: Literal["struggle", "learning_pattern"]

class NarrativeChunk(BaseModel):
    text: str
    source_profile_id: str
    role: str
    domain: str
    relevance_score: float

class RetrievalMetadata(BaseModel):
    neo4j_path_count: int
    neo4j_behavioral_count: int
    chroma_count: int
    neo4j_fallback_used: bool
    failed_sources: List[str]
    latency_ms: float

class RetrievalContext(BaseModel):
    trajectory_paths: List[TrajectoryPath]
    behavioral_signals: List[BehavioralSignal]
    narrative_chunks: List[NarrativeChunk]
    metadata: RetrievalMetadata
