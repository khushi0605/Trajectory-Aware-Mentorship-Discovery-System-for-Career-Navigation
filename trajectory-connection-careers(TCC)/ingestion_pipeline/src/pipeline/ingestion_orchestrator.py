import argparse
import yaml
import logging
from pathlib import Path
from typing import List, Optional

from src.ingestion.factories.collector_factory import CollectorFactory

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("src.pipeline.ingestion_orchestrator")

def load_config(config_path: str):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)

def run_pipeline(source: str, usernames: Optional[List[str]] = None, batch_limit: int = 10):
    config_path = "configs/ingestion_sources.yaml"
    config = load_config(config_path)
    
    logger.info(f"Initialized ingestion for source: {source}")
    
    try:
        collector = CollectorFactory.get_collector(source, config)
        
        params = {}
        if source == "github" and usernames:
            params["usernames"] = usernames
        elif source == "kaggle":
            params["batch_limit"] = batch_limit
        logger.info(f"Running collector for {source}...")
        collector.run(**params)
        logger.info(f"Ingestion complete for {source}.")
        
    except Exception as e:
        logger.error(f"Pipeline failed for {source}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mentorship Discovery Ingestion Orchestrator")
    parser.add_argument("--source", required=True, help="Data source (github, kaggle)")
    parser.add_argument("--usernames", nargs="+", help="Usernames for GitHub collection")
    parser.add_argument("--batch-limit", type=int, default=10, help="Batch limit for Kaggle collection")
    
    args = parser.parse_args()
    run_pipeline(args.source, args.usernames, args.batch_limit)
