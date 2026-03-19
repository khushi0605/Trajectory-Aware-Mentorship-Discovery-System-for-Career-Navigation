"""
job_description_processor.py
-----------------------------
Transforms raw job description CSV data from `data/raw/job_descriptions/`
into structured role-to-skill mappings for career modeling.

Input: job_dataset.csv (1,068 rows)
Columns: JobID, Title, ExperienceLevel, YearsOfExperience, Skills,
         Responsibilities, Keywords

Pipeline Steps:
  1. Load CSV
  2. Clean text fields (lowercase, strip noise)
  3. Extract job title → normalize to canonical role
     Extract skills → from Skills + Keywords fields + text mining
  4. Normalize skills using predefined dictionary
  5. Aggregate: group by role, union all skills
  6. Output per-role JSON profile
  7. Store in data/processed/job_req_profiles/
     Also saves _role_skill_map.json (master lookup table)

Usage:
  PYTHONPATH=. python3 src/processing/job_description_processor.py
"""

import argparse
import csv
import json
import logging
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/job_description_processor.log", mode="a"),
    ],
)
logger = logging.getLogger("job_description_processor")
Path("logs").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Skill normalization dictionary (reused + extended from resume processor)
# ---------------------------------------------------------------------------
SKILL_NORM: Dict[str, str] = {
    # Languages
    "c#": "csharp",
    "vb.net": "dotnet",
    "vb.net basics": "dotnet",
    ".net": "dotnet",
    ".net framework": "dotnet",
    ".net core": "dotnet",
    "asp.net": "dotnet",
    "asp.net mvc": "dotnet",
    "asp.net core": "dotnet",
    "js": "javascript",
    "javascript basics": "javascript",
    "node": "javascript",
    "node.js": "javascript",
    "nodejs": "javascript",
    "ts": "typescript",
    "py": "python",
    "python3": "python",
    "golang": "go",
    "c++": "cpp",
    "objective-c": "objective_c",
    "r language": "r",
    # ML / AI
    "ml": "machine_learning",
    "machine learning": "machine_learning",
    "ai": "artificial_intelligence",
    "deep learning": "deep_learning",
    "dl": "deep_learning",
    "nlp": "nlp",
    "natural language processing": "nlp",
    "computer vision": "computer_vision",
    "llm": "llm",
    "large language models": "llm",
    "llms": "llm",
    "generative ai": "generative_ai",
    "gen ai": "generative_ai",
    "rag": "rag",
    "reinforcement learning": "reinforcement_learning",
    # Data
    "data science": "data_science",
    "data analysis": "data_analysis",
    "data analytics": "data_analysis",
    "data engineering": "data_engineering",
    "big data": "big_data",
    "etl": "etl",
    "sql": "sql",
    "mysql": "sql",
    "postgresql": "sql",
    "postgres": "sql",
    "mssql": "sql",
    "sql server": "sql",
    "t-sql": "sql",
    "pl/sql": "sql",
    "nosql": "nosql",
    "mongodb": "mongodb",
    "elasticsearch": "elasticsearch",
    "redis": "redis",
    "cassandra": "cassandra",
    "hbase": "hbase",
    "hdfs": "hadoop",
    "mapreduce": "hadoop",
    "apache hive": "hadoop",
    "hive": "hadoop",
    "yarn": "hadoop",
    "hadoop ecosystem": "hadoop",
    "spark": "spark",
    "apache spark": "spark",
    "pyspark": "spark",
    "kafka": "kafka",
    "apache kafka": "kafka",
    "airflow": "airflow",
    "apache airflow": "airflow",
    "dbt": "dbt",
    "snowflake": "snowflake",
    "databricks": "databricks",
    # ML frameworks
    "tensorflow": "tensorflow",
    "pytorch": "pytorch",
    "keras": "keras",
    "scikit-learn": "scikit_learn",
    "sklearn": "scikit_learn",
    "xgboost": "xgboost",
    "pandas": "pandas",
    "numpy": "numpy",
    "matplotlib": "matplotlib",
    "seaborn": "seaborn",
    # Cloud & DevOps
    "aws": "aws",
    "amazon web services": "aws",
    "ec2": "aws",
    "s3": "aws",
    "lambda": "aws",
    "azure": "azure",
    "microsoft azure": "azure",
    "gcp": "gcp",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "devops": "devops",
    "ci/cd": "devops",
    "ci-cd": "devops",
    "continuous integration": "devops",
    "docker": "docker",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "terraform": "terraform",
    "ansible": "ansible",
    "jenkins": "jenkins",
    "github actions": "devops",
    # Web
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "angular": "angular",
    "angularjs": "angular",
    "vue": "vuejs",
    "vue.js": "vuejs",
    "next.js": "nextjs",
    "nextjs": "nextjs",
    "django": "django",
    "flask": "flask",
    "fastapi": "fastapi",
    "express": "expressjs",
    "express.js": "expressjs",
    "spring": "spring",
    "spring boot": "spring",
    "spring mvc": "spring",
    "rest api": "rest_api",
    "restful api": "rest_api",
    "graphql": "graphql",
    "html": "html",
    "html5": "html",
    "css": "css",
    "css3": "css",
    "bootstrap": "bootstrap",
    "tailwind": "tailwind_css",
    "tailwindcss": "tailwind_css",
    # Mobile
    "android": "android",
    "ios": "ios",
    "react native": "react_native",
    "flutter": "flutter",
    "kotlin": "kotlin",
    "swift": "swift",
    # Tools
    "git": "git",
    "github": "git",
    "gitlab": "git",
    "linux": "linux",
    "unix": "linux",
    "agile": "agile",
    "scrum": "agile",
    "jira": "jira",
    "unit testing": "testing",
    "selenium": "selenium",
    "tableau": "tableau",
    "power bi": "power_bi",
    "excel": "excel",
    "ms excel": "excel",
    "microsof excel": "excel",
    "linq": "dotnet",
    "entity framework": "dotnet",
    "visual studio": "visual_studio",
    "vs code": "vscode",
    "postman": "postman",
    "swagger": "rest_api",
    "mvc": "mvc_pattern",
    "mvc pattern": "mvc_pattern",
    "design patterns": "design_patterns",
    "solid principles": "design_patterns",
    "oop": "oop",
    "object oriented programming": "oop",
    "data structures": "data_structures",
    "algorithms": "algorithms",
    "system design": "system_design",
    "microservices": "microservices",
    "api development": "rest_api",
    "web services": "rest_api",
    "security": "security",
    "cybersecurity": "security",
    "networking": "networking",
    "cloud computing": "cloud",
    "communication": "communication",
    "problem solving": "problem_solving",
    "leadership": "leadership",
    "teamwork": "teamwork",
    "project management": "project_management",
    "time management": "time_management",
    "analytical skills": "analytical_skills",
}

