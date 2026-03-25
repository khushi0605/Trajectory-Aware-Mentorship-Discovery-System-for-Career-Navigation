import os
import sys
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Step 1: Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from storage.neo4j_ingestor import Neo4jIngestor
from enrichment.graph_experience_layer import GraphExperienceLayer

# Setup logging
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("logs/rebuild_graph.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("rebuild_graph")

def main():
    load_dotenv()
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    pwd = os.getenv("NEO4J_PASSWORD", "password")

    driver = None
    try:
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        driver.verify_connectivity()
        logger.info(f"Successfully connected to Neo4j at {uri}")
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {e}")
        return

    # Step 2: Cleanup orphaned nodes
    try:
        logger.info("Cleaning up orphaned 'id'-keyed nodes...")
        with driver.session() as session:
            session.run("MATCH (c:Candidate) WHERE c.id IS NOT NULL AND c.user_id IS NULL DETACH DELETE c")
        logger.info("Cleanup complete.")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")

    # Step 3: Remove duplicate HAS_SKILL relationships
    try:
        logger.info("Removing duplicate HAS_SKILL relationships...")
        with driver.session() as session:
            session.run("""
                MATCH (c:Candidate)-[r:HAS_SKILL]->(s:Skill) 
                WITH c, s, collect(r) AS rels WHERE size(rels) > 1
                FOREACH (r IN tail(rels) | DELETE r)
            """)
        logger.info("Duplicate relationship removal complete.")
    except Exception as e:
        logger.error(f"Relationship cleanup failed: {e}")

    # Step 4: Instantiate Neo4jIngestor and ingest base data
    try:
        logger.info("Starting base ingestion...")
        ingestor = Neo4jIngestor()
        ingestor.ingest_data()
        ingestor.close()
        logger.info("Base ingestion complete.")
    except Exception as e:
        logger.error(f"Base ingestion failed: {e}")

    # Step 5 & 6: Load enriched profiles and run GraphExperienceLayer
    try:
        logger.info("Starting EACR experience layer enrichment...")
        enriched_path = Path("data/processed/eacr_profiles_enriched.json")
        if not enriched_path.exists():
            logger.error(f"Enriched profiles file not found at {enriched_path}")
        else:
            with open(enriched_path, 'r', encoding='utf-8') as f:
                profiles = json.load(f)
            
            g_layer = GraphExperienceLayer(driver)
            counts = g_layer.enrich_graph(profiles)
            
            # Step 7: Print ingestion counts
            logger.info("--- Ingestion Results ---")
            for k, v in counts.items():
                logger.info(f"{k.capitalize()}: {v}")
    except Exception as e:
        logger.error(f"Experience layer enrichment failed: {e}")

    # Step 8: Verification query
    try:
        logger.info("Running final verification...")
        with driver.session() as session:
            total_candidates = session.run("MATCH (c:Candidate) WHERE c.user_id IS NOT NULL RETURN count(c) AS total").single()["total"]
            total_skill_edges = session.run("MATCH (c:Candidate)-[:HAS_SKILL]->(s:Skill) RETURN count(*) AS total").single()["total"]
            total_decisions = session.run("MATCH (c:Candidate)-[:MADE_DECISION]->(d:Decision) RETURN count(*) AS total").single()["total"]
            
            print("\n" + "="*40)
            print("REBUILD SUMMARY TABLE")
            print("="*40)
            print(f"{'Metric':<25} | {'Count':<10}")
            print("-" * 40)
            print(f"{'Total Candidates':<25} | {total_candidates:<10}")
            print(f"{'Total Skill Edges':<25} | {total_skill_edges:<10}")
            print(f"{'Total Decision Edges':<25} | {total_decisions:<10}")
            print("="*40)
            
    except Exception as e:
        logger.error(f"Verification query failed: {e}")

    if driver:
        driver.close()

if __name__ == "__main__":
    main()
