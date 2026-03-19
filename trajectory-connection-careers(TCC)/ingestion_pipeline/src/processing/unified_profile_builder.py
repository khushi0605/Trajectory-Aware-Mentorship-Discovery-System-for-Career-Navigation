"""
unified_profile_builder.py
--------------------------
Constructs unified professional identities by combining GitHub and Resume profiles.

This module consumes the output of `profile_matcher.py` and produces realistic
synthetic profiles ready for graph database ingestion and LinkedIn generation.

Outputs two types of profiles:
1. FULL: Merged GitHub (skills, projects) + Resume (trajectory, companies)
   Used when match `use_for_unification` is True.
2. PARTIAL: GitHub only (skills, projects)
   Used when match was weak (preserves skill signal but avoids hallucinated careers).

Usage:
  PYTHONPATH=. python3 src/processing/unified_profile_builder.py
"""

import argparse
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/unified_profile_builder.log", mode="a"),
    ],
)
logger = logging.getLogger("unified_builder")
Path("logs").mkdir(exist_ok=True)


class UnifiedProfileBuilder:
    def __init__(
        self,
        gh_dir: Path,
        resume_dir: Path,
        matches_file: Path,
        output_dir: Path,
    ):
        self.gh_dir = gh_dir
        self.resume_dir = resume_dir
        self.matches_file = matches_file
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory caches for fast lookup
        self.github_data: Dict[str, Dict] = {}
        self.resume_data: Dict[str, Dict] = {}

    def _load_data(self) -> List[Dict]:
        """Load source profiles and match data into memory."""
        logger.info(f"Loading matches from {self.matches_file.name}…")
        with open(self.matches_file, "r", encoding="utf-8") as f:
            matches = json.load(f)

        logger.info("Loading GitHub profiles…")
        for fpath in self.gh_dir.glob("*.json"):
            if fpath.name.startswith("_"):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                gh = json.load(f)
                self.github_data[gh["username"]] = gh

        logger.info("Loading Resume profiles…")
        for fpath in self.resume_dir.glob("*.json"):
            if fpath.name.startswith("_"):
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                res = json.load(f)
                self.resume_data[res["id"]] = res
                
        logger.info(f"Loaded {len(matches)} matches, {len(self.github_data)} GitHub, {len(self.resume_data)} Resumes.")
        return matches

    def _merge_skills(self, gh_weights: Dict[str, float], resume_skills: List[str]) -> Dict[str, float]:
        """
        Merge skills:
        - Keep GitHub skills and their exact weights
        - Add missing resume skills with a default lower weight (e.g., 0.3)
        Returns a sorted dictionary by weight descending.
        """
        merged = dict(gh_weights)
        
        # Add resume skills that aren't in GitHub weights
        for skill in resume_skills:
            if skill not in merged:
                merged[skill] = 0.3
                
        # Sort by weight descending
        return {k: round(v, 4) for k, v in sorted(merged.items(), key=lambda item: item[1], reverse=True)}

    def _merge_domains(self, gh_projects: List[Dict], resume_roles: List[str], resume_traj: List[str]) -> List[str]:
        """
        Extract unique domains from GitHub projects and Resume roles.
        Note: We avoid complex tool-to-domain mapping here since the profile
        matcher already used that for the match decision. We just extract
        explicitly stated domains and roles.
        """
        domains = set()
        
        # From GitHub projects
        for p in gh_projects:
            d = p.get("domain", "general").strip().lower()
            if d and d != "general":
                domains.add(d)
                
        # From Resume roles
        for r in (resume_roles + resume_traj):
            clean_role = r.replace("[target]", "").strip().lower()
            if clean_role:
                domains.add(clean_role)
                
        return sorted(list(domains))

    def _clean_projects(self, gh_projects: List[Dict]) -> List[Dict]:
        """Ensure projects have a consistent schema."""
        cleaned = []
        for p in gh_projects:
            cleaned.append({
                "name": p.get("name", "Unknown Project"),
                "domain": p.get("domain", "general"),
                "tools": p.get("tools", []),
                "stars": p.get("stars", 0)
            })
        return cleaned

    def _build_full_profile(self, user_id: str, gh: Dict, res: Dict, match: Dict) -> Dict:
        """Constructs a FULL profile merging GitHub and Resume data."""
        # Merge logic
        gh_exp = gh.get("experience_estimate", "intermediate")
        res_exp = res.get("experience_level", "mid")
        # Default to Resume experience level as it's usually more accurate/proven
        unified_exp = res_exp if res_exp else gh_exp
        
        return {
            "user_id": user_id,
            "profile_type": "full",
            
            "skills": self._merge_skills(gh.get("skill_weights", {}), res.get("skills", [])),
            "domains": self._merge_domains(
                gh.get("projects", []), 
                res.get("roles", []), 
                res.get("career_trajectory", [])
            ),
            "experience_level": unified_exp,
            
            "career_trajectory": res.get("career_trajectory", []),
            "companies": res.get("companies", []),
            
            "projects": self._clean_projects(gh.get("projects", [])),
            
            "confidence_score": round(match.get("match_score", 0.0), 4)
        }

    def _build_partial_profile(self, user_id: str, gh: Dict) -> Dict:
        """Constructs a PARTIAL profile using only GitHub data."""
        domains = set()
        for p in gh.get("projects", []):
            d = p.get("domain", "general").strip().lower()
            if d and d != "general":
                domains.add(d)
                
        # Sort skills by weight
        skills = {k: round(v, 4) for k, v in sorted(gh.get("skill_weights", {}).items(), key=lambda i: i[1], reverse=True)}

        return {
            "user_id": user_id,
            "profile_type": "partial",
            
            "skills": skills,
            "domains": sorted(list(domains)),
            "experience_level": gh.get("experience_estimate", "intermediate"),
            
            "projects": self._clean_projects(gh.get("projects", [])),
            
            "confidence_score": 0.40  # Fixed proxy score for partial profiles
        }

    def run(self) -> None:
        logger.info("=== Unified Profile Builder started ===")
        
        matches = self._load_data()
        
        if not matches or not self.github_data:
            logger.error("Missing required data (matches or GitHub profiles). Aborting.")
            return

        full_count = 0
        partial_count = 0
        
        # Process each match
        for match in matches:
            gh_id = match.get("github_id")
            res_id = match.get("matched_resume_id")
            use_for_unification = match.get("use_for_unification", False)
            
            gh_data = self.github_data.get(gh_id)
            if not gh_data:
                logger.warning(f"GitHub profile {gh_id} not found in loaded data. Skipping.")
                continue
                
            # Assign a unique, synthetic UUID
            # This severs the explicit link to the original GitHub username for the downstream graph
            synthetic_user_id = f"user_{uuid.uuid4().hex[:12]}"
            
            res_data = self.resume_data.get(res_id)
            
            if use_for_unification and res_data:
                # FULL profile
                profile = self._build_full_profile(synthetic_user_id, gh_data, res_data, match)
                full_count += 1
            else:
                # PARTIAL profile
                profile = self._build_partial_profile(synthetic_user_id, gh_data)
                partial_count += 1
                
            # Save individual file
            out_path = self.output_dir / f"{synthetic_user_id}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2)
                
        # Save consolidated JSON map (helps for fast loading downstream)
        all_profiles = []
        for fpath in sorted(self.output_dir.glob("user_*.json")):
            with open(fpath, "r", encoding="utf-8") as f:
                all_profiles.append(json.load(f))
                
        with open(self.output_dir / "_all_unified.json", "w", encoding="utf-8") as f:
            json.dump(all_profiles, f, indent=2)

        logger.info("=== Unification Complete ===")
        logger.info(f"  Total processed : {full_count + partial_count}")
        logger.info(f"  FULL profiles   : {full_count}  (Matches >= 0.50)")
        logger.info(f"  PARTIAL profiles: {partial_count}  (Matches < 0.50)")
        logger.info(f"  Output directory: {self.output_dir.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Unified Profile Builder")
    parser.add_argument("--github",  type=Path, default=Path("data/processed/github_profiles"))
    parser.add_argument("--resumes", type=Path, default=Path("data/processed/resume_profiles"))
    parser.add_argument("--matches", type=Path, default=Path("data/processed/matched_profiles/_all_matches.json"))
    parser.add_argument("--output",  type=Path, default=Path("data/processed/unified_profiles"))
    args = parser.parse_args()

    builder = UnifiedProfileBuilder(
        gh_dir=args.github,
        resume_dir=args.resumes,
        matches_file=args.matches,
        output_dir=args.output,
    )
    builder.run()
