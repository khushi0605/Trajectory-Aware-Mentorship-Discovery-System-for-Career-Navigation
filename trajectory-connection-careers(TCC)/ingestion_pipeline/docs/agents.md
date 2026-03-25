# Agent Architecture
## `src/agents/` + `src/app/` — Phase 3

---

## Overview

Seven specialised agents orchestrated as a LangGraph `StateGraph`. Each agent
is a pure function (node) that reads from shared state, calls the LLM or a
store, and writes structured output back to state. No agent talks to another
agent directly — communication is only through state.

The graph runs as a single pipeline per user query. Agent 7 (Feedback) creates
a conditional edge that can loop back into the graph for human-in-the-loop
refinement.

---

## Separation from Ingestion Layer

This entire phase lives in two new packages only:

```
src/
  agents/          ← individual agent node functions (was empty)
    __init__.py
    profile_understanding_agent.py
    career_reasoning_agent.py
    experience_retrieval_agent.py
    experience_analysis_agent.py
    mentor_discovery_agent.py
    outreach_agent.py
    feedback_agent.py
    base_agent.py          ← shared ABC + utilities
  app/             ← new top-level package
    __init__.py
    graph.py               ← StateGraph definition, edge wiring, entrypoint
    state.py               ← AgentState TypedDict (the shared state schema)
    runner.py              ← async entrypoint: build graph, stream output
```

The existing `src/` packages (`ingestion/`, `processing/`, `enrichment/`,
`storage/`, `pipeline/`) are **read-only** from the agent perspective.
Agents import from `src/retrieval/` only — never directly from storage drivers.

---

## Shared State (`src/app/state.py`)

LangGraph passes one state object through every node. This is the single
source of truth for the whole pipeline run.

```python
from typing import TypedDict, List, Optional
from src.retrieval.models import RetrievalContext
from src.agents.models import (
    UserProfile, CareerPathOptions, ExperienceInsights,
    MentorRanking, OutreachDraft, FeedbackSignal
)

class AgentState(TypedDict):
    # Input
    raw_user_input: str

    # Agent 1 output
    user_profile: Optional[UserProfile]

    # Agent 2 output
    retrieval_context: Optional[RetrievalContext]
    career_paths: Optional[CareerPathOptions]

    # Agent 3 output  (pure retrieval — no LLM)
    retrieval_context: Optional[RetrievalContext]

    # Agent 4 output
    experience_insights: Optional[ExperienceInsights]

    # Agent 5 output
    mentor_ranking: Optional[MentorRanking]

    # Agent 6 output
    outreach_drafts: Optional[List[OutreachDraft]]

    # Agent 7 input/output
    feedback: Optional[FeedbackSignal]
    feedback_target_agent: Optional[str]   # which agent to re-run

    # Pipeline metadata
    errors: List[str]
    completed_agents: List[str]
```

---

## Graph Topology (`src/app/graph.py`)

```
START
  │
  ▼
[1] ProfileUnderstandingAgent      extract structured profile from raw text
  │
  ▼
[3] ExperienceRetrievalAgent        fire RAGRetriever — no LLM, pure data fetch
  │
  ▼
[2] CareerReasoningAgent            reason over trajectory_paths → career options
  │
  ▼
[4] ExperienceAnalysisAgent         synthesise behavioral_signals + narratives
  │
  ▼
[5] MentorDiscoveryAgent            rank candidates by reachability + skill match
  │
  ▼
[6] OutreachAgent                   write personalised message per top mentor
  │
  ▼
[7] FeedbackAgent ─── human input ──► conditional edge:
      │                                  - "approved" → END
      └──────────────────────────────►  - "refine X"  → re-run agent X
```

Note: ExperienceRetrieval (3) runs before CareerReasoning (2) because the
reasoning agent needs the `RetrievalContext` to be grounded. The numbering
reflects the user-facing identity, not execution order.

---

## Agent 1 — `ProfileUnderstandingAgent`

**File:** `src/agents/profile_understanding_agent.py`

**Role:** Parses the user's free-text input into a `UserProfile` struct.
This is the only agent that operates without a `RetrievalContext` — it runs
on raw input only.

**Store queries:** None  
**LLM call:** Yes — extraction prompt  
**Input from state:** `raw_user_input`  
**Output to state:** `user_profile`

```python
class UserProfile(BaseModel):
    background: str           # "CS Student", "Junior Backend Engineer"
    skills: List[str]         # ["Python", "ML basics", "PyTorch"]
    interest: str             # "computer vision", "distributed systems"
    goal: str                 # "CV Engineer", "Staff Engineer"
    confusion: Optional[str]  # "not sure if research or industry"
    experience_level: Literal["student", "junior", "mid", "senior"]
```

