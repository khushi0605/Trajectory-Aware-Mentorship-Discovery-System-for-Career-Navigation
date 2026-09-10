from __future__ import annotations
import logging
from typing import List, Dict, Any, Tuple
from neo4j import GraphDatabase
from src.retrieval.models import TrajectoryPath, BehavioralSignal
from src.retrieval.config.retriever_config import Neo4jConfig

logger = logging.getLogger("neo4j_connector")

# Maps user interest/goal terms to your actual normalized role slugs in the graph
INTEREST_TO_ROLES = {
    "machine learning":    ["ml_engineer", "data_scientist", "research_scientist", "ai_engineer"],
    "big data":            ["data_engineer", "data_scientist", "big_data_engineer", "data_analyst"],
    "data science":        ["data_scientist", "data_analyst", "data_engineer"],
    "computer vision":     ["ml_engineer", "computer_vision_engineer", "research_scientist"],
    "generative ai":       ["ml_engineer", "ai_engineer", "research_scientist", "data_scientist"],
    "software engineering":["software_engineer", "backend_developer", "fullstack_developer"],
    "web development":     ["frontend_developer", "fullstack_developer", "javascript_developer"],
    "cloud":               ["cloud_engineer", "devops_engineer", "cloud_migration_specialist"],
    "devops":              ["devops_engineer", "system_engineer", "cloud_automation_engineer"],
    "healthcare tech":     ["data_scientist", "ml_engineer", "research_scientist"],
    "mobile":              ["ios_mobile_app_engineer", "android_developer", "mobile_developer"],
    "backend":             ["backend_developer", "software_engineer", "system_engineer"],
    "python":              ["data_scientist", "ml_engineer", "backend_developer", "software_engineer"],
    "javascript":          ["javascript_developer", "frontend_developer", "fullstack_developer"],
}

def _resolve_roles(interest: str, goal: str) -> List[str]:
    """Map free-text interest/goal to actual role slugs in the graph."""
    roles = set()
    combined = (interest + " " + goal).lower()
    
    for keyword, role_list in INTEREST_TO_ROLES.items():
        if keyword in combined:
            roles.update(role_list)
    
    # Also try goal directly as a slug (if ProfileUnderstanding returned a clean role)
    clean_goal = goal.lower().replace("-", "_")
    roles.add(clean_goal)
    
    # Fallback: any token from interest that might be a partial role match
    for token in interest.lower().split():
        if len(token) > 2:  # Changed from 4 to 2 to capture 'ai', 'ml'
            roles.add(token)
    
    # CRITICAL FIX: Convert slugs to space-separated strings for Neo4j text matching
    final_roles = [r.replace("_", " ") for r in roles]
    return final_roles if final_roles else ["data scientist", "software engineer", "ml engineer"]


