"""
resume_profile_processor.py
----------------------------
Transforms raw resume CSV data from `data/raw/resumes/` into structured,
analysis-ready career profiles saved to `data/processed/resume_profiles/`.

The CSV has 9,544 rows. Key column quirks handled here:
  - Skills and positions are stored as Python literal list strings
    e.g., "['Big Data', 'Python']"
  - related_skils_in_job is a nested list string: "[['Big Data'], ['Python']]"
  - The job_position_name column has a BOM prefix (\\ufeff)
  - Dates like 'Nov 2019', 'Till Date', 'Present', 'NA', etc.

Pipeline Steps:
  1.  Load CSV, iterate records
  2.  Field selection & text cleaning
  3.  Skill extraction & normalization
  4.  Role extraction & normalization
  5.  Career trajectory construction (chronological order)
  6.  Experience estimation (entry / mid / senior)
  7.  Domain enrichment + company count
  8.  Filtering (remove if no roles AND no skills)
  9.  Structured profile output
  10. Storage – one JSON + consolidated _all_profiles.json

Usage:
  PYTHONPATH=. python3 src/processing/resume_profile_processor.py
"""

import argparse
import ast
import csv
import json
import logging
import re
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/resume_processor.log", mode="a"),
    ],
)
logger = logging.getLogger("resume_profile_processor")
Path("logs").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Skill normalization dictionary
# ---------------------------------------------------------------------------
SKILL_NORM: Dict[str, str] = {
    # Programming languages
    "js": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    "node.js": "javascript",
    "ts": "typescript",
    "py": "python",
    "python3": "python",
    "golang": "go",
    "c++": "cpp",
    "c#": "csharp",
    "dotnet": "dotnet",
    ".net": "dotnet",
    "asp.net": "dotnet",
    "objective-c": "objective_c",
    "r language": "r",
    # ML / AI
    "ml": "machine_learning",
    "machine learning": "machine_learning",
    "ai": "artificial_intelligence",
    "artificial intelligence": "artificial_intelligence",
    "deep learning": "deep_learning",
    "dl": "deep_learning",
    "nlp": "nlp",
    "natural language processing": "nlp",
    "computer vision": "computer_vision",
    "cv": "computer_vision",
    "reinforcement learning": "reinforcement_learning",
    "rl": "reinforcement_learning",
    # Data
    "ds": "data_science",
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
    "nosql": "nosql",
    "mongodb": "mongodb",
    "elasticsearch": "elasticsearch",
    "redis": "redis",
    "cassandra": "cassandra",
    "hbase": "hbase",
    "hdfs": "hadoop",
    "mapreduce": "hadoop",
    "hive": "hadoop",
    "yarn": "hadoop",
    # Cloud & DevOps
    "aws": "aws",
    "amazon web services": "aws",
    "azure": "azure",
    "gcp": "gcp",
    "google cloud": "gcp",
    "google cloud platform": "gcp",
    "devops": "devops",
    "ci/cd": "devops",
    "docker": "docker",
    "kubernetes": "kubernetes",
    "k8s": "kubernetes",
    "terraform": "terraform",
    "ansible": "ansible",
    "jenkins": "jenkins",
    # Web development
    "react": "react",
    "reactjs": "react",
    "react.js": "react",
    "angular": "angular",
    "angularjs": "angular",
    "vue": "vuejs",
    "vue.js": "vuejs",
    "vuejs": "vuejs",
    "nextjs": "nextjs",
    "next.js": "nextjs",
    "django": "django",
    "flask": "flask",
    "fastapi": "fastapi",
    "express": "expressjs",
    "spring": "spring",
    "spring boot": "spring",
    "spring_boot": "spring",
    "springboot": "spring",
    "rest api": "rest_api",
    "restful": "rest_api",
    "graphql": "graphql",
    "html": "html",
    "html5": "html",
    "css": "css",
    "css3": "css",
    "bootstrap": "bootstrap",
    # Mobile
    "android": "android",
    "ios": "ios",
    "react native": "react_native",
    "flutter": "flutter",
    "kotlin": "kotlin",
    "swift": "swift",
    # Tools & practices
    "git": "git",
    "github": "git",
    "gitlab": "git",
    "linux": "linux",
    "unix": "linux",
    "agile": "agile",
    "scrum": "agile",
    "jira": "jira",
    "testing": "testing",
    "tdd": "testing",
    "unit testing": "testing",
    "selenium": "selenium",
    "tableau": "tableau",
    "power bi": "power_bi",
    "powerbi": "power_bi",
    "excel": "excel",
    "ms excel": "excel",
    # Misc
    "communication": "communication",
    "problem solving": "problem_solving",
    "problem-solving": "problem_solving",
    "leadership": "leadership",
    "teamwork": "teamwork",
    "team work": "teamwork",
}

