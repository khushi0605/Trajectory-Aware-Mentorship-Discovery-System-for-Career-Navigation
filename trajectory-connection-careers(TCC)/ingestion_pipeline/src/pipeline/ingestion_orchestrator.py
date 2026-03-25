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

def run_pipeline(source: Optional[str] = None, usernames: Optional[List[str]] = None, batch_limit: int = 10, enable_neo4j: bool = False, enrich_eacr: bool = False):
    # Resolve config path relative to this file's parent (src/pipeline/)
    base_dir = Path(__file__).resolve().parent.parent.parent
    config_path = base_dir / "configs" / "ingestion_sources.yaml"
    config = load_config(str(config_path))
    
    if source:
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
            
            if enable_neo4j:
                logger.info("Initializing Neo4j Graph Database Ingestion...")
                from src.storage.neo4j_ingestor import Neo4jIngestor
                neo4j_pipeline = Neo4jIngestor()
                neo4j_pipeline.ingest_data()
                neo4j_pipeline.close()
                logger.info("Neo4j Ingestion completed successfully.")
                
        except Exception as e:
            logger.error(f"Pipeline failed for {source}: {e}")

    if enrich_eacr:
        logger.info("Executing Phase 2 EACR Enrichment...")
        import json, os
        from neo4j import GraphDatabase
        import chromadb
        from chromadb.utils import embedding_functions
        from dotenv import load_dotenv
        
        from src.enrichment.narrative_inferencer import NarrativeInferencer
        from src.enrichment.reachability_scorer import ReachabilityScorer
        from src.enrichment.graph_experience_layer import GraphExperienceLayer
        
        load_dotenv(base_dir / ".env")
        eacr_path = base_dir / "data" / "processed" / "eacr_profiles.json"
        if not eacr_path.exists():
            logger.error("Cannot enrich: eacr_profiles.json missing! Run synthetic pipeline first.")
            return
            
        with open(eacr_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)
            
        with open(base_dir / "data" / "reference" / "domain_map.json", "r") as f:
            domain_map = json.load(f)
            
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        pwd = os.getenv("NEO4J_PASSWORD", "password")
        neo4j_driver = GraphDatabase.driver(uri, auth=(user, pwd))
        
        chroma_client = chromadb.PersistentClient(path=str(base_dir / "data" / "chroma_db"))
        emb_fn = embedding_functions.DefaultEmbeddingFunction()
        chroma_coll = chroma_client.get_collection("medium_narratives", embedding_function=emb_fn)
        
        inferencer = NarrativeInferencer(neo4j_driver, chroma_coll, domain_map)
        scorer = ReachabilityScorer()
        
        logger.info(f"Enriching {len(profiles)} profiles with heuristic and db mappings...")
        for p in profiles:
            inferencer.infer_candidate(p)
            scorer.calculate(p)
            
        out_path = base_dir / "data" / "processed" / "eacr_profiles_enriched.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(profiles, f, indent=2, ensure_ascii=False)
            
        def validate_enriched_profiles(profiles: list) -> dict:
            issues = []
            for p in profiles:
                uid = p.get("user_id", "unknown")
                for field, key in [
                    ("decision_points", "decision"),
                    ("struggles", "struggle"),
                    ("learning_patterns", "text")
                ]:
                    items = p.get("experience_model", {}).get(field, [])
                    texts = [i.get(key, "") for i in items]
                    if len(texts) != len(set(texts)):
                        issues.append(f"{uid}: duplicate in {field}")
            return {
                "total_profiles": len(profiles),
                "profiles_with_issues": len(issues),
                "issues": issues
            }

        val_report = validate_enriched_profiles(profiles)
        val_msg = f"Validation Report: {val_report['total_profiles']} total, {val_report['profiles_with_issues']} with issues."
        logger.info(val_msg)
        
        log_dir = base_dir / "logs"
        log_dir.mkdir(exist_ok=True)
        with open(log_dir / "eacr_enrichment.log", "a", encoding="utf-8") as lf:
            lf.write(val_msg + "\n")
            if val_report["issues"]:
                lf.write("\n".join(val_report["issues"]) + "\n")
                
        if val_report["profiles_with_issues"] > 0:
            logger.warning(f"Found {val_report['profiles_with_issues']} profiles with duplicate entries after deduplication!")
            
        logger.info("Enrichment logic completed. Transmitting results mapped to Graph Nodes...")
        g_layer = GraphExperienceLayer(neo4j_driver)
        counts = g_layer.enrich_graph(profiles)
        
        logger.info(f"Enriched {len(profiles)} profiles | Neo4j nodes added: {counts['decisions']} decisions, {counts['struggles']} struggles, {counts['lps']} learning patterns")
        neo4j_driver.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mentorship Discovery Ingestion Orchestrator")
    parser.add_argument("--source", required=False, help="Data source (github, kaggle)")
    parser.add_argument("--usernames", nargs="+", help="Usernames for GitHub collection")
    parser.add_argument("--batch-limit", type=int, default=10, help="Batch limit for Kaggle collection")
    parser.add_argument("--enable-neo4j", action="store_true", help="Ingest output entities into the Neo4j graph database")
    parser.add_argument("--enrich-eacr", action="store_true", help="Execute semantic EACR layer extending base graph nodes with decision/struggle tracking")
    
    args = parser.parse_args()
    if not args.source and not args.enrich_eacr:
        parser.error("Must specify either --source or --enrich-eacr")
        
    run_pipeline(args.source, args.usernames, args.batch_limit, args.enable_neo4j, args.enrich_eacr)
