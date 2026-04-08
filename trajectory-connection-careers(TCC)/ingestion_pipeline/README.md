# Trajectory-Aware Career Mentorship Discovery System

A multi-agent career intelligence system that leverages RAG (Retrieval-Augmented Generation) over career trajectories to provide grounded, near-peer mentorship.

## 🏗 System Architecture

The project is structured into 4 logical phases:

1.  **Ingestion Pipeline**: Collects data from GitHub (repositories, commits) and Kaggle (datasets) to build initial candidate profiles.
2.  **Retrieval Layer**: A hybrid RAG system using **Neo4j** for graph trajectories (career paths, behavioral signals) and **ChromaDB** for semantic narrative search (Medium articles, project descriptions).
3.  **LLM Reasoning Layer**: Powered by **Gemini 2.0/1.5 Flash**, enforcing grounding constraints to ensure all advice is backed by retrieved "peer" evidence.
4.  **Agentic Orchestration**: A 7-agent ensemble orchestrated via **LangGraph**, featuring:
    *   `ProfileUnderstandingAgent`: Intent extraction.
    *   `ExperienceRetrievalAgent`: Parallel data fetching (Neo4j + Chroma).
    *   `CareerReasoningAgent`: Trajectory analysis.
    *   `ExperienceAnalysisAgent`: Behavioral synthesis.
    *   `MentorDiscoveryAgent`: Ranking and matching.
    *   `OutreachAgent`: Generative connection messaging.
    *   `FeedbackAgent`: Human-in-the-loop refinement.

---

## 📂 File Structure

```text
ingestion_pipeline/
├── configs/                # YAML configurations for LLM, Retrieval, and Ingestion
├── data/
│   ├── chroma_db/          # Persistent Vector Database
│   └── processed/          # Intermediate data artifacts
├── docs/                   # Architectural specifications and design docs
├── src/
│   ├── agents/             # LangGraph agent node implementations
│   ├── app/                # Graph assembly, state management, and runner
│   ├── core/               # Shared types, exceptions, and utilities
│   ├── enrichment/         # Signal inference and reachability scoring
│   ├── ingestion/          # Source-specific collectors (GitHub, Kaggle)
│   ├── llm/                # Gemini client, prompt builder, and schema parser
│   ├── matching/           # Profile-to-Role matching logic
│   ├── pipeline/           # Orchestration for batch ingestion
│   ├── retrieval/          # RAG connectors (Neo4j, ChromaDB)
│   ├── storage/            # Database ingestors (Neo4j, Chroma)
│   └── main.py             # Main entrypoint (CLI)
├── tests/                  # E2E and unit tests
├── requirements.txt        # Project dependencies
└── .env                    # Environment variables (API Keys, DB Credentials)
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9+
- Neo4j Instance (Running)
- Google Gemini API Key

### 2. Installation
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Usage

The system operates in two modes:

#### **Interactive Career Mentorship (Phase 4)**
Talk to the agentic system and get personalized career guidance.
```bash
python src/main.py --mode career
```

#### **Batch Data Ingestion (Phase 1-2)**
Collect data from configured sources to populate the knowledge graph.
```bash
python src/main.py --mode ingest
```

---

## 🧪 Verification
Run the end-to-end pipeline test to verify agent orchestration and grounding:
```bash
PYTHONPATH=. python tests/test_pipeline_e2e.py
```

## 📜 Documentation
For detailed specs, see the `docs/` folder:
- [Agent Specs](docs/agents.md)
- [Retrieval Arch](docs/rag.md)
- [LLM Design](docs/systemprompts.md)