# ---------------------------------------------------------------------------
# Role normalization dictionary
# ---------------------------------------------------------------------------
ROLE_NORM: Dict[str, str] = {
    # Software engineering
    "software engineer": "software_engineer",
    "software developer": "software_engineer",
    "software development engineer": "software_engineer",
    "sde": "software_engineer",
    "sde-1": "software_engineer",
    "sde-2": "software_engineer",
    "developer": "software_engineer",
    "programmer": "software_engineer",
    "backend developer": "backend_developer",
    "backend engineer": "backend_developer",
    "front end developer": "frontend_developer",
    "frontend developer": "frontend_developer",
    "front-end developer": "frontend_developer",
    "full stack developer": "fullstack_developer",
    "fullstack developer": "fullstack_developer",
    "full-stack developer": "fullstack_developer",
    "full stack engineer": "fullstack_developer",
    # Data
    "data analyst": "data_analyst",
    "business analyst": "data_analyst",
    "data scientist": "data_scientist",
    "data engineer": "data_engineer",
    "big data analyst": "data_engineer",
    "big data engineer": "data_engineer",
    "analytics engineer": "data_engineer",
    "ml engineer": "ml_engineer",
    "machine learning engineer": "ml_engineer",
    "ai engineer": "ml_engineer",
    "research scientist": "research_scientist",
    "applied scientist": "research_scientist",
    # DevOps & Infra
    "devops engineer": "devops_engineer",
    "cloud engineer": "cloud_engineer",
    "site reliability engineer": "devops_engineer",
    "sre": "devops_engineer",
    "infrastructure engineer": "devops_engineer",
    "platform engineer": "devops_engineer",
    # Leadership
    "senior software engineer": "senior_software_engineer",
    "lead software engineer": "senior_software_engineer",
    "principal engineer": "senior_software_engineer",
    "staff engineer": "senior_software_engineer",
    "tech lead": "tech_lead",
    "technical lead": "tech_lead",
    "engineering manager": "engineering_manager",
    "product manager": "product_manager",
    "project manager": "project_manager",
    # QA
    "qa engineer": "qa_engineer",
    "quality assurance engineer": "qa_engineer",
    "test engineer": "qa_engineer",
    "sdet": "qa_engineer",
    # Design
    "ui/ux designer": "ui_ux_designer",
    "ux designer": "ui_ux_designer",
    "product designer": "ui_ux_designer",
    # Database
    "database administrator": "dba",
    "dba": "dba",
    "database engineer": "dba",
    # Security
    "security engineer": "security_engineer",
    "cybersecurity analyst": "security_engineer",
    "information security analyst": "security_engineer",
    # Generic
    "intern": "intern",
    "software intern": "intern",
    "engineer": "software_engineer",
    "analyst": "analyst",
    "consultant": "consultant",
    "architect": "software_architect",
    "solutions architect": "software_architect",
}

# Education domain mapping
EDU_DOMAIN_MAP: Dict[str, str] = {
    "computer science": "software",
    "computer engineering": "software",
    "software engineering": "software",
    "information technology": "software",
    "it": "software",
    "information systems": "software",
    "data science": "data_science",
    "statistics": "data_science",
    "mathematics": "data_science",
    "maths": "data_science",
    "electronics": "hardware",
    "electrical engineering": "hardware",
    "electrical": "hardware",
    "mechanical engineering": "engineering",
    "civil engineering": "engineering",
    "chemical engineering": "engineering",
    "business": "business",
    "management": "business",
    "mba": "business",
    "finance": "finance",
    "economics": "finance",
    "marketing": "marketing",
    "communication": "communication",
    "physics": "science",
    "chemistry": "science",
    "biology": "science",
    "biomedical": "biomedical",
    "bioinformatics": "biomedical",
}

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _safe_parse_list(raw: Any) -> List[Any]:
    """Parse a Python-literal list string like "['a', 'b']" safely."""
    if not raw or (isinstance(raw, float)):
        return []
    if isinstance(raw, list):
        return raw
    s = str(raw).strip()
    if not s or s in ("[]", "None", "nan"):
        return []
    try:
        result = ast.literal_eval(s)
        if isinstance(result, list):
            return result
        return [result]
    except Exception:
        # Fall back: split by comma after stripping brackets
        s = s.strip("[]").replace("'", "").replace('"', "")
        return [x.strip() for x in s.split(",") if x.strip()]


