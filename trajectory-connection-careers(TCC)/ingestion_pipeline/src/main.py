import logging
import argparse
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = str(Path(__file__).resolve().parent.parent if "src" in str(Path(__file__)) else Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

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

async def interactive_session():
    """
    Runs an interactive career mentorship session.
    Optionally accepts a resume file path to enrich the user's profile.
    """
    from src.ingestion.resume_parser import parse_resume
    from src.ingestion.resume_merger import merge_resume_with_query

    print("\n" + "="*50)
    print("🚀 Trajectory-Aware Career Intelligence System")
    print("="*50 + "\n")

    while True:
        # --- Optional resume input ---
        try:
            resume_path = input("📄 (Optional) Enter path to your resume PDF or TXT [press Enter to skip]: ").strip()
        except EOFError:
            break

        resume_text = None
        if resume_path:
            if not os.path.exists(resume_path):
                print(f"⚠️  File not found: '{resume_path}'. Continuing without resume.\n")
            else:
                try:
                    resume_text = parse_resume(resume_path)
                    print(f"✅ Resume loaded ({len(resume_text)} characters extracted).\n")
                except Exception as e:
                    print(f"⚠️  Could not parse resume: {e}. Continuing without resume.\n")
                    resume_text = None

        # --- Career query input ---
        try:
            query = input("🤖 Tell me about your background, skills, interests and career goals\n→ ").strip()
        except EOFError:
            break

        if not query: continue
        if query.lower() in ("exit", "quit", "q"): break

        # --- Merge resume with query if available ---
        if resume_text:
            enriched_input = merge_resume_with_query(resume_text, query)
        else:
            enriched_input = query

        print("\n🔮 Deep Thinking...")
        try:
            await run_career_mentorship(enriched_input)
        except Exception as e:
            logger.error(f"Session error: {e}")

        print("\n" + "-"*50 + "\n")

def ingestion_mode():
    """
    Batch ingestion logic.
    """
    INGESTION_CONFIG = {
        "github": {
            "usernames": ["octocat", "torvalds", "khushi0605"]
        }
    }
    logger.info("Starting Batch Ingestion Pipeline...")
    for source, params in INGESTION_CONFIG.items():
        logger.info(f"--- Processing Source: {source} ---")
        try:
            # Fix: use run_ingestion (the renamed import)
            run_ingestion(source=source, usernames=params.get("usernames"))
        except Exception as e:
            logger.error(f"Batch execution failed for {source}: {e}")
    logger.info("Batch Ingestion Pipeline completed.")

def main():
    parser = argparse.ArgumentParser(description="Career Connection Intelligence System")
    parser.add_argument("--mode", choices=["ingest", "career"], default="career",
                        help="Mode: 'ingest' for batch data, 'career' for interactive mentorship (default)")
    
    args = parser.parse_args()
    
    if args.mode == "ingest":
        ingestion_mode()
    else:
        try:
            asyncio.run(interactive_session())
        except KeyboardInterrupt:
            print("\nExiting...")

if __name__ == "__main__":
    main()
