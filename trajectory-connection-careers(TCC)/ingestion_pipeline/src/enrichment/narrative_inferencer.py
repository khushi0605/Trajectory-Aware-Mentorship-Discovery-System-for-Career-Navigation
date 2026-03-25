import os
import json
import logging
from typing import Dict, Any, List

logger = logging.getLogger("narrative_inferencer")

class NarrativeInferencer:
    """
    Deterministically infers candidate behavioral signals (learning patterns, decisions, struggles)
    from 3 strict sources in priority order: Neo4j (Graph), ChromaDB (Vector semantics), and
    Heuristics (regex).
    """
    def __init__(self, neo4j_driver, chroma_collection, domain_map: Dict[str, str]):
        self.driver = neo4j_driver
        self.chroma_collection = chroma_collection
        self.domain_map = domain_map
        
        if self.driver:
            with self.driver.session() as session:
                result = session.run("MATCH ()-[r:MATCHES_JOB]->() RETURN count(r) AS total LIMIT 1")
                total = result.single()["total"]
                
                if total == 0:
                    logger.error("MATCHES_JOB edges missing from graph — run profile_job_matcher.py first")
                    raise RuntimeError("MATCHES_JOB edges missing from graph")

    def _deduplicate_by_text(self, items: list, text_key: str) -> list:
        seen = set()
        result = []
        for item in items:
            val = item.get(text_key, "")
            if val not in seen:
                result.append(item)
                seen.add(val)
        return result

    def infer_candidate(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the deterministic inference cascade on a single Candidate."""
        uid = candidate.get("user_id")
        
        # Base structures to populate
        res = {
            "decisions": [],
            "struggles": [],
            "learning_patterns": [],
            "inferred_transitions": [],
            "stats": {"neo4j_dec": 0, "chroma_dec": 0, "heur_dec": 0,
                      "neo4j_str": 0, "heur_str": 0,
                      "chroma_lp": 0, "heur_lp": 0}
        }
        
        self._infer_neo4j(uid, candidate, res)
        self._infer_chroma(candidate, res)
        self._infer_heuristics(candidate, res)
        
        # Global Dedup before writing to profile
        res["decisions"] = self._deduplicate_by_text(res["decisions"], "decision")
        res["struggles"] = self._deduplicate_by_text(res["struggles"], "struggle")
        res["learning_patterns"] = self._deduplicate_by_text(res["learning_patterns"], "text")
        
        # Assemble narratives
        assembled_narratives = self._assemble_narratives(uid, candidate, res)
        
        # Inject into output payload structure
        candidate["trajectory"]["inferred_transitions"] = res["inferred_transitions"]
        candidate["experience_model"]["decision_points"] = res["decisions"]
        candidate["experience_model"]["struggles"] = res["struggles"]
        candidate["experience_model"]["learning_patterns"] = res["learning_patterns"]
        candidate["narratives"] = assembled_narratives
        candidate["_stats"] = res["stats"]
        return candidate

    def _infer_neo4j(self, uid: str, candidate: Dict[str, Any], res: Dict[str, Any]):
        """Source 1: Ground truth graph traversal resolving decisions/struggles via matches."""
        if not self.driver: return

        try:
            with self.driver.session() as session:
                # Query B: MATCHES_JOB
                query_b = """
                MATCH (c:Candidate {user_id: $uid})-[m:MATCHES_JOB]->(j:Job)
                RETURN j.role AS title, m.score AS score
                ORDER BY m.score DESC LIMIT 5
                """
                matches = session.run(query_b, uid=uid).data()
                
                if not matches:
                    logger.warning(f"[{uid}] No MATCHES_JOB edges found — transition_probabilities will be empty")
                
                curr_state = candidate.get("trajectory", {}).get("current_state", "unknown")
                start_state = candidate.get("trajectory", {}).get("start_state", "unknown")
                obs_paths = candidate.get("trajectory", {}).get("observed_paths", [])

                for match in matches:
                    res["inferred_transitions"].append({
                        "from_role": curr_state,
                        "to_role": match['title']
                    })
                
                # Decision Rule 1: High job match score + observed path history
                if len(obs_paths) >= 2 and matches and matches[0]['score'] > 70:
                    title = matches[0]['title']
                    d_name = candidate.get("core_profile", {}).get("domains", ["general"])[0]
                    res["decisions"].append({
                        "decision": f"Pursued {title} from {start_state} background",
                        "trigger": f"Strong skill alignment in {d_name}",
                        "confidence": round(matches[0]['score'] / 100.0, 2),
                        "synthetic": True,
                        "inferred_from": ["neo4j:MATCHES_JOB"]
                    })
                    res["stats"]["neo4j_dec"] += 1

                # Query A: Top skills
                query_a = """
                MATCH (c:Candidate {user_id: $uid})-[r:HAS_SKILL]->(s:Skill)
                RETURN s.name AS name, r.proficiency AS weight
                ORDER BY r.proficiency DESC LIMIT 5
                """
                skills = session.run(query_a, uid=uid).data()
                
                if skills and skills[0]['weight'] > 0.12:
                    top_skill = skills[0]['name']
                    
                    projects = candidate.get("core_profile", {}).get("projects", [])
                    skill_projects = [
                        p.get("name")
                        for p in projects
                        if top_skill in p.get("skills", [])
                    ][:3]

                    if skill_projects:
                        project_str = ", ".join(skill_projects)
                        trigger = f"High project concentration in {top_skill} across {project_str}"
                    else:
                        trigger = f"High project concentration in {top_skill}"

                    res["decisions"].append({
                        "decision": f"Specialized deeply in {top_skill}",
                        "trigger": trigger,
                        "confidence": 0.75,
                        "synthetic": True,
                        "inferred_from": ["neo4j:HAS_SKILL"]
                    })
                    res["stats"]["neo4j_dec"] += 1

                # Struggle Rule 1: High project count but low weight
                all_raw_skills = candidate.get("core_profile", {}).get("skills", [])
                skill_weights = {s["name"]: s["weight"] for s in all_raw_skills}
                
                projects = candidate.get("core_profile", {}).get("projects", [])
                skill_proj_counts = {}
                for p in projects:
                    for s in p.get("skills", []):
                        skill_proj_counts[s] = skill_proj_counts.get(s, 0) + 1
                        
                for sk, cnt in skill_proj_counts.items():
                    if cnt >= 3 and skill_weights.get(sk, 0) < 0.06:
                        domain = self.domain_map.get(sk, "general")
                        res["struggles"].append({
                            "struggle": f"Difficulty consolidating {sk} despite repeated use",
                            "domain": domain,
                            "resolved": False,
                            "synthetic": True,
                            "inferred_from": [f"neo4j:SKILL_PENALTY_{sk}"]
                        })
                        res["stats"]["neo4j_str"] += 1
                        
                # Struggle Rule 2: High path length
                if len(obs_paths) >= 3:
                    resolved = obs_paths[-1] != obs_paths[0]
                    res["struggles"].append({
                        "struggle": f"Navigating role ambiguity across {len(obs_paths)} career states",
                        "domain": "career_trajectory",
                        "resolved": resolved,
                        "synthetic": True,
                        "inferred_from": ["neo4j:TRAJECTORY_LENGTH"]
                    })
                    res["stats"]["neo4j_str"] += 1

        except Exception as e:
            logger.error(f"Neo4j inference failed for {uid}: {e}")

    def _infer_chroma(self, candidate: Dict[str, Any], res: Dict[str, Any]):
        """Source 2: Vector embedding intersection for behavioral learning actions."""
        if not self.chroma_collection: return
        
        all_skills = sorted(candidate.get("core_profile", {}).get("skills", []), key=lambda x: x.get("weight", 0), reverse=True)
        top_skills = [s["name"] for s in all_skills[:3]]
        
        if not top_skills: return
        
        query = " ".join(top_skills)
        try:
            c_res = self.chroma_collection.query(query_texts=[query], n_results=2)
            if not c_res or not c_res.get("ids") or len(c_res["ids"][0]) == 0:
                return
                
            seen_chunk_ids = set()
            for idx in range(len(c_res["ids"][0])):
                chunk_id = c_res["ids"][0][idx]
                if chunk_id in seen_chunk_ids:
                    continue
                seen_chunk_ids.add(chunk_id)
                
                doc = c_res["documents"][0][idx].lower()
                meta = c_res["metadatas"][0][idx] if c_res.get("metadatas") else {}
                
                # Extract learning themes & verbs robustly
                verbs_found = [v for v in ["built", "explored", "transitioned", "struggled", "shipped"] if v in doc]
                verb = verbs_found[0] if verbs_found else "worked on"
                
                themes = meta.get("themes", [])
                if isinstance(themes, str): 
                    try:
                        themes = json.loads(themes)
                    except:
                        themes = []
                        
                skill_source = top_skills[0]
                skill_cluster = f"{skill_source}-related architecture"
                project_type = "core projects"
                verb_cap = verb.capitalize()
                
                projects = candidate.get("core_profile", {}).get("projects", [])
                anchored_projects = [
                    p.get("name")
                    for p in projects
                    if skill_source in p.get("skills", [])
                ][:2]
                
                if anchored_projects:
                    project_str = " and ".join(anchored_projects)
                    learning_action = f"{verb_cap} {skill_cluster} via {project_str}"
                else:
                    learning_action = f"{verb_cap} {skill_cluster} through {project_type}"
                        
                res["learning_patterns"].append({
                    "text": learning_action,
                    "skill_source": skill_source,
                    "themes": themes,
                    "synthetic": True,
                    "inferred_from": [f"chroma:{chunk_id}"]
                })
                res["stats"]["chroma_lp"] += 1
        except Exception as e:
            logger.error(f"Chroma inference failed for {candidate.get('user_id')}: {e}")

    def _infer_heuristics(self, candidate: Dict[str, Any], res: Dict[str, Any]):
        """Source 3: Deterministic regex/word-map fallbacks when graphs and vectors lack density."""
        projects = candidate.get("core_profile", {}).get("projects", [])
        fired_rules = set()
        
        # Project heuristics
        for p in projects:
            p_name = p.get("name", "").lower()
            
            rule_name = "heuristic:http_server"
            if any(k in p_name for k in ["http", "server", "web", "kama"]) and rule_name not in fired_rules:
                res["learning_patterns"].append({
                    "text": "Built HTTP server infrastructure",
                    "skill_source": "system_design",
                    "themes": ["backend", "networking"],
                    "synthetic": True,
                    "inferred_from": [rule_name]
                })
                res["stats"]["heur_lp"] += 1
                fired_rules.add(rule_name)
                
            rule_name = "heuristic:storage_systems"
            if any(k in p_name for k in ["cache", "storage", "kv"]) and rule_name not in fired_rules:
                res["decisions"].append({
                    "decision": "Interest in distributed storage systems",
                    "trigger": "Heuristic project regex match",
                    "confidence": 0.5,
                    "synthetic": True,
                    "inferred_from": [rule_name]
                })
                res["stats"]["heur_dec"] += 1
                fired_rules.add(rule_name)
                
            rule_name = "heuristic:ds_algo"
            if any(k in p_name for k in ["leetcode", "algorithm", "skip"]) and rule_name not in fired_rules:
                res["struggles"].append({
                    "struggle": "Competitive interview preparation",
                    "domain": "algorithms",
                    "resolved": True,
                    "synthetic": True,
                    "inferred_from": [rule_name]
                })
                res["stats"]["heur_str"] += 1
                fired_rules.add(rule_name)
                
            rule_name = "heuristic:systems_prog"
            if any(k in p_name for k in ["rpc", "coroutine", "muduo"]) and rule_name not in fired_rules:
                res["decisions"].append({
                    "decision": "Deep systems programming specialization",
                    "trigger": "Low level library implementations",
                    "confidence": 0.6,
                    "synthetic": True,
                    "inferred_from": [rule_name]
                })
                res["stats"]["heur_dec"] += 1
                fired_rules.add(rule_name)

        # Skill distribution heuristics
        skills = candidate.get("core_profile", {}).get("skills", [])
        weights = [s["weight"] for s in skills]
        if weights:
            mean = sum(weights) / len(weights)
            diffs = sum(abs(xi - xj) for xi in weights for xj in weights)
            gini = diffs / (2 * len(weights)**2 * mean) if mean > 0 else 0
            
            rule_name = "heuristic:gini_specialist"
            if gini > 0.45 and rule_name not in fired_rules:
                res["decisions"].append({
                    "decision": "Chose to specialize narrowly",
                    "trigger": f"High GINI coefficient ({round(gini, 2)})",
                    "confidence": 0.65,
                    "synthetic": True,
                    "inferred_from": [rule_name]
                })
                res["stats"]["heur_dec"] += 1
                fired_rules.add(rule_name)
                
            rule_name = "heuristic:gini_generalist"
            if gini < 0.20 and rule_name not in fired_rules:
                res["decisions"].append({
                    "decision": "Maintained broad polyglot skill base",
                    "trigger": f"Low GINI coefficient ({round(gini, 2)})",
                    "confidence": 0.60,
                    "synthetic": True,
                    "inferred_from": [rule_name]
                })
                res["stats"]["heur_dec"] += 1
                fired_rules.add(rule_name)

        lang_set = set()
        for p in projects:
            lang_set.update(p.get("skills", []))
        rule_name = "heuristic:polyglot_languages"
        if len(lang_set) >= 4 and rule_name not in fired_rules:
            res["learning_patterns"].append({
                "text": "Explored multiple programming paradigms",
                "skill_source": "polyglot",
                "themes": ["diverse_tech_stack"],
                "synthetic": True,
                "inferred_from": [rule_name]
            })
            res["stats"]["heur_lp"] += 1
            fired_rules.add(rule_name)
            
    def _assemble_narratives(self, uid: str, candidate: Dict[str, Any], res: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Wraps up inferences into the final cohesive JSON shell (Max 2 narratives)."""
        curr_state = candidate.get("trajectory", {}).get("current_state", "unknown role")
        final_narratives = []
        
        # Narrative 0: Highest-confidence decision + first struggle
        decision = res["decisions"][0]["decision"] if res["decisions"] else "Standard career progression"
        struggle = res["struggles"][0]["struggle"] if res["struggles"] else ""
        learning = res["learning_patterns"][0]["text"] if res["learning_patterns"] else "Self-taught through project implementation"
        
        all_inf_0 = []
        for src in [res["decisions"][:1], res["struggles"][:1], res["learning_patterns"][:1]]:
            if src and "inferred_from" in src[0]:
                all_inf_0.extend(src[0]["inferred_from"])
        all_inf_0 = list(set(all_inf_0))
        
        themes_0 = candidate.get("core_profile", {}).get("domains", [])
        chr_ids_0 = [x.split(":")[1] for x in all_inf_0 if x.startswith("chroma:")]
        
        final_narratives.append({
            "id": f"narr_{uid}_0",
            "decision": decision,
            "struggle": struggle,
            "learning_action": learning,
            "outcome": f"Transitioned to {curr_state}",
            "themes": list(set(themes_0)),
            "chroma_source_ids": chr_ids_0,
            "synthetic": True,
            "inferred_from": all_inf_0
        })
        
        # Narrative 1: Driven by top ChromaDB theme seed (if chroma fired)
        chroma_lps = [lp for lp in res["learning_patterns"] if any("chroma:" in inf for inf in lp.get("inferred_from", []))]
        if chroma_lps:
            clp = chroma_lps[0]
            inf_1 = clp.get("inferred_from", [])
            themes_1 = clp.get("themes", [])
            chr_ids_1 = [x.split(":")[1] for x in inf_1 if x.startswith("chroma:")]
            
            final_narratives.append({
                "id": f"narr_{uid}_1",
                "decision": "Applied localized domain knowledge",
                "struggle": "",
                "learning_action": clp["text"],
                "outcome": f"Integrated {clp.get('skill_source', 'tools')} into workflow",
                "themes": list(set(themes_1)),
                "chroma_source_ids": chr_ids_1,
                "synthetic": True,
                "inferred_from": inf_1
            })
            
        return final_narratives
