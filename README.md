# GG-MAD: Graph-Grounded Multi-Agent Debate for Trajectory-Aware Mentorship Discovery

![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)
![Neo4j](https://img.shields.io/badge/Neo4j-Graph%20Database-blue)
![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-orange)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red)
![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)

## Abstract / Overview

When seeking career advice, standard Large Language Models (LLMs) often suffer from **"feasibility hallucination"**—they confidently recommend career transitions that are mathematically improbable or structurally disconnected from a candidate's actual starting skills.

**GG-MAD (Graph-Grounded Multi-Agent Debate)** solves this by constraining the generative power of LLMs within the rigorous structural bounds of a Knowledge Graph. By unifying disparate datasets—structural career trajectories from Neo4j and experiential narratives from ChromaDB—GG-MAD enables a truly data-backed approach to career navigation.

The core innovation is an **adversarial multi-agent debate** orchestrated via LangGraph. An **Optimist** agent proposes ambitious, fast-growth transitions, a **Realist** agent grounds paths in conservative, precedent-backed steps, and a **Critic** agent mathematically calculates credential gaps and transition *reachability scores*. This adversarial synthesis completely prevents hallucinated advice, ensuring that all recommended mentor profiles and upskilling pathways are historically verified and statistically reachable.

---

## System Architecture

The GG-MAD framework operates across three distinct architectural strata:

1. **Knowledge Source Layer:** A multi-source data ingestion pipeline that unifies GitHub profiles (via REST API v3), Kaggle Profiles, Resumes (parsed via PyMuPDF/OCR), synthetic Job Descriptions, and Medium articles into unified professional identities.
2. **Hybrid Retrieval Layer:** A dual-engine system fetching structural path constraints concurrently from Neo4j (via Cypher fallbacks) alongside top-5 semantic narrative chunks from ChromaDB.
3. **Multi-Agent Reasoning Layer:** A LangGraph-orchestrated workflow featuring Profile Understanding, Career Reasoning, Multi-Agent Debate (Optimist vs. Realist vs. Critic), Experience Analysis, Mentor Discovery, and Outreach Generation.

### Visual Architecture
*Architecture and Data Flow Diagrams outlining the GG-MAD methodology.*

![Dataset Pipeline](./Dataset%20Pipeline%20Diagram.svg)
*Figure 1: Multi-stage dataset construction and identity fusion.*

![System Architecture](./System%20Architecture%20Diagram.svg)
*Figure 2: The Hybrid Retrieval Layer merging Neo4j graphs with ChromaDB vectors.*

![Debate Workflow](./Debate%20Workflow%20Diagram.svg)
*Figure 3: The Multi-Agent Reasoning Layer featuring the adversarial debate mechanism.*

---

## Repository Structure

```text
trajectory-connection-careers(TCC)/
├── README.md                      # This file
├── System Architecture Diagram.svg
├── Dataset Pipeline Diagram.svg
├── Debate Workflow Diagram.svg
└── ingestion_pipeline/
    ├── app_batch_eval.py          # Dashboard: Runs GG-MAD against batch profiles
    ├── app_refiner_batch.py       # Dashboard: Translates raw JSON to phased prose
    ├── app_eval_dashboard.py      # Dashboard: Automated LLM-as-a-Judge Evaluation
    ├── requirements.txt           # Python dependencies
    ├── test_data/                 # Resumes (PDF) and batch evaluation inputs
    ├── scripts/                   # Data extraction, ingestion, and DB stats
    ├── outputs/                   # Contains TCC (GG-MAD) vs. Gemini baseline results
    └── src/
        ├── agents/                # LangGraph node implementations (Optimist, Critic, etc.)
        ├── core/                  # Core schemas and configuration states
        ├── llm/                   # LLM API clients
        ├── retrieval/             # Neo4j and ChromaDB connectors
        └── tools/                 # Agent utilities
```

---

## Installation & Setup

### Prerequisites
Before installing the Python dependencies, you must install the system-level libraries required for the OCR fallback (which parses PDF resumes).

**On macOS (Homebrew):**
```bash
brew install tesseract poppler
```

**On Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr poppler-utils
```

### Installation
1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/trajectory-connection-careers.git
   cd trajectory-connection-careers/ingestion_pipeline
   ```

2. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Environment Variables:**
   Create a `.env` file in the `ingestion_pipeline` directory with the following keys:
   ```env
   # Neo4j Graph Database
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=your_password
   
   # LLM Providers (Adjust based on your local/cloud config)
   GROQ_API_KEY=your_groq_key
   OPENAI_API_KEY=your_openai_key
   GITHUB_TOKEN=your_github_token
   ```

---

## Reproducing the Evaluation (Execution Pipeline)

Researchers can reproduce the complete 50-profile hold-out evaluation (comparing GG-MAD to a standard LLM baseline) by executing the following pipeline within the `ingestion_pipeline/` directory.

**Step 1: Data Extraction**
Extract 1-liners and goals from the raw PDF resumes using PyMuPDF and Tesseract OCR.
```bash
python scripts/extract_profiles.py
```

**Step 2: GG-MAD Batch Execution**
Process the 50 extracted profiles through the full LangGraph multi-agent pipeline to generate clinical, mathematically-grounded Markdown reports.
```bash
streamlit run app_batch_eval.py
```

**Step 3: Report Refinement**
Translate the clinical JSON-like outputs from the pipeline into phased, highly actionable prose suitable for a human end-user.
```bash
streamlit run app_refiner_batch.py
```

**Step 4: LLM-as-a-Judge Evaluation**
Run a strictly calibrated, double-blind evaluation comparing the GG-MAD results against a standard Gemini 3.8 Flash baseline, utilizing a locally hosted Qwen 2.5 14B model as the impartial judge.
```bash
streamlit run app_eval_dashboard.py
```

---

## Key Results

When evaluated on the 50 hold-out profiles, the GG-MAD architecture demonstrated massive quantitative improvements over a standard, ungrounded Gemini baseline. Furthermore, the automated LLM-as-a-Judge evaluation achieved a strong Pearson correlation of **$r = 0.88$** with human domain experts.

| Metric | Gemini Baseline (Mean) | GG-MAD (Mean) | Improvement (%) |
| :--- | :--- | :--- | :--- |
| **Empirical Grounding (EG)** | 7.38 | 8.02 | **+8.67%** |
| **Feasibility Risk (FRA)** | 6.28 | 7.88 | **+25.47%** |
| **Actionability (ANP)** | 6.88 | 8.46 | **+23.0%** |
| **Goal Alignment (GSA)** | 7.28 | 7.82 | **+7.41%** |

---

## Citation

If you use GG-MAD, or build upon our datasets and Multi-Agent Debate architecture, please cite our work:

```bibtex
@inproceedings{tcc_ggmad_2026,
  author    = {Your Name and Co-authors},
  title     = {GG-MAD: Graph-Grounded Multi-Agent Debate for Trajectory-Aware Mentorship Discovery},
  booktitle = {Proceedings of the IEEE International Conference on Tools with Artificial Intelligence (ICTAI)},
  year      = {2026}
}
```
