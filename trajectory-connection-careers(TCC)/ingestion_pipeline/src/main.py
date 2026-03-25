import logging
import argparse
import asyncio
from dotenv import load_dotenv
from src.pipeline.ingestion_orchestrator import run_pipeline as run_ingestion
from src.app.runner import run_pipeline as run_career_mentorship

# Authenticate and load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("src.main")

# CONFIGURATION: Define sources and identifiers here
INGESTION_CONFIG = {
    "github": {
        "usernames": ["octocat", "torvalds", "khushi0605"]
    },
    # "kaggle": {
    #     "batch_limit": 5
    # }
}

def main():
    """
    Main entry point for batch ingestion.
    Iterates through INGESTION_CONFIG and executes the pipeline for each source.
    """
    logger.info("Starting Batch Ingestion Pipeline...")
    
    for source, params in INGESTION_CONFIG.items():
        logger.info(f"--- Processing Source: {source} ---")
        
        usernames = params.get("usernames")
        batch_limit = params.get("batch_limit", 10)
        
        try:
            run_pipeline(
                source=source,
                usernames=usernames,
                batch_limit=batch_limit
            )
        except Exception as e:
            logger.error(f"Batch execution failed for {source}: {e}")

    logger.info("Batch Ingestion Pipeline completed.")

if __name__ == "__main__":
    main()
