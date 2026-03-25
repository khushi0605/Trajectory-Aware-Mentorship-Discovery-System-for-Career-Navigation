import logging
from typing import Dict, Any, List

logger = logging.getLogger("graph_experience_layer")

class GraphExperienceLayer:
    """
    Extends the existing Neo4j knowledge graph using a deterministic,
    research-consistent schema (EACR).
    """
    def __init__(self, driver):
        self.driver = driver

    def enrich_graph(self, enriched_profiles: List[Dict[str, Any]]) -> Dict[str, int]:
        """Ingests enriched experience data into Neo4j."""
        if not self.driver: 
            return {"candidates": 0, "decisions": 0, "struggles": 0, "lps": 0}
            
        logger.info(f"Ingesting {len(enriched_profiles)} EACR profiles into Neo4j...")
        
        counts = {
            "candidates": 0,
            "decisions": 0, 
            "struggles": 0, 
            "lps": 0,
            "has_skill": 0,
            "triggered_transition": 0
        }
        
        try:
            with self.driver.session() as session:
                for p in enriched_profiles:
                    uid = str(p.get("user_id", "unknown"))
                    
                    # STEP 1 — Candidate
                    reach_score = p.get("reachability", {}).get("reachability_score", 0.0)
                    session.run("""
                        MERGE (c:Candidate {user_id: $uid})
                        SET c.reachability_score = $score
                    """, uid=uid, score=reach_score)
                    counts["candidates"] += 1
                    
                    # STEP 2 — Skills
                    skills = p.get("core_profile", {}).get("skills", [])
                    for s in skills:
                        s_name = s.get("name", "unknown").lower()
                        s_weight = float(s.get("weight", 0.0))
                        session.run("""
                            MERGE (sk:Skill {name: $name})
                            WITH sk
                            MATCH (c:Candidate {user_id: $uid})
                            MERGE (c)-[r:HAS_SKILL]->(sk)
                            SET r.weight = $weight
                        """, name=s_name, uid=uid, weight=s_weight)
                        counts["has_skill"] += 1
                        
                    # STEP 3 — Current Role
                    curr_state = p.get("trajectory", {}).get("current_state", "unknown")
                    session.run("""
                        MERGE (j:Job {role: $role})
                        WITH j
                        MATCH (c:Candidate {user_id: $uid})
                        MERGE (c)-[:CURRENT_ROLE]->(j)
                    """, role=curr_state, uid=uid)
                    
                    # STEP 4 — Decisions
                    decisions = p.get("experience_model", {}).get("decision_points", [])
                    for idx, d in enumerate(decisions):
                        d_id = f"dec_{uid}_{idx}"
                        d_text = d.get("decision", "")
                        trigger = d.get("trigger", "")
                        conf = float(d.get("confidence", 0.0))
                        sources = d.get("inferred_from", [])
                        
                        session.run("""
                            MERGE (dec:Decision {id: $d_id})
                            SET dec.text = $text,
                                dec.trigger = $trigger,
                                dec.confidence = $conf,
                                dec.synthetic = true
                            WITH dec
                            MATCH (c:Candidate {user_id: $uid})
                            MERGE (c)-[:MADE_DECISION {
                                confidence: $conf,
                                inferred_from: $sources
                            }]->(dec)
                        """, d_id=d_id, text=d_text, trigger=trigger, conf=conf, uid=uid, sources=sources)
                        counts["decisions"] += 1
                        
                        # STEP 8 — Transitions (Linked to Decisions)
                        transitions = p.get("trajectory", {}).get("inferred_transitions", [])
                        for t in transitions:
                            from_role = t.get("from_role", "unknown")
                            to_role = t.get("to_role", "unknown")
                            
                            session.run("""
                                MERGE (j:Job {role: $to_role})
                                WITH j
                                MATCH (dec:Decision {id: $d_id})
                                MERGE (dec)-[:TRIGGERED_TRANSITION {
                                    from_role: $from_role,
                                    to_role: $to_role
                                }]->(j)
                            """, to_role=to_role, d_id=d_id, from_role=from_role)
                            counts["triggered_transition"] += 1

                    # STEP 5 — Struggles
                    struggles = p.get("experience_model", {}).get("struggles", [])
                    for idx, s in enumerate(struggles):
                        s_id = f"str_{uid}_{idx}"
                        s_text = s.get("struggle", "")
                        domain = s.get("domain", "general").lower()
                        resolved = bool(s.get("resolved", False))
                        
                        session.run("""
                            MERGE (str:Struggle {id: $s_id})
                            SET str.text = $text,
                                str.domain = $domain,
                                str.resolved = $resolved,
                                str.synthetic = true
                            WITH str
                            MATCH (c:Candidate {user_id: $uid})
                            MERGE (c)-[:FACED {resolved: $resolved}]->(str)
                            WITH str
                            MERGE (dom:Domain {name: $domain})
                            MERGE (str)-[:IN_DOMAIN]->(dom)
                        """, s_id=s_id, text=s_text, domain=domain, resolved=resolved, uid=uid)
                        counts["struggles"] += 1
                        
                    # STEP 6 — Learning Patterns
                    lps = p.get("experience_model", {}).get("learning_patterns", [])
                    for idx, lp in enumerate(lps):
                        lp_id = f"lp_{uid}_{idx}"
                        lp_text = lp.get("text", "")
                        skill_src = lp.get("skill_source", "unknown")
                        themes = ",".join(lp.get("themes", []))
                        
                        session.run("""
                            MERGE (l:LearningPattern {id: $lp_id})
                            SET l.text = $text,
                                l.skill_source = $skill,
                                l.themes = $themes,
                                l.synthetic = true
                            WITH l
                            MATCH (c:Candidate {user_id: $uid})
                            MERGE (c)-[:LEARNED_VIA]->(l)
                        """, lp_id=lp_id, text=lp_text, skill=skill_src, themes=themes, uid=uid)
                        counts["lps"] += 1
                        
                        # STEP 7 — Chroma Linking
                        inf_from = lp.get("inferred_from", [])
                        for source in inf_from:
                            if source.startswith("chroma:"):
                                chunk_id = source.replace("chroma:", "")
                                session.run("""
                                    MERGE (cr:ChromaRef {chunk_id: $chunk_id})
                                    SET cr.collection = "medium_chunks"
                                    WITH cr
                                    MATCH (l:LearningPattern {id: $lp_id})
                                    MERGE (l)-[:SEEDED_BY]->(cr)
                                """, chunk_id=chunk_id, lp_id=lp_id)

                    logger.info(f"[{uid}] decisions:{len(decisions)} struggles:{len(struggles)} learning_patterns:{len(lps)} transitions:{len(transitions)}")
            
            logger.info("Deterministic Neo4j ingestion complete.")
        except Exception as e:
            logger.error(f"Graph Ingestion Failed: {e}")
            raise
            
        return counts
