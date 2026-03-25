# RAG Architecture
## `src/retrieval/` — Phase 2

---

## Purpose

The retrieval layer is the read-only data access boundary between the populated
stores (Neo4j + ChromaDB) and the agent graph. Nothing outside this package
touches a database driver directly.

It exposes a single public method — `RAGRetriever.retrieve()` — that fires
three concurrent async queries, merges their results, and returns a typed
`RetrievalContext` object that every downstream agent consumes.

---

## What Is Already Populated (do not re-ingest)

### Neo4j (via `rebuild_graph.py` + `GraphExperienceLayer`)

| Node label | Key properties |
|---|---|
| `Candidate` | `user_id`, `reachability_score` |
| `Skill` | `name` |
| `Job` | `role` |
| `Decision` | `id`, `text`, `trigger`, `confidence`, `synthetic` |
| `Struggle` | `id`, `text`, `domain`, `resolved`, `synthetic` |
| `LearningPattern` | `id`, `text`, `skill_source`, `themes`, `synthetic` |
| `Domain` | `name` |
| `ChromaRef` | `chunk_id`, `collection` |

| Relationship | Properties |
|---|---|
| `(Candidate)-[:HAS_SKILL]->(Skill)` | `weight` |
| `(Candidate)-[:CURRENT_ROLE]->(Job)` | — |
| `(Candidate)-[:MADE_DECISION]->(Decision)` | `confidence`, `inferred_from` |
| `(Candidate)-[:FACED]->(Struggle)` | `resolved` |
| `(Candidate)-[:LEARNED_VIA]->(LearningPattern)` | — |
| `(Decision)-[:TRIGGERED_TRANSITION {from_role, to_role}]->(Job)` | `from_role`, `to_role` |
| `(Struggle)-[:IN_DOMAIN]->(Domain)` | — |
| `(LearningPattern)-[:SEEDED_BY]->(ChromaRef)` | — |

### ChromaDB

- **Collection:** `career_experiences` (confirm name in `configs/retrieval.yaml`)
- **Documents:** Medium article chunks, each with metadata:
  `source_profile_id`, `role`, `domain`
- **Persist directory:** `data/chroma_db`

---

## File Structure (new — do not modify existing `src/`)

```
src/
  retrieval/
    __init__.py                  ← exports RAGRetriever
    base_retriever.py            ← ABC, defines retrieve() contract
    rag_retriever.py             ← main class, composes connectors
    models.py                    ← Pydantic output types (RetrievalContext etc.)
    connectors/
      __init__.py
      neo4j_connector.py         ← wraps neo4j driver, all Cypher lives here
      chroma_connector.py        ← wraps langchain_community Chroma
    config/
      __init__.py
      retriever_config.py        ← frozen dataclass, loaded from retrieval.yaml
```

Config file stays at existing location: `configs/retrieval.yaml`

---

## Class Hierarchy

```
BaseRetriever (ABC)               ← src/retrieval/base_retriever.py
└── RAGRetriever                  ← src/retrieval/rag_retriever.py
      ├── Neo4jConnector          ← src/retrieval/connectors/neo4j_connector.py
      └── ChromaConnector         ← src/retrieval/connectors/chroma_connector.py
```

`RAGRetriever` depends on the connector interfaces, not the drivers directly.
This satisfies the Dependency Inversion principle already established in
`src/core/interfaces.py`.

---

## Retrieval Strategies (3 concurrent async calls)

### Query 1 — Neo4j Trajectory Paths

Finds all candidates who made decisions that triggered transitions matching the
user's start → goal pair. Uses the actual graph relationships from `GraphExperienceLayer`.

```cypher
-- Primary: decision-driven transition path
MATCH (c:Candidate)-[:MADE_DECISION]->(d:Decision)
      -[:TRIGGERED_TRANSITION]->(j:Job)
WHERE d.trigger CONTAINS $interest
   OR j.role CONTAINS $goal
RETURN c.user_id        AS candidate_id,
       c.reachability_score AS reachability,
       d.text           AS decision_text,
       d.trigger        AS trigger,
       j.role           AS target_role
ORDER BY c.reachability_score DESC
LIMIT $limit

-- Fallback (if primary returns 0 rows): role-only match
MATCH (c:Candidate)-[:CURRENT_ROLE]->(j:Job)
WHERE j.role CONTAINS $goal
RETURN c.user_id AS candidate_id,
       c.reachability_score AS reachability,
       j.role AS target_role
ORDER BY c.reachability_score DESC
LIMIT $limit
```