# ---------------------------------------------------------------------------
# Role normalization (consistent with resume processor)
# ---------------------------------------------------------------------------
ROLE_NORM: Dict[str, str] = {
    ".net developer": "dotnet_developer",
    "net developer": "dotnet_developer",
    "software engineer": "software_engineer",
    "software developer": "software_engineer",
    "sde": "software_engineer",
    "junior developer": "software_engineer",
    "junior software engineer": "software_engineer",
    "senior software engineer": "senior_software_engineer",
    "lead software engineer": "senior_software_engineer",
    "principal engineer": "senior_software_engineer",
    "staff engineer": "senior_software_engineer",
    "backend developer": "backend_developer",
    "backend engineer": "backend_developer",
    "front end developer": "frontend_developer",
    "frontend developer": "frontend_developer",
    "full stack developer": "fullstack_developer",
    "fullstack developer": "fullstack_developer",
    "full-stack developer": "fullstack_developer",
    "full stack engineer": "fullstack_developer",
    "data analyst": "data_analyst",
    "business analyst": "data_analyst",
    "data scientist": "data_scientist",
    "data engineer": "data_engineer",
    "big data engineer": "data_engineer",
    "analytics engineer": "data_engineer",
    "ml engineer": "ml_engineer",
    "machine learning engineer": "ml_engineer",
    "ai engineer": "ml_engineer",
    "ai/ml engineer": "ml_engineer",
    "research scientist": "research_scientist",
    "devops engineer": "devops_engineer",
    "cloud engineer": "cloud_engineer",
    "site reliability engineer": "devops_engineer",
    "sre": "devops_engineer",
    "platform engineer": "devops_engineer",
    "tech lead": "tech_lead",
    "technical lead": "tech_lead",
    "engineering manager": "engineering_manager",
    "product manager": "product_manager",
    "project manager": "project_manager",
    "qa engineer": "qa_engineer",
    "quality assurance engineer": "qa_engineer",
    "test engineer": "qa_engineer",
    "sdet": "qa_engineer",
    "ui/ux designer": "ui_ux_designer",
    "ux designer": "ui_ux_designer",
    "database administrator": "dba",
    "dba": "dba",
    "security engineer": "security_engineer",
    "cybersecurity analyst": "security_engineer",
    "android developer": "android_developer",
    "ios developer": "ios_developer",
    "mobile developer": "mobile_developer",
    "react native developer": "mobile_developer",
    "flutter developer": "mobile_developer",
    "solutions architect": "software_architect",
    "software architect": "software_architect",
    "cloud architect": "software_architect",
    "data architect": "data_architect",
    "python developer": "python_developer",
    "java developer": "java_developer",
    "javascript developer": "javascript_developer",
    "node.js developer": "javascript_developer",
    "react developer": "react_developer",
    "angular developer": "angular_developer",
    "blockchain developer": "blockchain_developer",
    "game developer": "game_developer",
    "embedded systems engineer": "embedded_engineer",
    "network engineer": "network_engineer",
    "systems administrator": "sysadmin",
    "system administrator": "sysadmin",
    "technical writer": "technical_writer",
    "scrum master": "scrum_master",
    "intern": "intern",
}

