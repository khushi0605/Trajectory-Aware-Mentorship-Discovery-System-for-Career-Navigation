import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple
import glob
import os
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("experience_matcher")

class ExperienceRoleMatcher:
    def __init__(self, 
                 experiences_path: str = "data/processed/experiences/medium_narratives.json",
                 roles_dir: str = "data/processed/job_req_profiles",
                 taxonomy_path: str = "data/reference/skill_taxonomy.json",
                 output_path: str = "data/processed/matches/experience_role_matched.json"):
        
        self.experiences_path = Path(experiences_path)
        self.roles_dir = Path(roles_dir)
        self.taxonomy_path = Path(taxonomy_path)
        self.output_path = Path(output_path)
        
        self.experiences = []
        self.roles = []
        self.taxonomy = {}
        # reverse mapping: low_level -> canonical
        self.skill_to_canonical = {}

    def load_taxonomy(self):
        # Fallback taxonomy if the exact file is missing or flat
        default_taxonomy = {
            "mobile_development": ["android_sdk", "kotlin", "jetpack", "android_studio", "ios", "swift", "flutter", "react_native", "mobile_dev", "android", "mobile"],
            "machine_learning": ["pytorch", "tensorflow", "nlp", "machine_learning", "deep_learning", "computer_vision", "scikit_learn", "keras", "xgboost", "gradient_descent"],
            "backend_development": ["python", "java", "sql", "node", "nodejs", "django", "flask", "spring", "backend", "go", "ruby", "csharp", "api", "rest_api", "microservices"],
            "frontend_development": ["react", "angular", "vue", "javascript", "typescript", "html", "css", "frontend", "ui_ux"],
            "data_science": ["pandas", "numpy", "statistics", "data_science", "data_analysis", "visualization", "matplotlib"],
            "devops": ["docker", "kubernetes", "aws", "gcp", "azure", "ci_cd", "terraform", "devops", "cloud", "jenkins", "git"],
            "cybersecurity": ["security", "cybersecurity", "ethical_hacking", "penetration_testing", "soc", "incident_response"]
        }
        
        if self.taxonomy_path.exists():
            try:
                with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.taxonomy = data
                    else:
                        logger.warning("Taxonomy file is not a dictionary. Using default mapping.")
                        self.taxonomy = default_taxonomy
            except Exception as e:
                logger.error(f"Error loading taxonomy: {e}. Using default.")
                self.taxonomy = default_taxonomy
        else:
            logger.info("Taxonomy file not found. Using default mapping.")
            self.taxonomy = default_taxonomy
            
        # Build reverse map
        for canonical, skills in self.taxonomy.items():
            for skill in skills:
                self.skill_to_canonical[self.clean_skill(skill)] = canonical

    def load_experiences(self):
        if not self.experiences_path.exists():
            logger.error(f"Experiences file not found: {self.experiences_path}")
            return
        with open(self.experiences_path, 'r', encoding='utf-8') as f:
            self.experiences = json.load(f)
        logger.info(f"Loaded {len(self.experiences)} experiences.")

    def load_roles(self):
        if not self.roles_dir.exists():
            single_file = Path(str(self.roles_dir) + ".json")
            if single_file.exists():
                with open(single_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.roles = data
                        logger.info(f"Loaded {len(self.roles)} roles from single file.")
                        return
                        
            logger.error(f"Roles directory/file not found: {self.roles_dir}")
            return
            
        role_files = glob.glob(str(self.roles_dir / "*.json"))
        for rf in role_files:
            if Path(rf).name.startswith("_"):
                continue
            with open(rf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "role" in data:
                    self.roles.append(data)
                elif isinstance(data, list):
                    self.roles.extend(data)
                    
        logger.info(f"Loaded {len(self.roles)} roles from individual profiles.")

    def clean_skill(self, skill: str) -> str:
        """Robust normalization: lowercases, strips spaces, removes special chars, replaces spaces with underscores."""
        if not isinstance(skill, str):
            return ""
        s = skill.lower().strip()
        s = re.sub(r'[^a-z0-9\s_.-]', '', s)
        s = re.sub(r'[\s.-]+', '_', s)
        s = s.strip('_')
        return s

    def map_to_canonical(self, skill: str) -> str:
        """Safe taxonomy mapping with fallback to the cleaned raw skill."""
        cleaned = self.clean_skill(skill)
        if not cleaned:
            return ""
        return self.skill_to_canonical.get(cleaned, cleaned)

    def normalize_skills(self, skills) -> Tuple[Set[str], Set[str]]:
        """Takes a list or dict of skills, returns (raw_cleaned_set, canonical_set)"""
        raw_set = set()
        canonical_set = set()
        
        skill_list = skills.keys() if isinstance(skills, dict) else skills
            
        for skill in skill_list:
            cleaned = self.clean_skill(skill)
            if cleaned:
                raw_set.add(cleaned)
                canonical_set.add(self.map_to_canonical(cleaned))
                
        return raw_set, canonical_set

    def infer_domain(self, canonical_skills: Set[str]) -> Set[str]:
        """Infers domains based on canonical concepts."""
        domains = set()
        for skill in canonical_skills:
            if skill in self.taxonomy:
                domains.add(skill)
            # also if the taxonomy maps directly
            elif skill in self.skill_to_canonical.values():
                domains.add(skill)
        return domains

    def compute_skill_score(self, 
                            exp_raw: Set[str], exp_can: Set[str], 
                            role_raw: Set[str], role_can: Set[str]) -> Tuple[float, Set[str]]:
        if not role_can and not role_raw:
            return 0.0, set()
            
        # Primary check: Canonical skills overlap
        overlap_can = exp_can.intersection(role_can)
        if overlap_can:
            return len(overlap_can) / max(len(role_can), 1), overlap_can
            
        # Fallback check: Raw skills overlap
        overlap_raw = exp_raw.intersection(role_raw)
        if overlap_raw:
            # penalize slightly for being a non-canonical match
            return (len(overlap_raw) / max(len(role_raw), 1)) * 0.8, overlap_raw
            
        return 0.0, set()

    def compute_theme_score(self, exp_themes: List[str], role_domains: Set[str]) -> float:
        score = 0.0
        for theme in exp_themes:
            theme_clean = self.clean_skill(theme)
            if theme_clean in role_domains:
                score += 0.1
            else:
                if any(theme_clean in rd or rd in theme_clean for rd in role_domains):
                    score += 0.1
        return min(score, 0.2)

    def compute_level_score(self, exp_stage: str, role_levels: List[str]) -> float:
        if not exp_stage or not role_levels:
            return 0.0
            
        estage = exp_stage.lower()
        role_levels_lower = [lvl.lower() for lvl in role_levels]
        
        if estage in role_levels_lower:
            return 0.2
            
        mapping = {
            "beginner": ["fresher", "intern", "junior", "entry"],
            "intermediate": ["experienced", "mid", "associate", "intermediate"],
            "advanced": ["experienced", "senior", "lead", "principal", "architect"]
        }
        
        mapped_targets = mapping.get(estage, [])
        for target in mapped_targets:
            if any(target in rl for rl in role_levels_lower):
                return 0.2
                
        if estage == "intermediate" and "senior" in " ".join(role_levels_lower):
            return 0.1
        if estage == "advanced" and "intermediate" in " ".join(role_levels_lower):
            return 0.1
            
        return 0.0

    def compute_insight_score(self, what_you_learn: str, target_skills: Set[str]) -> float:
        if not what_you_learn:
            return 0.0
        text = self.clean_skill(what_you_learn).replace('_', ' ')
        for r_skill in target_skills:
            clean_skill = r_skill.replace("_", " ")
            if clean_skill and clean_skill in text:
                return 0.1
        return 0.0
        
    def generate_reason(self, overlap: Set[str], insight: Dict) -> str:
        skills_str = ", ".join(list(overlap)[:3])
        if len(overlap) > 3:
            skills_str += " and others"
            
        outcome = insight.get("experience_outcome", "apply relevant technical skills")
        outcome = outcome.replace("ability to", "builds ability to")
        
        if not overlap:
            return f"{outcome.capitalize()}."
            
        return f"Develops required skills like {skills_str} and {outcome.lower()}."
        
    def get_match_strength(self, score: float) -> str:
        if score > 0.75:
            return "strong"
        elif score >= 0.55:
            return "moderate"
        else:
            return "weak"

    def match_experiences_to_roles(self):
        output_data = []
        debug_logged = False
        
        for role in self.roles:
            role_name = role.get("role", "unknown_role")
            raw_req_skills = role.get("required_skills", [])
            role_levels = role.get("experience_levels", [])
            
            r_raw, r_can = self.normalize_skills(raw_req_skills)
            role_domains = self.infer_domain(r_can)
            
            if not r_can and not r_raw:
                continue
                
            role_matches = []
            all_matched_skills = set()
            
            for exp in self.experiences:
                exp_skills = exp.get("skills", {})
                exp_themes = exp.get("themes", [])
                
                e_raw, e_can = self.normalize_skills(exp_skills)
                exp_domains = self.infer_domain(e_can)
                
                # Relaxed Domain Pre-filter: if both have domains and they don't intersect at all, maybe skip
                # But to avoid over-skipping, only skip if domains are totally disjoint AND neither is completely empty.
                if role_domains and exp_domains and not role_domains.intersection(exp_domains):
                    continue
                
                skill_score, overlap_set = self.compute_skill_score(e_raw, e_can, r_raw, r_can)
                
                # Provide a logging trace for the very first matching check for diagnostics
                if not debug_logged:
                    logger.info("--- DEBUG DIAGNOSTIC TRACE ---")
                    logger.info(f"Role: {role_name}")
                    logger.info(f"Role Raw: {r_raw}")
                    logger.info(f"Role Canonical: {r_can}")
                    logger.info(f"Exp ID: {exp.get('narrative_id')}")
                    logger.info(f"Exp Raw: {e_raw}")
                    logger.info(f"Exp Canonical: {e_can}")
                    logger.info(f"Computed Overlap: {overlap_set} | Score: {skill_score:.2f}")
                    logger.info("------------------------------")
                    debug_logged = True
                
                insight = exp.get("experience_insight", {})
                level_score = self.compute_level_score(exp.get("career_stage", ""), role_levels)
                theme_score = self.compute_theme_score(exp_themes, role_domains)
                
                # For insight, check both canonical and raw role targets
                target_skills_for_insight = r_can.union(r_raw)
                insight_score = self.compute_insight_score(insight.get("what_you_learn", ""), target_skills_for_insight)
                
                final_score = (0.7 * skill_score) + (0.15 * level_score) + (0.1 * theme_score) + (0.05 * insight_score)
                
                if final_score >= 0.4:
                    reason = self.generate_reason(overlap_set, insight)
                    strength = self.get_match_strength(final_score)
                    
                    role_matches.append({
                        "narrative_id": exp.get("narrative_id", ""),
                        "match_score": round(final_score, 4),
                        "matched_skills": list(overlap_set),
                        "reason": reason,
                        "match_strength": strength
                    })
                    
                    all_matched_skills.update(overlap_set)
                    
            # Identify missing skills. We compute against canonical requirement, minus matched overlap
            missing_skills = list(r_can - all_matched_skills)
            
            # Sort matches desc
            role_matches = sorted(role_matches, key=lambda x: x["match_score"], reverse=True)
            
            readiness = 0.0
            if role_matches:
                top_5 = role_matches[:5]
                readiness = sum(m["match_score"] for m in top_5) / len(top_5)
                
            output_data.append({
                "role": role_name,
                "role_readiness_score": round(readiness, 4),
                "matched_experiences": role_matches,
                "missing_skills": missing_skills
            })
            
        return output_data

    def process_and_save(self):
        logger.info("Initializing Experience ↔ Role Matcher Pipeline...")
        self.load_taxonomy()
        self.load_experiences()
        self.load_roles()
        
        matches = self.match_experiences_to_roles()
        
        logger.info(f"Ensuring output directory exists: {self.output_path.parent}")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(matches, f, indent=2, ensure_ascii=False)
            
        total_roles = len(matches)
        total_exps = len(self.experiences)
        avg_matches = sum(len(m["matched_experiences"]) for m in matches) / max(total_roles, 1)
        
        logger.info(f"=== Matching Summary ===")
        logger.info(f"Total Roles Analyzed: {total_roles}")
        logger.info(f"Total Experiences: {total_exps}")
        logger.info(f"Average Matches per Role: {avg_matches:.2f}")
        
        if matches:
            sorted_by_coverage = sorted(matches, key=lambda x: len(x["matched_experiences"]), reverse=True)
            logger.info(f"Highest Coverage Role: {sorted_by_coverage[0]['role']} ({len(sorted_by_coverage[0]['matched_experiences'])} matches)")
            logger.info(f"Lowest Coverage Role: {sorted_by_coverage[-1]['role']} ({len(sorted_by_coverage[-1]['matched_experiences'])} matches)")
            
        logger.info(f"Successfully saved Experience to Role Matches to {self.output_path}")

if __name__ == "__main__":
    matcher = ExperienceRoleMatcher()
    matcher.process_and_save()
