"""
github_profile_processor.py
----------------------------
Transforms 500 raw GitHub user profiles from `data/raw/profiles/github/`
into structured, analysis-ready career profiles saved to
`data/processed/github_profiles/`.

Pipeline Steps:
  1. Data Cleaning       – remove repos with null lang/desc, normalize text
  2. Skill Normalization – language + topic → canonical skill names
  3. Skill Extraction    – aggregate unique skills per user
  4. Skill Weighting     – frequency × stars × recency, normalized 0–1
  5. Project Signals     – identify key repos, extract domains
  6. Experience Estimate – heuristic based on repo count
  7. Activity Level      – heuristic based on commits + followers
  8. Output Storage      – one JSON file per user, + consolidated master file

Usage:
  PYTHONPATH=. python3 src/processing/github_profile_processor.py
  PYTHONPATH=. python3 src/processing/github_profile_processor.py --input data/raw/profiles/github --output data/processed/github_profiles
"""

import argparse
import json
import logging
import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/github_processor.log", mode="a"),
    ],
)
logger = logging.getLogger("github_profile_processor")

Path("logs").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Constants and Mappings
# ---------------------------------------------------------------------------

# Canonical skill normalization map
# keys are lowercased; values are canonical names
SKILL_NORMALIZATION: Dict[str, str] = {
    # Languages
    "jupyter notebook": "python",
    "ipython notebook": "python",
    "python3": "python",
    "py": "python",
    "js": "javascript",
    "node": "javascript",
    "node.js": "javascript",
    "nodejs": "javascript",
    "ecmascript": "javascript",
    "ts": "typescript",
    "golang": "go",
    "c++": "cpp",
    "c#": "csharp",
    "objective-c": "objective_c",
    "objective c": "objective_c",
    "vim script": "vimscript",
    "vim l": "vimscript",
    "shell": "bash",
    "zsh": "bash",
    "sh": "bash",
    "makefile": "make",
    "dockerfile": "docker",
    "hcl": "terraform",
    # Topics → normalized skills
    "ml": "machine_learning",
    "machine-learning": "machine_learning",
    "machine_learning": "machine_learning",
    "deep-learning": "deep_learning",
    "deep_learning": "deep_learning",
    "dl": "deep_learning",
    "nlp": "nlp",
    "natural-language-processing": "nlp",
    "computer-vision": "computer_vision",
    "cv": "computer_vision",
    "data-science": "data_science",
    "datascience": "data_science",
    "data-engineering": "data_engineering",
    "devops": "devops",
    "ci-cd": "devops",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "docker": "docker",
    "containerization": "docker",
    "aws": "aws",
    "amazon-web-services": "aws",
    "azure": "azure",
    "gcp": "gcp",
    "google-cloud": "gcp",
    "cloud": "cloud",
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "vue": "vuejs",
    "vue.js": "vuejs",
    "vuejs": "vuejs",
    "angular": "angular",
    "angularjs": "angular",
    "nextjs": "nextjs",
    "next.js": "nextjs",
    "fastapi": "fastapi",
    "flask": "flask",
    "django": "django",
    "express": "expressjs",
    "expressjs": "expressjs",
    "spring": "spring",
    "spring-boot": "spring",
    "springboot": "spring",
    "graphql": "graphql",
    "rest": "rest_api",
    "rest-api": "rest_api",
    "restful": "rest_api",
    "web-development": "web_development",
    "webdev": "web_development",
    "frontend": "frontend",
    "front-end": "frontend",
    "backend": "backend",
    "back-end": "backend",
    "fullstack": "fullstack",
    "full-stack": "fullstack",
    "microservices": "microservices",
    "api": "api",
    "blockchain": "blockchain",
    "cryptocurrency": "blockchain",
    "android": "android",
    "ios": "ios",
    "swift": "swift",
    "mobile": "mobile_development",
    "mobile-development": "mobile_development",
    "algorithm": "algorithms",
    "algorithms": "algorithms",
    "datastructures": "data_structures",
    "data-structures": "data_structures",
    "system-design": "system_design",
    "distributed-systems": "distributed_systems",
    "security": "security",
    "cybersecurity": "security",
    "open-source": "open_source",
    "linux": "linux",
    "embedded": "embedded_systems",
    "iot": "iot",
    "game": "game_development",
    "game-development": "game_development",
    "gamedev": "game_development",
    "automation": "automation",
    "testing": "testing",
    "tdd": "testing",
    "bdd": "testing",
}

# Domain mapping from topics
DOMAIN_MAP: Dict[str, str] = {
    "machine_learning": "machine_learning",
    "deep_learning": "deep_learning",
    "nlp": "nlp",
    "computer_vision": "computer_vision",
    "data_science": "data_science",
    "data_engineering": "data_engineering",
    "web_development": "web_development",
    "frontend": "frontend",
    "backend": "backend",
    "fullstack": "fullstack",
    "devops": "devops",
    "cloud": "cloud",
    "kubernetes": "cloud",
    "aws": "cloud",
    "gcp": "cloud",
    "azure": "cloud",
    "blockchain": "blockchain",
    "mobile_development": "mobile_development",
    "android": "mobile_development",
    "ios": "mobile_development",
    "game_development": "game_development",
    "security": "security",
    "algorithms": "computer_science",
    "data_structures": "computer_science",
    "system_design": "system_design",
    "distributed_systems": "distributed_systems",
    "iot": "iot",
    "embedded_systems": "embedded_systems",
    "automation": "automation",
}

