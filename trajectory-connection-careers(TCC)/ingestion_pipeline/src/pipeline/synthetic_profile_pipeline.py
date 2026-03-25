import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("logs/synthetic_pipeline.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("synthetic_pipeline")

# Import dependencies
from neo4j import GraphDatabase
import chromadb
from chromadb.utils import embedding_functions

from src.enrichment.experience_inferencer import ExperienceInferencer
from src.enrichment.profile_builder import EACRBuilder

class SyntheticPipelineOrchestrator:
    """
    Main pipeline merging structured JSON profiles, Neo4j Graph relations, 
    and ChromaDB semantic documents to generate the EACR Profile representations.
    """
    def __init__(self):
        base_dir = Path(__file__).resolve().parent.parent.parent
        self.unified_path = base_dir / "data" / "processed" / "unified" / "enriched_profiles.json"
        self.output_path = base_dir / "data" / "processed" / "eacr_profiles.json"
        
        # Inits
        load_dotenv(base_dir / ".env")
        self.inferencer = ExperienceInferencer()
        self.builder = EACRBuilder()
        
        # Graph DB Setup (Neo4j)
        self.neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.neo4j_user = os.getenv("NEO4J_USER", "neo4j")
        self.neo4j_pwd = os.getenv("NEO4J_PASSWORD", "password")
        self.driver = None
        try:
            self.driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_pwd))
            self.driver.verify_connectivity()
            logger.info("Successfully connected to Neo4j graph for trajectory extraction.")
        except Exception as e:
            logger.warning(f"Neo4j connection skipped or failed: {e}. Trajectories will be extrapolated from base JSON.")
            self.driver = None

        # Vector DB Setup (ChromaDB)
        db_path = base_dir / "data" / "chroma_db"
        self.chroma_client = chromadb.PersistentClient(path=str(db_path))
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self.narrative_coll = None
        try:
            self.narrative_coll = self.chroma_client.get_collection("medium_narratives", embedding_function=self.embedding_fn)
            logger.info(f"Successfully loaded ChromaDB with {self.narrative_coll.count()} narratives.")
        except Exception as e:
            logger.warning(f"ChromaDB collection mapping failed: {e}. Semantic reasoning will be bypassed.")

    def run(self, build_limit=None):
        """Execute the enrichment pipeline entirely."""
        logger.info("Starting Synthetic EACR Pipeline...")
        
        if not self.unified_path.exists():
            logger.error(f"Cannot run pipeline! File not found: {self.unified_path}")
            return
            
        with open(self.unified_path, "r", encoding="utf-8") as f:
            profiles = json.load(f)
            
        if build_limit:
            profiles = profiles[:build_limit]
            
        eacr_records = []
        for i, p in enumerate(profiles):
            user_id = p.get("user_id", "unsigned")
            
            # Step 1 -> Base candidate loaded (p)
            # Step 2 -> Neo4j Trajectory data overlay
            trajectory = self._extract_neo4j_trajectory(user_id)
            
            # Step 3 -> ChromaDB vector correlation 
            queried_narratives = self._query_chromadb_narratives(p)
            
            # Step 4 -> Inference extraction
            inferred_exp = self.inferencer.infer_narratives(queried_narratives)
            
            # Step 5 -> Model mapping 
            eacr_profile = self.builder.build_profile(p, trajectory, queried_narratives, inferred_exp)
            eacr_records.append(eacr_profile)
            
            if (i+1) % 50 == 0:
                logger.info(f"Generated {i+1}/{len(profiles)} EACR profiles.")
                
        # Step 6 -> Caching Output 
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(eacr_records, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Successfully built {len(eacr_records)} profiles to {self.output_path}.")
        
        if self.driver:
            self.driver.close()

    def _extract_neo4j_trajectory(self, user_id: str) -> dict:
        """Fetch node relational graph traits from Neo4j DB."""
        if not self.driver:
            return {}
            
        trajectory = {
            "start_state": "unknown",
            "current_state": "unknown",
            "observed_paths": [],
            "transition_probabilities": {}
        }
        
        query = """
        MATCH (c:Candidate {user_id: $user_id})-[r:MATCHES_JOB]->(j:Job)
        RETURN j.role AS Role, r.score AS Score
        ORDER BY r.score DESC LIMIT 3
        """
        try:
            with self.driver.session() as session:
                result = session.run(query, user_id=user_id)
                roles = [record["Role"] for record in result]
                if roles:
                    trajectory["observed_paths"] = roles
                    trajectory["current_state"] = roles[0]
                    trajectory["start_state"] = roles[-1] if len(roles) > 1 else roles[0]
        except Exception as e:
            logger.debug(f"Neo4j extraction failed for {user_id}: {e}")
            
        return trajectory

    def _query_chromadb_narratives(self, profile: dict) -> list:
        """Perform similarity queries fetching comparable real-world Medium experiences."""
        if not self.narrative_coll:
            return []
            
        # Compile a semantic query from the skills and domains
        skills = profile.get("skills", {})
        skill_names = list(skills.keys()) if isinstance(skills, dict) else skills
        domains = profile.get("domains", [])
        
        if not skill_names and not domains: return []
            
        search_terms = f"Career experiences of someone working with {' '.join(skill_names[:5])} in {' '.join(domains[:3])}, including learning journey, decisions, and challenges"
        
        try:
            results = self.narrative_coll.query(
                query_texts=[search_terms],
                n_results=2
            )
            narratives = []
            if results and results.get("ids") and len(results["ids"][0]) > 0:
                for idx in range(len(results["ids"][0])):
                    narratives.append({
                        "id": results["ids"][0][idx],
                        "summary": results["documents"][0][idx],
                        "themes": results["metadatas"][0][idx].get("themes", "[]") if results.get("metadatas") else []
                    })
            return narratives
        except Exception as e:
            logger.debug(f"ChromaDB lookup failed for {profile.get('user_id')}: {e}")
            return []

if __name__ == "__main__":
    orchestrator = SyntheticPipelineOrchestrator()
    orchestrator.run()