def _flatten(nested: Any) -> List[str]:
    """Flatten nested lists like [['Big Data'], ['Python']] → ['Big Data', 'Python']."""
    result = []
    if not isinstance(nested, list):
        return result
    for item in nested:
        if isinstance(item, list):
            result.extend(_flatten(item))
        elif item is not None and str(item).strip():
            result.append(str(item).strip())
    return result


def _normalize_text(text: str) -> str:
    """Lowercase, strip accents, collapse whitespace, remove non-alphanumeric."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower().strip()
    return text


def _normalize_skill(raw: str) -> str:
    """Apply normalization dictionary, then clean."""
    key = _normalize_text(raw)
    # Direct lookup
    if key in SKILL_NORM:
        return SKILL_NORM[key]
    # Partial match (prefix)
    for k, v in SKILL_NORM.items():
        if key.startswith(k) or k.startswith(key):
            if len(key) > 2:  # Avoid overly short matches
                return v
    # Fallback: clean the key
    key = re.sub(r"[^a-z0-9_]", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    return key


def _normalize_role(raw: str) -> str:
    """Normalize a role title to a canonical string."""
    key = _normalize_text(raw).strip()
    # Direct lookup
    if key in ROLE_NORM:
        return ROLE_NORM[key]
    # Partial match (longest prefix wins)
    best: Tuple[int, str] = (0, key.replace(" ", "_"))
    for k, v in ROLE_NORM.items():
        if k in key or key in k:
            if len(k) > best[0]:
                best = (len(k), v)
    if best[0] > 0:
        return best[1]
    # Fallback: clean
    key = re.sub(r"[^a-z0-9_]", "_", key)
    key = re.sub(r"_+", "_", key).strip("_")
    return key or "unknown"


def _parse_date(raw: str) -> Optional[datetime]:
    """Try to parse varied date strings; return None if unparseable."""
    if not raw:
        return None
    s = raw.strip()
    if s.lower() in ("till date", "present", "current", "na", "n/a", "", "none"):
        return datetime(2099, 1, 1)  # Sentinel: ongoing
    for fmt in ("%b %Y", "%B %Y", "%Y-%m", "%m/%Y", "%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _education_domain(major_fields: List[str]) -> str:
    """Map major field of study to a career domain."""
    for field in major_fields:
        key = _normalize_text(field)
        for k, v in EDU_DOMAIN_MAP.items():
            if k in key:
                return v
    return "other"

# ---------------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------------

class ResumeProfileProcessor:
    """Transforms raw CSV resume rows into structured career profiles."""

    MIN_SKILLS = 2   # Minimum skills to keep profile
    MIN_ROLES = 1    # Minimum roles to keep profile (relaxed — some CVs only have 1)

    def __init__(self, input_path: Path, output_dir: Path):
        self.input_path = input_path
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._processed = 0
        self._skipped = 0
        self._failed = 0

    # ------------------------------------------------------------------
    # Steps 3: Skill extraction
    # ------------------------------------------------------------------

    def _extract_skills(self, row: Dict[str, str]) -> List[str]:
        # Combine skills and related_skils_in_job
        raw_skills = _safe_parse_list(row.get("skills", ""))
        raw_related = _safe_parse_list(row.get("related_skils_in_job", ""))
        raw_required = _safe_parse_list(row.get("skills_required", ""))

        all_raw = list(raw_skills) + _flatten(raw_related) + list(raw_required)

        # Further split by comma in case items are comma-separated strings
        expanded = []
        for item in all_raw:
            if item:
                parts = [p.strip() for p in str(item).split(",") if p.strip()]
                expanded.extend(parts)

        # Normalize and deduplicate
        seen = set()
        skills = []
        for s in expanded:
            norm = _normalize_skill(s)
            if norm and norm not in seen and len(norm) > 1:
                seen.add(norm)
                skills.append(norm)

        return skills

    # ------------------------------------------------------------------
    # Steps 4+5: Role extraction and career trajectory
    # ------------------------------------------------------------------

    def _extract_roles_chronological(self, row: Dict[str, str]) -> List[Dict]:
        """
        Returns a list of {role, start, end} dicts sorted by start date.
        """
        positions = _safe_parse_list(row.get("positions", ""))
        start_dates = _safe_parse_list(row.get("start_dates", ""))
        end_dates = _safe_parse_list(row.get("end_dates", ""))

        entries = []
        for i, pos in enumerate(positions):
            if not pos or str(pos).strip().lower() in ("none", "n/a", ""):
                continue
            norm_role = _normalize_role(str(pos))
            start_raw = start_dates[i] if i < len(start_dates) else None
            end_raw = end_dates[i] if i < len(end_dates) else None
            start_dt = _parse_date(str(start_raw) if start_raw else "")
            end_dt = _parse_date(str(end_raw) if end_raw else "")
            entries.append({
                "role": norm_role,
                "start": start_dt,
                "end": end_dt,
            })

        # Sort chronologically by start date (None last)
        entries.sort(key=lambda e: e["start"] or datetime.max)
        return entries

    # ------------------------------------------------------------------
    # Step 6: Experience estimation
    # ------------------------------------------------------------------

    def _estimate_experience(self, role_count: int) -> str:
        if role_count <= 1:
            return "entry"
        elif role_count <= 3:
            return "mid"
        else:
            return "senior"

    # ------------------------------------------------------------------
    # Step 7: Domain enrichment
    # ------------------------------------------------------------------

    def _enrich(self, row: Dict[str, str]) -> Tuple[str, List[str]]:
        """Returns (education_domain, companies_list)."""
        majors = _safe_parse_list(row.get("major_field_of_studies", ""))
        domain = _education_domain(majors)
        companies_raw = _safe_parse_list(row.get("professional_company_names", ""))
        companies = [
            _normalize_text(str(c)) for c in companies_raw
            if c and str(c).strip().lower() not in ("none", "n/a", "")
        ]
        return domain, list(dict.fromkeys(companies))  # preserve order, dedup

    # ------------------------------------------------------------------
    # Main: process a single row
    # ------------------------------------------------------------------

    def _process_row(self, row: Dict[str, str], row_idx: int) -> Optional[Dict[str, Any]]:
        # Step 3: Skills
        skills = self._extract_skills(row)
        if len(skills) < self.MIN_SKILLS:
            self._skipped += 1
            return None

        # Steps 4+5: Roles & trajectory
        role_entries = self._extract_roles_chronological(row)
        roles = [e["role"] for e in role_entries]
        trajectory = list(dict.fromkeys(roles))  # ordered unique

        # Optional: include job_position_name (target role) if present
        # Handle BOM in column name
        job_col = "\ufeffjob_position_name"
        job_pos = row.get(job_col) or row.get("job_position_name", "")
        if job_pos and job_pos.strip():
            norm_target = _normalize_role(job_pos.strip())
            if norm_target and norm_target != "unknown":
                roles.append(f"[target] {norm_target}")

        # Step 8: Filter
        if not roles and not trajectory:
            self._skipped += 1
            return None

        # Step 6: Experience
        experience_level = self._estimate_experience(len(role_entries))

        # Step 7: Enrichment
        education_domain, companies = self._enrich(row)

        # Step 9: Build structured profile
        profile_id = f"resume_{row_idx:05d}"
        return {
            "id": profile_id,
            "skills": skills,
            "roles": roles,
            "career_trajectory": trajectory,
            "experience_level": experience_level,
            "companies": companies,
            "education_domain": education_domain,
        }

    # ------------------------------------------------------------------
    # Step 1+10: Load and run full pipeline
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info(f"=== Resume Profile Processor | Input: {self.input_path} ===")

        all_profiles = []

        with open(self.input_path, encoding="utf-8-sig") as f:  # utf-8-sig strips BOM
            reader = csv.DictReader(f)
            rows = list(reader)

        total = len(rows)
        logger.info(f"  Total rows: {total}")

        for idx, row in enumerate(rows):
            try:
                profile = self._process_row(row, idx)
                if profile is None:
                    continue

                all_profiles.append(profile)

                # Save individual file
                out_path = self.output_dir / f"{profile['id']}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(profile, f, indent=2, ensure_ascii=False)

                self._processed += 1
                if self._processed % 500 == 0:
                    logger.info(f"  Progress: {self._processed} profiles saved (row {idx+1}/{total})")

            except Exception as e:
                logger.error(f"Error on row {idx}: {e}")
                self._failed += 1

        # Save consolidated master file
        master_path = self.output_dir / "_all_profiles.json"
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(all_profiles, f, indent=2, ensure_ascii=False)

        logger.info("=== Resume Processing Complete ===")
        logger.info(f"  Processed : {self._processed}")
        logger.info(f"  Skipped   : {self._skipped}")
        logger.info(f"  Failed    : {self._failed}")
        logger.info(f"  Output    : {self.output_dir.resolve()}")
        logger.info(f"  Master    : {master_path.resolve()}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume Profile Processor")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/raw/resumes/resume_data.csv"),
        help="Path to the raw resume CSV file",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/processed/resume_profiles"),
        help="Output directory for processed resume profiles",
    )
    args = parser.parse_args()

    processor = ResumeProfileProcessor(input_path=args.input, output_dir=args.output)
    processor.run()