**Prompt strategy:** Extraction — the system prompt tells Gemini to parse
the user's text into the above schema and return JSON. Temperature 0.1
(we want deterministic extraction, not creativity).

---

## Agent 2 — `CareerReasoningAgent`

**File:** `src/agents/career_reasoning_agent.py`

**Role:** Given the `RetrievalContext` (trajectory paths from Neo4j),
reasons over what career options exist and presents them ranked by how many
real candidates took each path.

**Store queries:** None (uses pre-fetched `RetrievalContext`)  
**LLM call:** Yes — analytical prompt grounded on `trajectory_paths`  
**Input from state:** `user_profile`, `retrieval_context`  
**Output to state:** `career_paths`

```python
class CareerPath(BaseModel):
    path_description: str          # "CS Student → ML Intern → CV Engineer"
    supporting_candidate_ids: List[str]
    avg_reachability: float
    key_decision: str              # the decision that triggered this transition
    estimated_hops: int

class CareerPathOptions(BaseModel):
    recommended_paths: List[CareerPath]   # top 3, ordered by evidence strength
    reasoning: str                         # LLM explanation grounded in context
    data_gaps: List[str]                   # what the graph didn't have
```

**Grounding enforcement:** The prompt explicitly lists the `trajectory_paths`
from context and instructs the model: "Only describe paths that appear in the
data above. Do not suggest paths not present."

---

## Agent 3 — `ExperienceRetrievalAgent`

**File:** `src/agents/experience_retrieval_agent.py`

**Role:** Pure data fetcher. Calls `RAGRetriever.retrieve()` with the
structured `UserProfile`. No LLM involved. This is the agent that actually
hits Neo4j and ChromaDB.

**Store queries:** Yes — via `RAGRetriever` (all 3 queries)  
**LLM call:** None  
**Input from state:** `user_profile`  
**Output to state:** `retrieval_context`

This agent exists as a separate node (not inlined into other agents) because:
1. It's the most likely to fail or be slow — isolating it means errors are
   caught and logged cleanly.
2. Its output (`RetrievalContext`) is shared by agents 2, 4, and 5 — it
   should run once and be reused, not called redundantly.

---

## Agent 4 — `ExperienceAnalysisAgent`

**File:** `src/agents/experience_analysis_agent.py`

**Role:** Synthesises the `behavioral_signals` (struggles + learning patterns)
and `narrative_chunks` from the `RetrievalContext` into human-readable
insights. This is what gives the system depth beyond just listing paths.

**Store queries:** None (uses `RetrievalContext`)  
**LLM call:** Yes — synthesis prompt  
**Input from state:** `retrieval_context`, `user_profile`  
**Output to state:** `experience_insights`

```python
class ExperienceInsight(BaseModel):
    theme: str                      # "Transitioning from ML basics to production CV"
    frequency: int                  # how many candidates faced this
    resolution_pattern: str         # "Most resolved via project-based learning on GitHub"
    supporting_evidence: List[str]  # direct quotes from narrative_chunks

class ExperienceInsights(BaseModel):
    common_struggles: List[ExperienceInsight]
    common_learning_paths: List[ExperienceInsight]
    key_skills_to_acquire: List[str]
    estimated_transition_time: str  # "6–12 months based on N candidates"
```

**Prompt strategy:** Synthesis — present the behavioral signals and narrative
chunks verbatim in the prompt, ask Gemini to identify patterns. The model
is explicitly told to cite `candidate_id` when making claims.

---

## Agent 5 — `MentorDiscoveryAgent`

**File:** `src/agents/mentor_discovery_agent.py`

**Role:** Ranks candidates from the `trajectory_paths` by their fitness as
mentors. Fitness = reachability score (already computed in Neo4j) × skill
overlap with the user × path alignment with the user's goal.

**Store queries:** None (uses `RetrievalContext.trajectory_paths`)  
**LLM call:** Yes — ranking + justification prompt  
**Input from state:** `retrieval_context`, `user_profile`  
**Output to state:** `mentor_ranking`

```python
class MentorMatch(BaseModel):
    candidate_id: str
    reachability_score: float
    skill_overlap: List[str]        # skills user has that mentor also had
    path_taken: str                 # "CS Student → ML Intern → CV Engineer"
    why_relevant: str               # LLM-generated justification (grounded)
    contact_hook: str               # specific experience to reference in outreach

class MentorRanking(BaseModel):
    top_mentors: List[MentorMatch]  # top 3
    ranking_rationale: str
```

**Near-peer constraint:** The system prompt instructs Gemini to prefer
candidates with `reachability_score >= 0.6` and to explicitly deprioritise
any candidate whose trajectory is more than 3 hops ahead of the user.

This is the paper's core contribution made agent-level: surfacing reachable
near-peers, not globally visible experts.

---

## Agent 6 — `OutreachAgent`

**File:** `src/agents/outreach_agent.py`

