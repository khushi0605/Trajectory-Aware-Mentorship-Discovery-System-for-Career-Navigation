# Mentorship Discovery System Architecture

## 1. Project Vision & Goal
The **Mentorship Discovery System** is a high-fidelity discovery engine designed to replace generic career advice with **real-world evidence**. The system enables users to navigate career paths by analyzing the actual journeys of professionals who have already reached those goals.

Unlike traditional career assistants, this system focuses on:
* **Real Trajectories:** Structured sequences of roles and skill gains.
* **Authentic Experiences:** Narrative "how-to" insights extracted from engineering blogs and articles.
* **Reachable Mentors:** Identifying "near-peers" (1–5 years ahead) rather than unreachable public figures.

**Guiding Principle:** Use AI to *discover* real mentorship rather than *generate* hypothetical advice.

---

## 2. The Core Problem
* **Generic Advice:** Existing LLMs produce generalized guidance not grounded in real data.
* **Hallucinated Experiences:** Generated stories are often hypothetical.
* **Unrealistic Suggestions:** Most systems suggest mentors who are too high-profile to be accessible.
* **Data Fragmentation:** Professional data is scattered across GitHub, LinkedIn, Kaggle, and personal blogs.

---

## 3. Technical Strategy
The system follows a **Raw-to-Insight** progression using a hybrid knowledge architecture:
* **Semantic Store (ChromaDB):** For unstructured narrative experiences (RAG).
* **Trajectory Store (Neo4j):** For structured career pathfinding (Graph).
* **Dynamic Ingestion:** Using **Playwright**, **Firecrawl**, and **Crawl4AI** to scrape and fetch live, dynamic data.

---

## 4. Master File Structure

```text
mentorship_system/
├── configs/
│   ├── ingestion_sources.yaml      # Source registry & scraper settings (GH, LI, Kaggle, etc.)
│   ├── db_config.yaml              # Neo4j & ChromaDB credentials
│   └── agent_config.yaml           # LLM parameters for the multi-agent system
│
├── data/
│   ├── raw/                        # Immutable raw JSON files (Raw-First Ingestion)
│   │   ├── profiles/               # Trajectory data (GH, LinkedIn, Kaggle)
│   │   ├── experiences/            # Narrative data (Blogs, Journey articles)
│   │   └── skill_transitions/      # Role-shift data (Job postings, Resumes)
│   ├── normalized/                 # Unified Pydantic-validated JSONs
│   └── vector_index/               # Local persistence for ChromaDB
│
├── src/
│   ├── core/                       # Shared system foundations
│   │   ├── interfaces.py           # ABCs: ICollector, IScraper, IGraph, IAgent
│   │   ├── types.py                # Pydantic models & Enums for strong typing
│   │   └── exceptions.py           # Custom error hierarchy
│   │
│   ├── ingestion/                  # Data Acquisition Layer (Targeted Discovery)
│   │   ├── scrapers/               # Dynamic Web Engines (Playwright, Crawl4AI)
│   │   ├── collectors/             # Strategy Pattern: Source-specific logic
│   │   ├── factories/              # Factory Pattern: Collector instantiation
│   │   └── routing/                # DataRouter: Maps source to Knowledge Group
│   │
│   ├── storage/                    # Database Abstraction Layer
│   │   ├── raw_repo.py             # Local FileSystem IO manager
│   │   ├── vector_store.py         # ChromaDB client & semantic indexing
│   │   └── graph_store.py          # Neo4j driver & Cypher query builder
│   │
│   ├── processing/                 # Data Transformation Layer
│   │   ├── normalizers/            # Logic to unify Raw -> Unified schemas
│   │   └── extractors/             # NLP/LLM logic to distill skills & roles
│   │
│   ├── agents/                     # Agentic Orchestration Layer
│   │   ├── intent_agent.py         # Query deconstruction (What does the user want?)
│   │   ├── trajectory_agent.py     # Neo4j pathfinding logic (The "Map")
│   │   ├── experience_agent.py     # ChromaDB RAG & narrative retrieval (The "Story")
│   │   └── outreach_agent.py       # Personalized connection drafting (The "Bridge")
│   │
│   └── pipeline/                   # Execution Orchestrators
│       ├── ingestion_orchestrator.py # Manages Raw Ingestion
│       └── system_orchestrator.py   # Main User Query -> Reachable Connections loop
│
├── docs/                           # Documentation (Ingestion, RAG, Graph schemas)
├── tests/                          # Pytest suite
├── .cursorrules                    # Project-specific AI instructions
└── pyproject.toml                  # Dependency management

```markdown
## 6. Programming Principles
* **OOAD & Abstraction:** Every external component (Database, Scraper, Collector) is hidden behind an Interface.
* **Strong Typing:** Pydantic models act as the strict contract between all layers.
* **Separation of Concerns:**
    * **Collectors:** Fetch data.
    * **Routers:** Categorize data.
    * **Normalizers:** Clean data.
    * **Agents:** Reason over data.
* **Information-Type Storage:** Data is stored by its utility (Trajectory vs. Experience), not just its source.
```
