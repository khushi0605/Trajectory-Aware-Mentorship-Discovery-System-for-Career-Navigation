"""
skill_normalizer.py
-------------------
Cleans, standardizes, and normalizes raw skill data from unified profiles
to produce high-quality, semantically meaningful representations.

Operations applied to each profile:
  1. Skill Cleaning      : Removes <3 chars, numerics, and generic stopwords.
  2. Whitelist Validation: Retains only skills in `skills_taxonomy.json`.
  3. Sqrt Smoothing      : Applies sqrt to weights before normalization to
                           prevent single-skill dominance (e.g., rust: 0.85).
  4. Importance Adjustment: Boosts core tech / penalizes soft skills.
  5. Sum-to-1 Normalization: Re-scales all retained weights to sum to 1.0.
  6. Deduplication       : Merges dictionary keys if normalization creates dupes.
  7. Domain Inference    : Infers top 2–3 domains via weighted scoring against
                           `domain_map.json` (runs AFTER smoothing).
  8. Project Tool Normalization: Runs the same clean/alias/taxonomy pipeline
                           on each project's `tools` list.

Usage:
  PYTHONPATH=. python3 src/processing/skill_normalizer.py
"""

import argparse
import json
import logging
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/skill_normalizer.log", mode="a"),
    ],
)
logger = logging.getLogger("skill_normalizer")
Path("logs").mkdir(exist_ok=True)