**Role:** Writes one personalised outreach message per top mentor. Uses the
mentor's specific experiences (from `behavioral_signals` and `narrative_chunks`)
to make each message concrete and non-generic.

**Store queries:** None  
**LLM call:** Yes — generative prompt, one call per mentor (max 3)  
**Input from state:** `mentor_ranking`, `retrieval_context`, `user_profile`  
**Output to state:** `outreach_drafts`

```python
class OutreachDraft(BaseModel):
    mentor_candidate_id: str
    subject_line: str
    message_body: str               # personalised, references specific experiences
    personalisation_hooks: List[str]  # what specific data was used
```

**Personalisation constraint:** The system prompt requires the message to
reference at least one specific struggle or learning pattern from the
mentor's `behavioral_signals`. Generic messages ("I saw your profile and...") 
are explicitly forbidden in the prompt.

---

## Agent 7 — `FeedbackAgent` (Human-in-the-loop)

**File:** `src/agents/feedback_agent.py`

**Role:** Receives human feedback after the full pipeline has run. Parses
the feedback to determine which agent's output should be revised, then
signals LangGraph's conditional edge to re-run the appropriate node.

**Store queries:** None  
**LLM call:** Yes — classification prompt (what does the feedback target?)  
**Input from state:** `feedback` (human-provided string), all previous outputs  
**Output to state:** `feedback_target_agent`, updated target agent's output

```python
class FeedbackSignal(BaseModel):
    raw_feedback: str
    target_agent: Literal[
        "career_reasoning", "experience_analysis",
        "mentor_discovery", "outreach", "end"
    ]
    refinement_instruction: str    # what specifically to change
```

**Conditional edge logic in `graph.py`:**
```python
def route_feedback(state: AgentState) -> str:
    signal = state.get("feedback")
    if signal is None or signal.target_agent == "end":
        return END
    return signal.target_agent   # re-routes to that agent node
```

The graph supports max 2 feedback loops per session to prevent infinite
cycles on free-tier API limits.

---

## Shared Agent Base (`src/agents/base_agent.py`)

```python
class BaseAgent(ABC):
    def __init__(self, llm_client: GeminiClient, prompt_builder: PromptBuilder):
        self.llm = llm_client
        self.prompts = prompt_builder

    @abstractmethod
    async def run(self, state: AgentState) -> dict:
        """
        Each agent implements this. Returns a dict of state keys to update.
        LangGraph merges the returned dict into AgentState automatically.
        """
        ...

    def _log_completion(self, agent_name: str):
        # appends agent_name to state["completed_agents"]
        ...

    def _handle_error(self, agent_name: str, error: Exception) -> dict:
        # appends to state["errors"], returns safe partial state
        ...
```

---

## Pydantic Models (`src/agents/models.py`)

All input/output types for agents (listed above) live in one file.
This is separate from `src/retrieval/models.py` (which owns `RetrievalContext`).
Import chain is always one direction:

```
src/agents/models.py          (agent I/O types)
src/retrieval/models.py       (RetrievalContext types)
src/llm/models.py             (LLM config types)
src/core/types.py             (base types — existing, do not modify)
```

---

## OOAD Principles Applied

| Principle | How |
|---|---|
| **Single Responsibility** | Each agent does exactly one thing. Agent 3 only fetches. Agent 6 only writes messages. |
| **Open/Closed** | New agent = new file + new node in `graph.py`. Existing agents untouched. |
| **Dependency Inversion** | Agents depend on `BaseAgent`, `GeminiClient`, `PromptBuilder` — not on Gemini SDK or neo4j driver. |
| **Interface Segregation** | `BaseAgent.run()` is the only method agents implement. No agent is forced to implement methods it doesn't need. |
| **Separation from ingestion** | Zero imports from `src/ingestion/`, `src/processing/`, `src/enrichment/`, or `src/pipeline/`. |

---

## File Checklist for Gemini to Implement

```
src/app/
  __init__.py
  state.py           ← AgentState TypedDict
  graph.py           ← StateGraph wiring + conditional feedback edge
  runner.py          ← async run(user_input: str) entrypoint

src/agents/
  __init__.py
  models.py          ← UserProfile, CareerPathOptions, ExperienceInsights,
                        MentorRanking, OutreachDraft, FeedbackSignal
  base_agent.py      ← BaseAgent ABC
  profile_understanding_agent.py
  career_reasoning_agent.py
  experience_retrieval_agent.py
  experience_analysis_agent.py
  mentor_discovery_agent.py
  outreach_agent.py
  feedback_agent.py

src/llm/
  __init__.py
  client.py          ← GeminiClient
  prompt_builder.py  ← PromptBuilder (all 6 agent methods)
  response_parser.py ← ResponseParser
  models.py          ← LLMConfig

configs/
  llm.yaml           ← new file
```