# Skill keywords to scan from free text (Responsibilities / Keywords)
_TEXT_SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "golang", "c++", "csharp",
    "kotlin", "swift", "rust", "scala", "r", "ruby", "php", "matlab",
    "react", "angular", "vue", "django", "flask", "fastapi", "spring",
    "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy", "keras",
    "docker", "kubernetes", "aws", "azure", "gcp", "terraform", "jenkins",
    "spark", "kafka", "hadoop", "airflow", "dbt", "snowflake", "databricks",
    "sql", "mongodb", "postgresql", "redis", "cassandra", "elasticsearch",
    "machine learning", "deep learning", "nlp", "computer vision", "llm",
    "microservices", "rest api", "graphql", "git", "linux", "agile",
    "data structures", "algorithms", "system design", "oop",
    "tableau", "power bi", "excel", "selenium", "jira",
]

# Compile keyword patterns for fast text scanning
_KW_PATTERNS = [(kw, re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE))
                for kw in _TEXT_SKILL_KEYWORDS]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def _normalize_skill(raw: str) -> Optional[str]:
    """Return canonical skill name or None if noise."""
    key = _normalize_text(raw).strip()
    if len(key) < 2:
        return None
    if key in SKILL_NORM:
        return SKILL_NORM[key]
    # Partial match
    for k, v in SKILL_NORM.items():
        if k == key:
            return v
    # Clean fallback
    result = re.sub(r"[^a-z0-9_]", "_", key)
    result = re.sub(r"_+", "_", result).strip("_")
    return result if len(result) > 1 else None


def _normalize_role(raw: str) -> str:
    """Return canonical role key."""
    key = _normalize_text(raw).strip()
    if key in ROLE_NORM:
        return ROLE_NORM[key]
    # Partial / substring match
    best = (0, "")
    for k, v in ROLE_NORM.items():
        if k in key or key in k:
            if len(k) > best[0]:
                best = (len(k), v)
    if best[0] > 0:
        return best[1]
    # Fallback: clean
    result = re.sub(r"[^a-z0-9_]", "_", key)
    return re.sub(r"_+", "_", result).strip("_") or "unknown"


def _extract_skills_from_text(text: str) -> List[str]:
    """Scan free text for known skill keywords."""
    found = []
    for kw, pat in _KW_PATTERNS:
        if pat.search(text):
            norm = _normalize_skill(kw)
            if norm:
                found.append(norm)
    return found


def _extract_skills_from_field(field: str) -> List[str]:
    """
    Parse a semicolon / comma / pipe delimited skill field.
    e.g. "C#; .NET Framework; SQL Server; HTML; CSS"
    """
    if not field or not field.strip():
        return []
    # Split on ; , | and strip
    parts = re.split(r"[;,|]+", field)
    skills = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        norm = _normalize_skill(part)
        if norm:
            skills.append(norm)
    return skills


# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

class JobDescriptionProcessor:
    """
    Extracts structured role-to-skill mappings from job description data.
    """

    def __init__(self, input_path: Path, output_dir: Path):
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # role → set of skills
        self._role_skills: Dict[str, Set[str]] = defaultdict(set)
        # role → metadata (experience_levels seen, job_count)
        self._role_meta: Dict[str, Dict] = defaultdict(lambda: {"job_count": 0, "experience_levels": set()})
        self._processed = 0
        self._skipped = 0

    def _process_row(self, row: Dict[str, str]) -> Optional[str]:
        """Process one CSV row. Returns the normalized role name or None."""
        title_raw = row.get("Title", "").strip()
        if not title_raw:
            self._skipped += 1
            return None

        role = _normalize_role(title_raw)
        exp_level = _normalize_text(row.get("ExperienceLevel", "")).strip()

        # Collect skills from all signal sources
        skills_raw = row.get("Skills", "")
        keywords_raw = row.get("Keywords", "")
        responsibilities_raw = row.get("Responsibilities", "")

        skills: Set[str] = set()

        # Step 3a: from Skills field (semicolon-separated)
        for s in _extract_skills_from_field(skills_raw):
            skills.add(s)

        # Step 3b: from Keywords field
        for s in _extract_skills_from_field(keywords_raw):
            skills.add(s)

        # Step 3c: mine Responsibilities free text for skill keywords
        for s in _extract_skills_from_text(responsibilities_raw):
            skills.add(s)

        # Filter out very generic/noisy skills
        noise = {"and", "the", "with", "for", "of"}
        skills = {s for s in skills if s not in noise and len(s) > 1}

        # Accumulate into role bucket (Step 5: aggregate)
        self._role_skills[role].update(skills)
        self._role_meta[role]["job_count"] += 1
        if exp_level:
            self._role_meta[role]["experience_levels"].add(exp_level)

        self._processed += 1
        return role

    def run(self) -> None:
        logger.info(f"=== Job Description Processor | Input: {self.input_path} ===")

        with open(self.input_path, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        logger.info(f"  Total rows: {len(rows)}")

        for row in rows:
            try:
                self._process_row(row)
            except Exception as e:
                logger.error(f"Error on row: {e}")
                self._skipped += 1

        logger.info(f"  Processed: {self._processed} rows → {len(self._role_skills)} unique roles")

        # Step 6+7: Output one JSON per role + master map
        all_profiles = []
        for role, skills in sorted(self._role_skills.items()):
            meta = self._role_meta[role]
            profile: Dict[str, Any] = {
                "role": role,
                "required_skills": sorted(list(skills)),
                "job_count": meta["job_count"],
                "experience_levels": sorted(list(meta["experience_levels"])),
            }
            all_profiles.append(profile)

            # Individual file per role
            safe_name = re.sub(r"[^a-z0-9_]", "_", role).strip("_")
            out_path = self.output_dir / f"{safe_name}.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)

        # Master role→skills lookup table (flat dict for fast lookup)
        master_map = {p["role"]: p["required_skills"] for p in all_profiles}
        master_path = self.output_dir / "_role_skill_map.json"
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(master_map, f, indent=2, ensure_ascii=False)

        # Full profiles list
        all_path = self.output_dir / "_all_profiles.json"
        with open(all_path, "w", encoding="utf-8") as f:
            json.dump(all_profiles, f, indent=2, ensure_ascii=False)

        logger.info("=== Job Processing Complete ===")
        logger.info(f"  Unique roles : {len(all_profiles)}")
        logger.info(f"  Total rows   : {self._processed}")
        logger.info(f"  Skipped      : {self._skipped}")
        logger.info(f"  Output       : {self.output_dir.resolve()}")
        logger.info(f"  Master map   : {master_path.resolve()}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Job Description Processor")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/job_descriptions/job_dataset.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/job_req_profiles"),
    )
    args = parser.parse_args()

    processor = JobDescriptionProcessor(input_path=args.input, output_dir=args.output)
    processor.run()