# Reference date for recency scoring
_NOW = datetime.now(timezone.utc)
_OLDEST_DATE = datetime(2010, 1, 1, tzinfo=timezone.utc)
_DATE_RANGE_DAYS = (_NOW - _OLDEST_DATE).days or 1


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _normalize_text(text: Optional[str]) -> str:
    """Lowercase, strip accents, remove non-ASCII special chars."""
    if not text:
        return ""
    # Normalize unicode (e.g., Chinese chars kept as-is, just strip control chars)
    text = unicodedata.normalize("NFKD", text)
    # Remove non-printable control chars but keep Unicode letters/digits/spaces/punct
    text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
    return text.strip().lower()


def _normalize_skill(raw: str) -> str:
    """Return the canonical skill name for a raw language or topic string."""
    key = raw.strip().lower()
    return SKILL_NORMALIZATION.get(key, key.replace("-", "_").replace(" ", "_"))


def _recency_score(created_at: Optional[str]) -> float:
    """Return 0–1 where 1 = created today, 0 = created before 2010."""
    if not created_at:
        return 0.0
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        days_ago = (_NOW - dt).days
        score = 1.0 - min(days_ago, _DATE_RANGE_DAYS) / _DATE_RANGE_DAYS
        return max(0.0, min(1.0, score))
    except Exception:
        return 0.0


def _star_score(stars: int) -> float:
    """Logarithmic star weight: log(stars+1)/log(10001) → 0–1."""
    return math.log(stars + 1) / math.log(10001)


# ---------------------------------------------------------------------------
# Processor class
# ---------------------------------------------------------------------------

