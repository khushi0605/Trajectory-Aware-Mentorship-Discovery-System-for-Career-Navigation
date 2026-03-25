import logging
from typing import Dict, List, Any

logger = logging.getLogger("profile_builder")

class EACRBuilder:
    """
    Constructs the final synthetic Experience-Aware Candidate Representation (EACR) schema.
    Merges base data, trajectory paths, ChromaDB narratives, and inferred experience logic.
    """
    def __init__(self):
        pass

    def build_profile(
        self, 
        base_user: Dict[str, Any], 
        trajectory_data: Dict[str, Any], 
        narratives: List[Dict[str, Any]], 
        inferred_exp: Dict[str, Any]
    ) -> Dict[str, Any]:
    
        user_id = base_user.get("user_id", "unknown_user")
        
        # Format skills correctly to output schema
        skills_raw = base_user.get("skills", {})
        if isinstance(skills_raw, dict):
            skills_arr = [{"name": k, "weight": float(v)} for k, v in skills_raw.items()]
        else:
            skills_arr = skills_raw
            
        # Format experience from trajectory
        career_traj = base_user.get("career_trajectory", [])
        exp_arr = [{"role": r, "source": "unified_inference", "description": ""} for r in career_traj]
        
        # Format projects
        projects_raw = base_user.get("projects", [])
        proj_arr = []
        for p in projects_raw:
            proj_arr.append({
                "name": p.get("name", ""),
                "description": p.get("description", p.get("domain", "")),
                "skills": p.get("tools", p.get("technologies", []))
            })

        eacr_payload = {
            "user_id": user_id,
            "core_profile": {
                "skills": skills_arr,
                "domains": base_user.get("domains", []),
                "experience": exp_arr,
                "projects": proj_arr
            },
            "trajectory": {
                "start_state": trajectory_data.get("start_state", career_traj[0] if career_traj else "unknown"),
                "current_state": trajectory_data.get("current_state", career_traj[-1] if career_traj else "unknown"),
                "observed_paths": trajectory_data.get("observed_paths", []),
                "transition_probabilities": trajectory_data.get("transition_probabilities", {})
            },
            "experience_model": {
                "learning_patterns": inferred_exp.get("learning_patterns", []),
                "decision_points": inferred_exp.get("decision_points", []),
                "struggles": inferred_exp.get("struggles", [])
            },
            "narratives": [
                {
                    "id": nav.get("id", str(idx)),
                    "summary": nav.get("summary", ""),
                    "themes": nav.get("themes", [])
                }
                for idx, nav in enumerate(narratives)
            ],
            "reachability": {
                "location": base_user.get("location", "remote"),
                "experience_years": trajectory_data.get("experience_years", len(career_traj) * 2), # Heuristic estimation if missing
                "activity_level": "high" if base_user.get("github_score", 0) > 0 else "medium",
                "source_platforms": [k for k,v in base_user.get("source_weights", {}).items() if v > 0]
            }
        }
        
        return eacr_payload
