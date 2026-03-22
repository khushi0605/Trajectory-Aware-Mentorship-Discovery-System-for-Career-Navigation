import json
import logging
from pathlib import Path
from typing import Dict, List, Set, Any, Tuple
import glob
import re

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("profile_job_matcher")

class ProfileJobMatcher:
    def __init__(self, 
                 profiles_path: str = "data/processed/unified/enriched_profiles.json",
                 jobs_dir: str = "data/processed/job_req_profiles",
                 taxonomy_path: str = "data/reference/skill_taxonomy.json",
                 output_path: str = "data/processed/matches/profile_job_matches.json"):
        
        self.profiles_path = Path(profiles_path)
        self.jobs_dir = Path(jobs_dir)
        self.taxonomy_path = Path(taxonomy_path)
        self.output_path = Path(output_path)
        
        self.profiles = []
        self.jobs = []
        self.taxonomy = {}
        self.skill_to_canonical = {}

    def load_taxonomy(self):
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
                        self.taxonomy = default_taxonomy
            except Exception:
                self.taxonomy = default_taxonomy
        else:
            self.taxonomy = default_taxonomy
            
        for canonical, skills in self.taxonomy.items():
            for skill in skills:
                self.skill_to_canonical[self.clean_skill(skill)] = canonical

    def load_profiles(self):
        # Handle fallback if the file is an array of files, but here it's likely a single file array
        # Checking multiple potential locations
        possible_paths = [
            self.profiles_path,
            Path("data/processed/unified_profiles/_all_unified.json")
        ]
        
        for p in possible_paths:
            if p.exists():
                logger.info(f"Loading profiles from {p}")
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.profiles = data
                    elif isinstance(data, dict) and "profiles" in data:
                        self.profiles = data["profiles"]
                break
                
        logger.info(f"Loaded {len(self.profiles)} enriched profiles.")

    def load_jobs(self):
        if not self.jobs_dir.exists():
            single_file = Path(str(self.jobs_dir) + ".json")
            if single_file.exists():
                with open(single_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        self.jobs = data
                        logger.info(f"Loaded {len(self.jobs)} jobs from single file.")
                        return
                        
        job_files = glob.glob(str(self.jobs_dir / "*.json"))
        for jf in job_files:
            if Path(jf).name.startswith("_"):
                continue
            with open(jf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict) and "role" in data:
                    self.jobs.append(data)
                elif isinstance(data, list):
                    self.jobs.extend(data)
                    
        logger.info(f"Loaded {len(self.jobs)} job requirements.")

    def clean_skill(self, skill: str) -> str:
        """Lowercases, strips spaces, replaces internal spaces/dashes with underscores, removes special chars."""
        if not isinstance(skill, str):
            return ""
        s = skill.lower().strip()
        s = re.sub(r'[^a-z0-9\s_.-]', '', s)
        s = re.sub(r'[\s.-]+', '_', s)
        s = s.strip('_')
        return s

    def map_to_canonical(self, skill: str) -> str:
        """Map to canonical if exists, else fallback to cleaned raw skill."""
        cleaned = self.clean_skill(skill)
        if not cleaned:
            return ""
        return self.skill_to_canonical.get(cleaned, cleaned)

    def normalize_skills(self, skills) -> Tuple[Set[str], Set[str]]:
        raw_set = set()
        can_set = set()
        
        if isinstance(skills, dict):
            # Enriched profiles usually have dict of skills {name: weight}
            skills_iter = skills.keys()
        elif isinstance(skills, list):
            skills_iter = skills
        else:
            return raw_set, can_set
            
        for skill in skills_iter:
            cleaned = self.clean_skill(skill)
            if cleaned:
                raw_set.add(cleaned)
                can_set.add(self.map_to_canonical(cleaned))
                
        return raw_set, can_set

    def infer_domain(self, canonical_skills: Set[str], role_name: str = "") -> Set[str]:
        domains = set()
        
        # Infer from skills
        for skill in canonical_skills:
            if skill in self.taxonomy:
                domains.add(skill)
            elif skill in self.skill_to_canonical.values():
                domains.add(skill)
                
        # Infer from role name if available
        if role_name:
            role_clean = self.clean_skill(role_name)
            for dom, skills in self.taxonomy.items():
                if dom in role_clean: 
                    domains.add(dom)
                for s in skills:
                    if s in role_clean:
                        domains.add(dom)
                        
        return domains

    def compute_skill_score(self, 
                            prof_raw: Set[str], prof_can: Set[str], 
                            job_raw: Set[str], job_can: Set[str]) -> Tuple[float, Set[str]]:
        if not job_can and not job_raw:
            return 0.0, set()
            
        overlap_can = prof_can.intersection(job_can)
        if overlap_can:
            return len(overlap_can) / max(len(job_can), 1), overlap_can
            
        overlap_raw = prof_raw.intersection(job_raw)
        if overlap_raw:
            return (len(overlap_raw) / max(len(job_raw), 1)) * 0.8, overlap_raw
            
        return 0.0, set()

    def compute_level_score(self, prof_stage: str, job_levels: List[str]) -> float:
        if not prof_stage or not job_levels:
            return 0.0
            
        estage = prof_stage.lower()
        job_levels_lower = [lvl.lower() for lvl in job_levels]
        
        if estage in job_levels_lower:
            return 1.0 # Full weight exact match
            
        mapping = {
            "beginner": ["fresher", "intern", "junior", "entry", "entry_level"],
            "fresher": ["beginner", "intern", "junior", "entry", "entry_level"],
            "intern": ["fresher", "beginner", "junior", "entry", "entry_level"],
            "junior": ["beginner", "fresher", "intern", "entry", "entry_level"],
            "intermediate": ["experienced", "mid", "associate", "intermediate"],
            "senior": ["experienced", "lead", "principal", "architect", "advanced"],
            "advanced": ["experienced", "senior", "lead", "principal", "architect"],
            "expert": ["experienced", "senior", "lead", "principal", "architect"]
        }
        
        for target in mapping.get(estage, []):
            if any(target in rl for rl in job_levels_lower):
                return 1.0
                
        # Partial mappings
        if (estage in ["intermediate", "mid"] and any("senior" in j for j in job_levels_lower)) or \
           (estage in ["advanced", "senior"] and any("intermediate" in j for j in job_levels_lower)):
            return 0.5
            
        if (estage in ["beginner", "junior"] and any("intermediate" in j for j in job_levels_lower)):
            return 0.2
            
        return 0.0

    def match_profiles_to_jobs(self):
        output_data = []
        logs_printed = 0
        
        for job in self.jobs:
            role_name = job.get("role", "unknown_role")
            raw_req_skills = job.get("required_skills", [])
            job_levels = job.get("experience_levels", [])
            
            j_raw, j_can = self.normalize_skills(raw_req_skills)
            job_domains = self.infer_domain(j_can, role_name)
            
            if not j_can and not j_raw:
                continue
                
            matched_profiles = []
            all_matched_skills = set()
            
            for prof in self.profiles:
                user_id = prof.get("user_id", prof.get("username", prof.get("id", "unknown")))
                prof_skills = prof.get("skills", {})
                
                # Resumes or unified profiles might have projects/tools. Let's extract all skills
                if not prof_skills and "projects" in prof:
                    skills_list = []
                    for prj in prof.get("projects", []):
                        skills_list.extend(prj.get("tools", []))
                    prof_skills = skills_list
                
                p_raw, p_can = self.normalize_skills(prof_skills)
                prof_domains = self.infer_domain(p_can)
                
                # Check Domain overlap
                domain_overlap = prof_domains.intersection(job_domains)
                # Apply domain filtering: skip entirely if domains do not overlap 
                # (unless both are completely unclassified, then we pass through)
                if job_domains and prof_domains and not domain_overlap:
                    continue
                    
                domain_score = 1.0 if domain_overlap else 0.0
                
                # Skill checking
                skill_score, overlap_set = self.compute_skill_score(p_raw, p_can, j_raw, j_can)
                
                # Diagnostic Logging for first 3 evaluated instances
                if logs_printed < 3 and overlap_set:
                    logger.info("--- DIAGNOSTIC TRACE ---")
                    logger.info(f"Job Role: {role_name}")
                    logger.info(f"Job Reqs Canonical: {j_can}")
                    logger.info(f"Profile User ID: {user_id}")
                    logger.info(f"Profile Raw Skills: {p_raw}")
                    logger.info(f"Profile Canonical: {p_can}")
                    logger.info(f"Computed Domain Overlap: {domain_overlap} (Score: {domain_score})")
                    logger.info(f"Computed Skill Overlap: {overlap_set} (Score: {skill_score:.2f})")
                    logger.info("------------------------")
                    logs_printed += 1
                
                prof_level = prof.get("experience_level", prof.get("career_stage", ""))
                level_score = self.compute_level_score(prof_level, job_levels)
                
                # final_score = 0.7 * skill_score + 0.2 * level_score + 0.1 * domain_score
                final_score = (0.7 * skill_score) + (0.2 * level_score) + (0.1 * domain_score)
                
                # If they have meaningul skills or perfect level + domain, include them
                # Since role requires skill specifically, let's say skill_score must be > 0
                if skill_score > 0 and final_score >= 0.2:
                    matched_profiles.append({
                        "user_id": user_id,
                        "match_score": round(final_score, 4),
                        "matched_skills": list(overlap_set),
                        "missing_skills": list(j_can - overlap_set),
                        "experience_level_score": level_score,
                        "domain_score": domain_score,
                        "overall_score": round(final_score, 4)
                    })
                    all_matched_skills.update(overlap_set)
                    
            # Identify missing skills for the job across ALL matched candidates
            total_missing = list(j_can - all_matched_skills)
            
            # Sort desc
            matched_profiles = sorted(matched_profiles, key=lambda x: x["match_score"], reverse=True)
            
            readiness = 0.0
            if matched_profiles:
                top_5 = matched_profiles[:5]
                readiness = sum(m["match_score"] for m in top_5) / len(top_5)
                
            output_data.append({
                "role": role_name,
                "role_readiness_score": round(readiness, 4),
                "matched_profiles": matched_profiles,
                "missing_skills": total_missing
            })
            
        return output_data

    def process_and_save(self):
        logger.info("Initializing Profile ↔ Job Matcher Pipeline...")
        self.load_taxonomy()
        self.load_profiles()
        self.load_jobs()
        
        matches = self.match_profiles_to_jobs()
        
        logger.info(f"Ensuring output directory exists: {self.output_path.parent}")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(matches, f, indent=2, ensure_ascii=False)
            
        total_jobs = len(matches)
        total_profs = len(self.profiles)
        avg_matches = sum(len(m["matched_profiles"]) for m in matches) / max(total_jobs, 1)
        
        logger.info(f"=== Profile Matching Summary ===")
        logger.info(f"Total Jobs Analyzed: {total_jobs}")
        logger.info(f"Total Profiles Evaluated: {total_profs}")
        logger.info(f"Average Profile Matches per Job: {avg_matches:.2f}")
        
        if matches:
            sorted_by_coverage = sorted(matches, key=lambda x: len(x["matched_profiles"]), reverse=True)
            logger.info(f"Highest Applicant Job: {sorted_by_coverage[0]['role']} ({len(sorted_by_coverage[0]['matched_profiles'])} matches)")
            logger.info(f"Lowest Applicant Job: {sorted_by_coverage[-1]['role']} ({len(sorted_by_coverage[-1]['matched_profiles'])} matches)")
            
        logger.info(f"Successfully saved Profile to Job Matches to {self.output_path}")

if __name__ == "__main__":
    matcher = ProfileJobMatcher()
    matcher.process_and_save()
