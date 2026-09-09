# Trajectory-Aware Career Mentorship Discovery System

A multi-agent career intelligence system that leverages RAG (Retrieval-Augmented Generation) over career trajectories to provide grounded, near-peer mentorship.

## ✨ Key Advancements (Recent Updates)

*   **Multi-Agent Debate (MAD) Module**: Career recommendations are now scrutinized by a 3-persona agent ensemble (**Optimist**, **Realist**, **Critic**) ensuring high-nuance advice and assumption-challenging.
*   **Quota-Aware LLM Layer**: Enhanced Gemini client with exponential backoff and staggered execution to handle API rate limits (essential for free-tier users).
*   **Mentor Reachability Calibration**: Mentor discovery thresholds are now dynamically calibrated (0.45) based on Neo4j graph data distribution for higher matching precision.
*   **Performance Benchmarking**: A comprehensive instrumentation harness to track per-agent latency and output completeness across synthetic profiles.

---

## 🏗 System Architecture

The project is structured into 4 logical phases:

1.  **Ingestion Pipeline**: Collects data from GitHub and Kaggle to build initial candidate profiles.
2.  **Retrieval Layer**: A hybrid RAG system using **Neo4j** for graph trajectories (reachability scoring) and **ChromaDB** for semantic narrative search.
3.  **LLM Reasoning Layer**: Powered by **Gemini 1.5 Flash**, featuring a unified client with structured output validation and retry logic.
4.  **Agentic Orchestration**: Orchestrated via **LangGraph**, featuring:
    *   `ProfileUnderstandingAgent`: Intent extraction and resume parsing (PDF/TXT supported).
    *   `MultiAgentDebateNode`: Peer-review logic (Optimist/Realist/Critic).
    *   `ExperienceAnalysisAgent`: Collaborative struggle detection.
    *   `MentorDiscoveryAgent`: Calibrated trajectory matching.
    *   `OutreachAgent`: Generative connection messaging.

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
├── tests/                  # MAD unit tests and E2E pipeline tests
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

## 📜 Documentation
- [Latest Walkthrough](walkthrough.md): Summary of MAD logic and Quota fixes.
- [Project Breakdown](project_breakdown.md): Deep dive into agent interactions.
