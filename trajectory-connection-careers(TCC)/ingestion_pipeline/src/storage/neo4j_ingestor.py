import json
import logging
import os
import sys
from pathlib import Path
import glob

from dotenv import load_dotenv

try:
    from neo4j import GraphDatabase
except ImportError:
    print("neo4j not installed. Please run: pip install neo4j")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(name)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler("logs/neo4j_ingestor.log", mode='w'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("neo4j_ingestor")

class Neo4jIngestor:
    def __init__(self):
        load_dotenv()
        self.uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        self.user = os.getenv("NEO4J_USER", "neo4j")
        self.password = os.getenv("NEO4J_PASSWORD", "password")
        
        self.driver = None
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            self.driver.verify_connectivity()
            logger.info(f"Successfully connected to Neo4j at {self.uri}")
        except Exception as e:
            logger.warning(f"Could not connect to Neo4j. Ingestion cannot proceed. Error: {e}")

        # Paths
        self.profiles_path = Path("data/processed/unified/enriched_profiles.json")
        self.jobs_dir = Path("data/processed/job_req_profiles")
        self.matches_path = Path("data/processed/matches/profile_job_matches.json")
        self.taxonomy_path = Path("data/reference/skill_taxonomy.json")
        self.domain_map_path = Path("data/reference/domain_map.json")

    def close(self):
        if self.driver:
            self.driver.close()

    def ingest_data(self):
        if not self.driver:
            logger.error("No active Neo4j connection. Exiting ingestion.")
            return

        with self.driver.session() as session:
            self._ingest_taxonomy_and_domains(session)
            self._ingest_candidates(session)
            self._ingest_jobs(session)
            self._ingest_matches(session)

    def _ingest_taxonomy_and_domains(self, session):
        logger.info("Ingesting Skills and Domains...")
        
        # Load taxonomy
        taxonomy_data = {}
        if self.taxonomy_path.exists():
            with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
                taxonomy_data = json.load(f)
        
        # Ingest skills and link to domains
        query = """
        UNWIND $records AS record
        MERGE (d:Domain {name: record.domain})
        MERGE (s:Skill {name: record.skill})
        MERGE (s)-[:BELONGS_TO_DOMAIN]->(d)
        """
        
        records = []
        for domain, skills in taxonomy_data.items():
            for skill in skills:
                records.append({"domain": domain.lower(), "skill": skill.lower()})
                
        if records:
            session.run(query, records=records)
        logger.info(f"Ingested {len(records)} Skill->Domain relationships.")

    def _ingest_candidates(self, session):
        logger.info("Ingesting Candidates...")
        if not self.profiles_path.exists():
            logger.warning(f"Profiles file not found at {self.profiles_path}")
            return
            
        with open(self.profiles_path, 'r', encoding='utf-8') as f:
            profiles = json.load(f)
        
        query = """
        UNWIND $candidates AS c
        
        // Merge Candidate
        MERGE (cand:Candidate {user_id: c.user_id})
        SET cand.experience_level = c.experience_level,
            cand.github_score = c.github_score,
            cand.kaggle_score = c.kaggle_score,
            cand.confidence_score = c.confidence_score
            
        // Domain Relationship
        WITH cand, c
        UNWIND c.domains AS dom
        MERGE (d:Domain {name: dom})
        MERGE (cand)-[:IN_DOMAIN]->(d)
        
        // Skill Relationship
        WITH cand, c
        UNWIND c.skills AS skill_node
        MERGE (s:Skill {name: skill_node.name})
        MERGE (cand)-[r:HAS_SKILL]->(s)
        SET r.proficiency = skill_node.weight
        """
        
        # Transform data for Cypher UNWIND
        candidates_payload = []
        for prof in profiles:
            uid = prof.get("user_id", prof.get("username", "unknown"))
            lvl = prof.get("experience_level", prof.get("career_stage", "unknown"))
            
            # Transform skills dict into list of dicts
            skills_dict = prof.get("skills", {})
            skills_arr = [{"name": k.lower(), "weight": float(v)} for k, v in skills_dict.items()] if isinstance(skills_dict, dict) else []
            
            candidates_payload.append({
                "user_id": uid,
                "experience_level": lvl,
                "github_score": prof.get("github_metrics", {}).get("impact_score", prof.get("github_score", 0.0)),
                "kaggle_score": prof.get("kaggle_metrics", {}).get("performance_score", prof.get("kaggle_score", 0.0)),
                "confidence_score": prof.get("confidence_score", 0.0),
                "domains": [d.lower() for d in prof.get("domains", [])],
                "skills": skills_arr
            })
            
        if candidates_payload:
            session.run(query, candidates=candidates_payload)
            
        logger.info(f"Ingested {len(candidates_payload)} Candidate nodes.")

    def _ingest_jobs(self, session):
        logger.info("Ingesting Jobs...")
        job_files = glob.glob(str(self.jobs_dir / "*.json"))
        
        roles = []
        for jf in job_files:
            if Path(jf).name.startswith("_"): continue
            
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    roles.append(data)
                elif isinstance(data, list):
                    roles.extend(data)
                    
        query = """
        UNWIND $jobs AS j
        
        MERGE (job:Job {role: j.role})
        SET job.job_count = j.job_count
        
        WITH job, j
        UNWIND j.required_skills AS req
        MERGE (s:Skill {name: req.name})
        MERGE (job)-[r:REQUIRES_SKILL]->(s)
        SET r.weight = req.weight
        """
        
        jobs_payload = []
        for role in roles:
            r_name = role.get("role", "unknown")
            r_skills = role.get("required_skills", [])
            s_arr = [{"name": s.lower() if isinstance(s, str) else str(s).lower(), "weight": 1.0} for s in r_skills]
            
            jobs_payload.append({
                "role": r_name,
                "job_count": role.get("job_count", 0),
                "required_skills": s_arr
            })
            
        if jobs_payload:
            session.run(query, jobs=jobs_payload)
            
        logger.info(f"Ingested {len(jobs_payload)} Job nodes.")

    def _ingest_matches(self, session):
        logger.info("Ingesting Match Relationships...")
        if not self.matches_path.exists():
            logger.warning(f"Matches file not found at {self.matches_path}")
            return
            
        with open(self.matches_path, 'r', encoding='utf-8') as f:
            matches_data = json.load(f)
            
        query = """
        UNWIND $matches AS m
        MATCH (cand:Candidate {user_id: m.user_id})
        MATCH (job:Job {role: m.role})
        MERGE (cand)-[r:MATCHES_JOB]->(job)
        SET r.score = m.overall_score,
            r.skill_score_component = m.skill_score_component,
            r.level_score_component = m.level_score_component,
            r.domain_score_component = m.domain_score_component,
            r.matched_skills_count = m.matched_skills_count,
            r.missing_skills_count = m.missing_skills_count
        """
        
        matches_payload = []
        for match_group in matches_data:
            role = match_group.get("role")
            for profile in match_group.get("matched_profiles", []):
                uid = profile.get("user_id")
                # Deduce components backwards or pass them along safely
                overall = profile.get("overall_score", profile.get("match_score", 0.0))
                level_score = profile.get("experience_level_score", 0.0)
                domain_score = profile.get("domain_score", 0.0)
                # Reverse math for skill_score_component since formula was 0.7s + 0.2l + 0.1d
                skill_score = (overall - (0.2 * level_score) - (0.1 * domain_score)) / 0.7 if overall else 0.0
                
                matches_payload.append({
                    "role": role,
                    "user_id": uid,
                    "overall_score": overall,
                    "skill_score_component": round(skill_score, 4),
                    "level_score_component": level_score,
                    "domain_score_component": domain_score,
                    "matched_skills_count": len(profile.get("matched_skills", [])),
                    "missing_skills_count": len(profile.get("missing_skills", []))
                })
                
        # Batch upload to avoid overwhelming memory
        batch_size = 1000
        for i in range(0, len(matches_payload), batch_size):
            batch = matches_payload[i:i + batch_size]
            session.run(query, matches=batch)
            
        logger.info(f"Ingested {len(matches_payload)} MATCHES_JOB relationships.")


if __name__ == "__main__":
    Path("logs").mkdir(exist_ok=True)
    ingestor = Neo4jIngestor()
    ingestor.ingest_data()
    ingestor.close()
