# Career Intelligence System: Ingestion Pipeline

A modular data ingestion system designed to build career trajectories by scraping and processing data from various professional sources.

## 📁 Repository Structure
```text
.
├── ingestion_pipeline/
│   ├── configs/             # Source configurations (YAML)
│   ├── data/                # Raw scraped data (Gitignored)
│   ├── src/                 # Core logic, collectors, and scrapers
│   ├── tests/               # Integration and unit tests
│   └── main.py              # Entry point for batch ingestion
└── .gitignore               # Standard exclusions
```

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.9+
- GitHub Personal Access Token (for high-limit scraping)

### 2. Setup
```bash
# 1. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# 2. Install dependencies
pip install -r ingestion_pipeline/requirements.txt

# 3. Configure environment variables
cd ingestion_pipeline
cp .env.example .env
# Edit .env with your credentials
```

### 3. Usage
Run the batch ingestion pipeline for specific sources:
```bash
export PYTHONPATH=.
python3 src/main.py
```

## 🛠 Features
- **GitHub Scraper**: Professional REST API implementation with schema mapping.
- **Kaggle Collector**: Automated metadata retrieval for competitions.
- **Modular Design**: Easy to extend with new collectors/scrapers.
- **Rate Limiting**: Built-in throttling and retry logic for APIs.