class GitHubProfileProcessor:
    """
    Transforms raw GitHub user profiles into structured career signals.
    """

    MIN_STARS_OR_TOPICS = 5  # Step 5: threshold for "important" repos

    def __init__(self, input_dir: Path, output_dir: Path):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._processed = 0
        self._failed = 0

    # ------------------------------------------------------------------
    # Step 1: Data Cleaning
    # ------------------------------------------------------------------

    def _clean_repos(self, repos: List[Dict]) -> List[Dict]:
        """
        Remove repos with:
          - null or empty `language`
          - null or empty `description`
        Deduplicate by repo name. Normalize text fields.
        """
        seen_names: Set[str] = set()
        cleaned = []
        for repo in repos:
            name = repo.get("name") or ""
            lang = repo.get("language")
            desc = repo.get("description")

            # Filter nulls
            if not lang or not desc:
                continue
            # Deduplicate
            norm_name = name.lower()
            if norm_name in seen_names:
                continue
            seen_names.add(norm_name)

            cleaned.append({
                "name": name,
                "description": _normalize_text(desc),
                "language": lang,          # keep original case for display
                "stars": int(repo.get("stars") or 0),
                "topics": [t for t in (repo.get("topics") or []) if t],
                "created_at": repo.get("created_at"),
            })
        return cleaned

    # ------------------------------------------------------------------
    # Step 2 + 3: Skill Normalization & Extraction
    # ------------------------------------------------------------------

    def _extract_skills(self, repos: List[Dict]) -> List[str]:
        """Return a unique sorted list of normalized skills for the user."""
        skills: Set[str] = set()
        for repo in repos:
            lang = repo.get("language")
            if lang:
                skills.add(_normalize_skill(lang))
            for topic in repo.get("topics", []):
                skills.add(_normalize_skill(topic))
        return sorted(skills)

    # ------------------------------------------------------------------
    # Step 4: Skill Weighting
    # ------------------------------------------------------------------

    def _compute_skill_weights(self, repos: List[Dict]) -> Dict[str, float]:
        """
        Raw weight = sum over repos where skill appears of:
            (1 + star_score) × (1 + recency_score)
        Then normalize all weights to [0, 1].
        """
        raw: Dict[str, float] = {}

        for repo in repos:
            star_s = _star_score(repo.get("stars", 0))
            rec_s = _recency_score(repo.get("created_at"))
            contribution = (1 + star_s) * (1 + rec_s)

            lang = repo.get("language")
            if lang:
                skill = _normalize_skill(lang)
                raw[skill] = raw.get(skill, 0.0) + contribution

            for topic in repo.get("topics", []):
                skill = _normalize_skill(topic)
                raw[skill] = raw.get(skill, 0.0) + contribution

        if not raw:
            return {}

        max_w = max(raw.values())
        if max_w == 0:
            return {k: 0.0 for k in raw}
        return {k: round(v / max_w, 4) for k, v in sorted(raw.items(), key=lambda x: -x[1])}

    # ------------------------------------------------------------------
    # Step 5: Project Signal Extraction
    # ------------------------------------------------------------------

    def _extract_projects(self, repos: List[Dict]) -> List[Dict[str, Any]]:
        """
        Identify important repos (stars > 5 OR non-empty topics).
        Extract domain from topics, tools from language + topics.
        """
        projects = []
        for repo in repos:
            stars = repo.get("stars", 0)
            topics = repo.get("topics", [])
            if stars <= self.MIN_STARS_OR_TOPICS and not topics:
                continue

            # Determine domain
            domain = "general"
            for topic in topics:
                norm = _normalize_skill(topic)
                if norm in DOMAIN_MAP:
                    domain = DOMAIN_MAP[norm]
                    break

            # Tools = language + normalized topics
            tools: List[str] = []
            lang = repo.get("language")
            if lang:
                tools.append(_normalize_skill(lang))
            for topic in topics:
                norm = _normalize_skill(topic)
                if norm not in tools:
                    tools.append(norm)

            projects.append({
                "name": repo.get("name"),
                "domain": domain,
                "tools": tools,
                "stars": stars,
            })

        return projects

    # ------------------------------------------------------------------
    # Step 6: Experience Estimation
    # ------------------------------------------------------------------

    def _estimate_experience(self, repo_count: int) -> str:
        if repo_count < 5:
            return "beginner"
        elif repo_count <= 20:
            return "intermediate"
        else:
            return "advanced"

    # ------------------------------------------------------------------
    # Step 7: Activity Level
    # ------------------------------------------------------------------

    def _estimate_activity(self, total_commits: str, followers: str) -> str:
        """
        Heuristic combining commits + followers:
          high   : commits > 10000 OR followers > 500
          medium : commits > 1000  OR followers > 50
          low    : otherwise
        """
        try:
            commits = int(total_commits or 0)
        except (ValueError, TypeError):
            commits = 0
        try:
            fol = int(followers or 0)
        except (ValueError, TypeError):
            fol = 0

        if commits > 10_000 or fol > 500:
            return "high"
        elif commits > 1_000 or fol > 50:
            return "medium"
        else:
            return "low"

    # ------------------------------------------------------------------
    # Main processing method for a single user
    # ------------------------------------------------------------------

    def _process_profile(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        username = raw.get("username", "unknown")

        # Step 1: Clean repos
        clean_repos = self._clean_repos(raw.get("repositories", []))

        # Step 2+3: Skills
        skills = self._extract_skills(clean_repos)

        # Step 4: Weights (computed on clean repos, but also include lang from raw
        #          repos that may have been dropped for missing description)
        all_repos_for_weight = []
        for repo in raw.get("repositories", []):
            if repo.get("language"):  # Only need language for weighting
                all_repos_for_weight.append(repo)
        skill_weights = self._compute_skill_weights(all_repos_for_weight)

        # Step 5: Projects
        projects = self._extract_projects(clean_repos)

        # Step 6: Experience
        total_repo_count = len(raw.get("repositories", []))
        experience = self._estimate_experience(total_repo_count)

        # Step 7: Activity
        activity = self._estimate_activity(
            raw.get("total_commits", "0"),
            raw.get("followers", "0"),
        )

        return {
            "username": username,
            "skills": skills,
            "skill_weights": skill_weights,
            "projects": projects,
            "experience_estimate": experience,
            "activity_level": activity,
            "followers": raw.get("followers", "0"),
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Step 8: Run full pipeline
    # ------------------------------------------------------------------

    def run(self) -> None:
        raw_files = sorted(self.input_dir.glob("*.json"))
        total = len(raw_files)
        logger.info(f"=== GitHub Profile Processor | {total} profiles to process ===")

        all_profiles = []

        for i, fpath in enumerate(raw_files, 1):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    raw = json.load(f)

                processed = self._process_profile(raw)
                all_profiles.append(processed)

                # Save individual file
                out_path = self.output_dir / fpath.name
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(processed, f, indent=2, ensure_ascii=False)

                self._processed += 1
                if i % 50 == 0 or i == total:
                    logger.info(f"Progress: {i}/{total} processed")

            except Exception as e:
                logger.error(f"Failed to process {fpath.name}: {e}")
                self._failed += 1

        # Save consolidated master file
        master_path = self.output_dir / "_all_profiles.json"
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(all_profiles, f, indent=2, ensure_ascii=False)

        logger.info("=== Processing complete ===")
        logger.info(f"  Processed : {self._processed}")
        logger.info(f"  Failed    : {self._failed}")
        logger.info(f"  Output    : {self.output_dir.resolve()}")
        logger.info(f"  Master    : {master_path.resolve()}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub Profile Processor")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/profiles/github"),
        help="Directory containing raw GitHub JSON profiles",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/github_profiles"),
        help="Output directory for processed profiles",
    )
    args = parser.parse_args()

    processor = GitHubProfileProcessor(input_dir=args.input, output_dir=args.output)
    processor.run()