class Neo4jConnector:
    def __init__(self, config: Neo4jConfig):
        self.driver = GraphDatabase.driver(
            config.uri,
            auth=(config.user, config.password)
        )

    def close(self):
        self.driver.close()

    async def get_trajectory_paths(self, interest: str, goal: str, skills: List[str], limit: int) -> Tuple[List[TrajectoryPath], bool]:
        fallback_used = False
        paths = []
        role_terms = _resolve_roles(interest, goal)
        logger.info(f"Resolved role terms for interest='{interest}' goal='{goal}': {role_terms}")

        try:
            with self.driver.session() as session:
                # Primary: match via MADE_DECISION → TRIGGERED_TRANSITION → Job role
                primary_query = """
                MATCH (c:Candidate)-[:MADE_DECISION]->(d:Decision)-[:TRIGGERED_TRANSITION]->(j:Job)
                WHERE any(term IN $role_terms WHERE toLower(j.role) CONTAINS term)
                RETURN coalesce(c.id, c.user_id) AS candidate_id,
                       coalesce(c.reachability_score, 1.0) AS reachability,
                       coalesce(d.text, "Unknown Decision") AS decision_text,
                       coalesce(d.trigger, "Unknown Trigger") AS trigger,
                       j.role AS target_role
                ORDER BY reachability DESC
                LIMIT $limit
                """
                result = session.run(primary_query, role_terms=role_terms, limit=limit)
                rows = result.data()

                if not rows:
                    fallback_used = True
                    fallback_query = """
                    MATCH (c:Candidate)-[:CURRENT_ROLE]->(j:Job)
                    WHERE any(term IN $role_terms WHERE toLower(j.role) CONTAINS term)
                    RETURN coalesce(c.id, c.user_id) AS candidate_id,
                           coalesce(c.reachability_score, 1.0) AS reachability,
                           j.role AS target_role,
                           "Current role match" AS decision_text,
                           "Role similarity" AS trigger
                    ORDER BY reachability DESC
                    LIMIT $limit
                    """
                    result = session.run(fallback_query, role_terms=role_terms, limit=limit)
                    rows = result.data()

                if not rows and skills:
                    fallback_used = True
                    # Use explicit skills instead of string parsing
                    lower_skills = [s.lower() for s in skills]
                    broad_query = """
                    MATCH (c:Candidate)-[:HAS_SKILL]->(s:Skill)
                    WHERE any(term IN $skill_terms WHERE toLower(s.name) CONTAINS term)
                    WITH c, collect(s.name) AS matched_skills
                    OPTIONAL MATCH (c)-[:CURRENT_ROLE]->(j:Job)
                    RETURN coalesce(c.id, c.user_id) AS candidate_id,
                           coalesce(c.reachability_score, 1.0) AS reachability,
                           coalesce(j.role, "software engineer") AS target_role,
                           "Skill-based match" AS decision_text,
                           head(matched_skills) AS trigger
                    ORDER BY reachability DESC
                    LIMIT $limit
                    """
                    result = session.run(broad_query, skill_terms=lower_skills, limit=limit)
                    rows = result.data()

                for row in rows:
                    paths.append(TrajectoryPath(
                        candidate_id=row["candidate_id"],
                        reachability_score=float(row["reachability"]),
                        decision_text=row["decision_text"],
                        trigger=row["trigger"],
                        target_role=row["target_role"]
                    ))
        except Exception as e:
            logger.error(f"Neo4j get_trajectory_paths failed: {e}")
            raise

        return paths, fallback_used

    async def get_behavioral_signals(self, domain: str, interest: str, skills: List[str], limit: int) -> List[BehavioralSignal]:
        signals = []
        skill_terms = [s.lower() for s in skills] + [interest.lower(), domain.lower()]
        
        try:
            with self.driver.session() as session:
                query = """
                // Struggles
                MATCH (c:Candidate)-[:FACED]->(s:Struggle)
                OPTIONAL MATCH (s)-[:IN_DOMAIN]->(dom:Domain)
                WHERE any(term IN $skill_terms 
                          WHERE toLower(s.text) CONTAINS term
                             OR (dom IS NOT NULL AND toLower(dom.name) CONTAINS term))
                RETURN c.user_id    AS candidate_id,
                       s.text       AS text,
                       s.resolved   AS resolved,
                       coalesce(dom.name, $domain) AS domain,
                       "struggle"   AS signal_type
                LIMIT $limit

                UNION

                // Learning patterns
                MATCH (c:Candidate)-[:LEARNED_VIA]->(lp:LearningPattern)
                WHERE any(term IN $skill_terms 
                          WHERE toLower(lp.text) CONTAINS term
                             OR any(theme IN lp.themes WHERE toLower(theme) CONTAINS term))
                RETURN c.user_id        AS candidate_id,
                       lp.text          AS text,
                       true             AS resolved,
                       lp.skill_source  AS domain,
                       "learning_pattern" AS signal_type
                LIMIT $limit
                """
                result = session.run(query,
                                     skill_terms=skill_terms,
                                     domain=domain,
                                     limit=limit)
                for row in result.data():
                    signals.append(BehavioralSignal(
                        candidate_id=row["candidate_id"],
                        text=row["text"] or "",
                        resolved=bool(row["resolved"]),
                        domain=row["domain"] or domain,
                        signal_type=row["signal_type"]
                    ))

        except Exception as e:
            logger.error(f"Neo4j get_behavioral_signals failed: {e}")
            raise

        return signals