### Query 2 — Neo4j EACR Behavioral Context

Pulls struggle + learning pattern signals for candidates heading toward the
user's target domain. This is what makes LLM responses grounded in real
behavioral data, not generic advice.

```cypher
MATCH (c:Candidate)-[:FACED]->(s:Struggle)-[:IN_DOMAIN]->(dom:Domain)
WHERE dom.name CONTAINS $domain
RETURN c.user_id    AS candidate_id,
       s.text       AS struggle_text,
       s.resolved   AS resolved,
       dom.name     AS domain
LIMIT $limit

UNION

MATCH (c:Candidate)-[:LEARNED_VIA]->(lp:LearningPattern)
WHERE lp.themes CONTAINS $domain
   OR lp.skill_source CONTAINS $interest
RETURN c.user_id    AS candidate_id,
       lp.text      AS struggle_text,
       true         AS resolved,
       lp.skill_source AS domain
LIMIT $limit
```

### Query 3 — ChromaDB Semantic Search

Semantic similarity search over Medium article chunks using the user's
background + skills + interest as the query string.

- **k = 5** (configurable via `retrieval_params.top_k_chroma`)
- Returns: `text`, `metadata.source_profile_id`, `metadata.role`,
  `metadata.domain`, `relevance_score`

---

## Output Schema (`RetrievalContext`)

This is the **strict contract** between retrieval and agents. Defined as a
Pydantic model in `src/retrieval/models.py`. Agents must not access the
raw store results — only this object.

```python
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
```

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Neo4j primary query returns 0 rows | Runs fallback role-only query; sets `neo4j_fallback_used: true` |
| Neo4j connection failure | Logs error, returns empty lists, adds `"neo4j"` to `failed_sources` |
| ChromaDB returns 0 results | Returns empty `narrative_chunks: []`; agents use graph data only |
| ChromaDB connection failure | Logs error, adds `"chroma"` to `failed_sources` |
| Config missing / env var not set | Raises `ConfigurationError` (from `src/core/exceptions.py`) at init |
| Any single query exceeds timeout | `asyncio.wait_for` per query; partial results included |

---

## Configuration (`configs/retrieval.yaml`) — update existing file

```yaml
neo4j:
  uri: "${NEO4J_URI:-bolt://localhost:7687}"
  user: "${NEO4J_USER:-neo4j}"
  password: "${NEO4J_PASSWORD:-password}"

chroma:
  persist_directory: "data/chroma_db"
  collection_name: "career_experiences"
  embedding_model: "all-MiniLM-L6-v2"   # must match what was used at ingest time

retrieval_params:
  top_k_chroma: 5
  neo4j_result_limit: 10
  timeout_seconds: 10
  eacr_behavioral_limit: 10
```

---

## OOAD Principles Applied

| Principle | How |
|---|---|
| **Single Responsibility** | `RAGRetriever` only retrieves and merges. No ranking, no reasoning. |
| **Open/Closed** | New store (e.g. Pinecone) → new connector subclass, no changes to `RAGRetriever`. |
| **Dependency Inversion** | `RAGRetriever` takes connector instances at init — not drivers. |
| **Interface Segregation** | Connectors expose only what retriever needs. Driver API is fully hidden. |
| **Liskov Substitution** | Any `BaseRetriever` subclass can replace `RAGRetriever` in agent code. |

---

## What This Module Does NOT Do

- Does not rank or score mentors → `MentorDiscoveryAgent`
- Does not reason over context → LLM layer
- Does not write to any store → strictly read-only
- Does not build prompts → `PromptBuilder` (Phase 4)
- Does not know about agents → agents import retriever, not the other way around