class SkillNormalizer:
    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        taxonomy_path: Path,
        domain_map_path: Path,
        stopwords_path: Path,
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Load reference files
        self.taxonomy: Set[str] = self._load_taxonomy(taxonomy_path)
        self.domain_map: Dict[str, str] = self._load_domain_map(domain_map_path)
        self.stopwords: Set[str] = self._load_stopwords(stopwords_path)

        # Shared alias / synonym map (used for both skills AND project tools)
        self.aliases: Dict[str, str] = {
            "js":      "javascript",
            "ts":      "typescript",
            "py":      "python",
            "ml":      "machine_learning",
            "ai":      "artificial_intelligence",
            "reactjs": "react",
            "nodejs":  "nodejs",
            "k8s":     "kubernetes",
        }

        # Domain to role mapping
        self.domain_to_role: Dict[str, str] = {
            "machine_learning": "ml_engineer",
            "web_dev": "frontend_engineer",
            "backend": "backend_engineer",
            "systems": "systems_engineer",
            "cloud_devops": "devops_engineer",
            "data_engineering": "data_engineer",
            "mobile_dev": "mobile_engineer",
            "security": "security_engineer"
        }

        # Metrics
        self.total_profiles       = 0
        self.skills_in            = 0
        self.skills_out           = 0
        self.skills_removed       = 0
        self.tools_removed        = 0
        self.domain_counts: List[int] = []
        self.max_weight_before: List[float] = []
        self.max_weight_after:  List[float] = []

    # -----------------------------------------------------------------------
    # Reference file loaders
    # -----------------------------------------------------------------------

    def _load_taxonomy(self, path: Path) -> Set[str]:
        if not path.exists():
            logger.warning(f"Taxonomy file {path} not found. Whitelist disabled.")
            return set()
        with open(path, "r", encoding="utf-8") as f:
            return {s.strip().lower() for s in json.load(f)}

    def _load_domain_map(self, path: Path) -> Dict[str, str]:
        if not path.exists():
            logger.warning(f"Domain map file {path} not found. Domain inference disabled.")
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return {k.strip().lower(): v.strip().lower() for k, v in json.load(f).items()}

    def _load_stopwords(self, path: Path) -> Set[str]:
        if not path.exists():
            logger.warning(f"Stopwords file {path} not found.")
            return set()
        with open(path, "r", encoding="utf-8") as f:
            return {line.strip().lower() for line in f if line.strip()}

    # -----------------------------------------------------------------------
    # Shared cleaning helpers  (used by BOTH skill pipeline & tool pipeline)
    # -----------------------------------------------------------------------

    def _clean_name(self, raw: str) -> str:
        """
        Normalizes a skill or tool name:
          - Lowercase
          - Replace dashes / spaces with underscores
          - Strip special chars (except underscore)
        """
        s = raw.lower().strip()
        s = re.sub(r"[\s\-]+", "_", s)
        s = re.sub(r"[^a-z0-9_]", "", s)
        return s

    def _is_valid_skill(self, skill: str) -> bool:
        """Heuristic validation used in the SKILL pipeline."""
        # Allow important single/two-char tokens explicitly
        SHORT_ALLOW = {"c", "r", "go", "js", "ts", "ui", "ux", "qa"}
        if len(skill) <= 2 and skill not in SHORT_ALLOW:
            return False
        if skill.isnumeric():
            return False
        if skill in self.stopwords:
            return False
        # Whitelist enforcement (no-op when taxonomy is empty)
        if self.taxonomy and skill not in self.taxonomy:
            return False
        return True

    def _adjust_weight(self, skill: str, weight: float) -> float:
        """
        Optional heuristic weight adjustment.
        Applied BEFORE sqrt smoothing so it biases relative ratios, not
        the absolute scale that smoothing will flatten anyway.
        """
        boosts = {
            "python": 1.1, "java": 1.1, "go": 1.1, "rust": 1.1, "cpp": 1.1,
            "react": 1.1, "aws": 1.1, "machine_learning": 1.1, "system_design": 1.1,
        }
        penalties = {
            "html": 0.8, "css": 0.8, "git": 0.8, "github": 0.8,
            "agile": 0.5, "scrum": 0.5, "jira": 0.5,
        }
        multiplier = boosts.get(skill, penalties.get(skill, 1.0))
        return weight * multiplier

    # -----------------------------------------------------------------------
    # Domain inference  (weighted scoring → top 2–3 domains)
    # -----------------------------------------------------------------------

    def _infer_domains(self, skills: Dict[str, float]) -> List[str]:
        """
        Compute domain scores by summing skill weights that map to each domain.
        Returns the top 2–3 domains sorted by accumulated weight (descending).

        Running on POST-smoothed weights ensures the scores reflect the
        redistributed, de-dominated weight distribution.
        """
        domain_score: Dict[str, float] = defaultdict(float)

        for skill, weight in skills.items():
            domain = self.domain_map.get(skill)
            if domain:
                domain_score[domain] += weight

        # Sort and take top 2–3
        top_domains = sorted(domain_score.items(), key=lambda x: x[1], reverse=True)[:3]

        domain_names = [d for d, _ in top_domains]
        return domain_names if domain_names else ["general"]

    # -----------------------------------------------------------------------
    # Role inference
    # -----------------------------------------------------------------------

    def _infer_roles(self, domains: List[str]) -> List[str]:
        """
        Infer up to 2 professional roles based on the top domains.
        Returns a deduplicated list of roles.
        """
        roles = []
        # Take the top 2 domains at most
        for domain in domains[:2]:
            role = self.domain_to_role.get(domain)
            if role and role not in roles:
                roles.append(role)
        return roles

    # -----------------------------------------------------------------------
    # Project tool normalization  (same pipeline as skills, no weight logic)
    # -----------------------------------------------------------------------

    def _normalize_tools(self, tool_list: List[str]) -> List[str]:
        """
        Runs the clean → alias → taxonomy-filter pipeline on a project's
        tool list. Returns deduplicated, validated tool names.
        """
        cleaned: List[str] = []
        for raw_tool in tool_list:
            if not isinstance(raw_tool, str):
                continue
            tool = self._clean_name(raw_tool)
            tool = self.aliases.get(tool, tool)  # synonym mapping

            # Taxonomy filter (same whitelist as skills)
            if self.taxonomy and tool not in self.taxonomy:
                self.tools_removed += 1
                continue
            # Basic noise filter: drop pure numerics & very short tokens
            if tool.isnumeric() or (len(tool) <= 2 and tool not in {"c", "r", "go"}):
                self.tools_removed += 1
                continue

            cleaned.append(tool)

        return list(dict.fromkeys(cleaned))  # preserve order, deduplicate

    # -----------------------------------------------------------------------
    # Core profile processing
    # -----------------------------------------------------------------------

    def process_profile(self, profile: Dict) -> Dict:
        raw_skills: Dict = profile.get("skills") or {}
        self.skills_in += len(raw_skills)

        # ── Step 1: Clean, alias, validate, and merge raw skills ────────────
        merged_skills: Dict[str, float] = {}

        for raw_name, weight in raw_skills.items():
            # Ensure weight is a positive float; default 1.0 for missing/zero
            try:
                weight = float(weight) if weight else 1.0
            except (TypeError, ValueError):
                weight = 1.0

            name = self._clean_name(raw_name)
            name = self.aliases.get(name, name)

            if not self._is_valid_skill(name):
                self.skills_removed += 1
                continue

            adj_weight = self._adjust_weight(name, weight)

            # Merge duplicate keys (e.g., "React" + "reactjs" both → "react")
            merged_skills[name] = merged_skills.get(name, 0.0) + adj_weight

        # ── Step 2: Sqrt smoothing to dampen dominant skills ────────────────
        if merged_skills:
            max_before = max(merged_skills.values())
            self.max_weight_before.append(max_before)

            smoothed_skills: Dict[str, float] = {
                skill: math.sqrt(weight)
                for skill, weight in merged_skills.items()
            }

            # ── Step 3: Sum-to-1 normalization ──────────────────────────────
            total = sum(smoothed_skills.values())
            normalized_skills: Dict[str, float] = {
                skill: round(w / total, 4)
                for skill, w in smoothed_skills.items()
            }

            max_after = max(normalized_skills.values())
            self.max_weight_after.append(max_after)
        else:
            normalized_skills = {}

        # ── Step 4: Sort by weight descending ───────────────────────────────
        sorted_skills: Dict[str, float] = dict(
            sorted(normalized_skills.items(), key=lambda x: x[1], reverse=True)
        )

        # ── Step 5: Domain inference on POST-smoothed weights ───────────────
        inferred_domains = self._infer_domains(sorted_skills)
        self.domain_counts.append(len(inferred_domains))

        # ── Step 6: Role inference from top domains ─────────────────────────
        inferred_roles = self._infer_roles(inferred_domains)

        # ── Step 7: Project tool normalization ──────────────────────────────
        projects: List[Dict] = profile.get("projects") or []
        for project in projects:
            raw_tools = project.get("tools") or []
            project["tools"] = self._normalize_tools(raw_tools)

        # ── Step 8: Write back to profile (non-destructive for other keys) ──
        profile["skills"]  = sorted_skills
        profile["domains"] = inferred_domains
        profile["roles"]   = inferred_roles
        profile["projects"] = projects
        self.skills_out += len(sorted_skills)

        return profile

    # -----------------------------------------------------------------------
    # Batch runner
    # -----------------------------------------------------------------------

    def run(self) -> None:
        logger.info("=== Skill Normalizer started ===")

        in_files = list(self.input_dir.glob("user_*.json"))
        if not in_files:
            logger.error(f"No profiles found in {self.input_dir}")
            return

        all_normalized: List[Dict] = []

        for idx, fpath in enumerate(in_files, 1):
            with open(fpath, "r", encoding="utf-8") as f:
                profile = json.load(f)

            norm_profile = self.process_profile(profile)
            all_normalized.append(norm_profile)

            out_path = self.output_dir / fpath.name
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(norm_profile, f, indent=2)

            self.total_profiles += 1
            if idx % 100 == 0:
                logger.info(f"  Processed {idx}/{len(in_files)} profiles…")

        # Save master list
        master_path = self.output_dir / "_all_normalized.json"
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(all_normalized, f, indent=2)

        # ── Summary metrics ─────────────────────────────────────────────────
        n = max(1, self.total_profiles)
        reduction_pct = (self.skills_removed / max(1, self.skills_in)) * 100
        avg_domains   = sum(self.domain_counts) / max(1, len(self.domain_counts))
        avg_max_before = sum(self.max_weight_before) / max(1, len(self.max_weight_before))
        avg_max_after  = sum(self.max_weight_after)  / max(1, len(self.max_weight_after))

        logger.info("=== Normalization Complete ===")
        logger.info(f"  Profiles processed       : {self.total_profiles}")
        logger.info(f"  Skills analyzed          : {self.skills_in}")
        logger.info(f"  Skills retained          : {self.skills_out}")
        logger.info(f"  Skills removed           : {self.skills_removed} ({reduction_pct:.1f}% noise reduction)")
        logger.info(f"  Avg skills / profile     : {self.skills_out / n:.1f}")
        logger.info(f"  Avg domains / profile    : {avg_domains:.2f}  (target 2–3)")
        logger.info(f"  Avg max skill wt BEFORE  : {avg_max_before:.3f}  (raw dominance)")
        logger.info(f"  Avg max skill wt AFTER   : {avg_max_after:.3f}  (post-smoothing)")
        logger.info(f"  Project tools removed    : {self.tools_removed}")
        logger.info(f"  Output directory         : {self.output_dir.resolve()}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Skill Normalizer")
    parser.add_argument("--input",    type=Path, default=Path("data/processed/unified_profiles"))
    parser.add_argument("--output",   type=Path, default=Path("data/processed/normalized_profiles"))
    parser.add_argument("--taxonomy", type=Path, default=Path("data/reference/skills_taxonomy.json"))
    parser.add_argument("--domain",   type=Path, default=Path("data/reference/domain_map.json"))
    parser.add_argument("--stop",     type=Path, default=Path("data/reference/stopwords.txt"))
    args = parser.parse_args()

    normalizer = SkillNormalizer(
        input_dir=args.input,
        output_dir=args.output,
        taxonomy_path=args.taxonomy,
        domain_map_path=args.domain,
        stopwords_path=args.stop,
    )
    normalizer.run()
