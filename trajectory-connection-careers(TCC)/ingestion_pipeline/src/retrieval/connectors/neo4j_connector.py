from __future__ import annotations
import logging
from typing import List, Dict, Any, Tuple
from neo4j import GraphDatabase
from ..models import TrajectoryPath, BehavioralSignal
from ..config.retriever_config import Neo4jConfig

logger = logging.getLogger("neo4j_connector")

class Neo4jConnector:
    def __init__(self, config: Neo4jConfig):
        self.driver = GraphDatabase.driver(
            config.uri, 
            auth=(config.user, config.password)
        )

    def close(self):
        self.driver.close()

    async def get_trajectory_paths(self, interest: str, goal: str, limit: int) -> Tuple[List[TrajectoryPath], bool]:
        """
        Executes the trajectory path query with fallback logic.
        Returns: (List[TrajectoryPath], fallback_used_bool)
        """
        fallback_used = False
        paths = []
        
        try:
            with self.driver.session() as session:
                # Primary Query: decision-triggered transitions
                # Using toLower for case-insensitivity
                primary_query = """
                MATCH (c:Candidate)-[:MADE_DECISION]->(d:Decision)
                      -[:TRIGGERED_TRANSITION]->(j:Job)
                WHERE toLower(d.trigger) CONTAINS toLower($interest)
                   OR toLower(j.role) CONTAINS toLower($interest)
                   OR any(term in [toLower(j.role), toLower(d.trigger)] WHERE any(g in $goal_terms WHERE term CONTAINS g))
                RETURN c.user_id        AS candidate_id,
                       c.reachability_score AS reachability,
                       d.text           AS decision_text,
                       d.trigger        AS trigger,
                       j.role           AS target_role
                ORDER BY c.reachability_score DESC
                LIMIT $limit
                """
                # Split goal into terms for better matching (e.g. "research or industry" -> ["research", "industry"])
                goal_terms = [t.strip().lower() for t in goal.replace(" or ", ",").replace("/", ",").split(",") if t.strip()]
                if not goal_terms: goal_terms = [goal.lower()]

                result = session.run(primary_query, interest=interest, goal_terms=goal_terms, limit=limit)
                rows = result.data()
                
                if not rows:
                    fallback_used = True
                    logger.info("Neo4j primary query returned 0 rows, running fallback role-only match.")
                    fallback_query = """
                    MATCH (c:Candidate)-[:CURRENT_ROLE]->(j:Job)
                    WHERE any(g in $goal_terms WHERE toLower(j.role) CONTAINS g)
                       OR toLower(j.role) CONTAINS toLower($interest)
                    RETURN c.user_id AS candidate_id,
                           c.reachability_score AS reachability,
                           j.role AS target_role,
                           "Standard career progression" AS decision_text,
                           "Automatic role match" AS trigger
                    ORDER BY c.reachability_score DESC
                    LIMIT $limit
                    """
                    result = session.run(fallback_query, goal_terms=goal_terms, limit=limit)
                    rows = result.data()
                
                for row in rows:
                    paths.append(TrajectoryPath(
                        candidate_id=row["candidate_id"],
                        reachability_score=row["reachability"],
                        decision_text=row["decision_text"],
                        trigger=row["trigger"],
                        target_role=row["target_role"]
                    ))
                    
        except Exception as e:
            logger.error(f"Neo4j get_trajectory_paths failed: {e}")
            raise # Let RAGRetriever handle partial failures and failed_sources

        return paths, fallback_used

    async def get_behavioral_signals(self, domain: str, interest: str, limit: int) -> List[BehavioralSignal]:
        """
        Executes the behavioral context query combining struggles and learning patterns.
        """
        signals = []
        try:
            with self.driver.session() as session:
                query = """
                MATCH (c:Candidate)-[:FACED]->(s:Struggle)-[:IN_DOMAIN]->(dom:Domain)
                WHERE toLower(dom.name) CONTAINS toLower($domain)
                RETURN c.user_id    AS candidate_id,
                       s.text       AS text,
                       s.resolved   AS resolved,
                       dom.name     AS domain,
                       "struggle"   AS signal_type
                LIMIT $limit

                UNION

                MATCH (c:Candidate)-[:LEARNED_VIA]->(lp:LearningPattern)
                WHERE any(theme in lp.themes WHERE toLower(theme) CONTAINS toLower($domain))
                   OR toLower(lp.skill_source) CONTAINS toLower($interest)
                RETURN c.user_id    AS candidate_id,
                       lp.text      AS text,
                       True         AS resolved,
                       lp.skill_source AS domain,
                       "learning_pattern" AS signal_type
                LIMIT $limit
                """
                result = session.run(query, domain=domain, interest=interest, limit=limit)
                for row in result.data():
                    signals.append(BehavioralSignal(
                        candidate_id=row["candidate_id"],
                        text=row["text"],
                        resolved=row["resolved"],
                        domain=row["domain"],
                        signal_type=row["signal_type"]
                    ))
        except Exception as e:
            logger.error(f"Neo4j get_behavioral_signals failed: {e}")
            raise
            
        return signals
