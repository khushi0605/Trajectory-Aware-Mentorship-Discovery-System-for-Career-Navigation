"""
profile_matcher.py
------------------
Matches each processed GitHub profile to the most compatible resume profile
via persona alignment — finding the resume that best explains the GitHub activity.

Scoring formula (weighted):
  score = 0.5 * skill_similarity
        + 0.3 * domain_similarity   ← skill-based Jaccard (top-N weighted skills)
        + 0.2 * experience_alignment

Identity classification:
  strong   → score >= 0.75   (use_for_unification = True)
  moderate → score  0.50–0.74 (use_for_unification = True)
  weak     → score <  0.50   (use_for_unification = False)

Confidence:
  high   → score > 0.75
  medium → score 0.50–0.75
  low    → score < 0.50

Performance:
  Builds a (R × V) numpy skill matrix; uses vectorised dot products to
  shortlist 200 candidates per GitHub profile before full scoring.

Usage:
  PYTHONPATH=. python3 src/processing/profile_matcher.py
"""

import argparse
import json
import logging
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/profile_matcher.log", mode="a"),
    ],
)
logger = logging.getLogger("profile_matcher")
Path("logs").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Experience level ordering
# ---------------------------------------------------------------------------
# Maps both GitHub and Resume level strings to a numeric tier 0–4
_EXP_TIER: Dict[str, int] = {
    # GitHub levels
    "beginner": 0,
    "entry": 0,
    "intermediate": 1,
    "mid": 1,
    # Resume levels
    "senior": 2,
    "advanced": 2,
}

def _exp_tier(level: str) -> int:
    return _EXP_TIER.get((level or "").lower().strip(), 1)  # default mid


# (No project-domain lookup tables needed — domain similarity is now
#  derived purely from skill overlap, which is more robust.)


def _domain_set(domain_str: str) -> set:  # kept for potential future use
    return {domain_str}


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def _load_json_dir(directory: Path, skip_prefix: str = "_") -> List[Dict]:
    profiles = []
    for fpath in sorted(directory.glob("*.json")):
        if fpath.name.startswith(skip_prefix):
            continue
        try:
            with open(fpath, encoding="utf-8") as f:
                profiles.append(json.load(f))
        except Exception as e:
            logger.warning(f"Skipping {fpath.name}: {e}")
    return profiles


# ---------------------------------------------------------------------------
# Scoring functions (modular as required)
# ---------------------------------------------------------------------------

def compute_skill_similarity(
    gh_weights: Dict[str, float],
    resume_skills: List[str],
) -> float:
    """
    Weighted overlap between GitHub skill_weights and resume skills list.

    For each skill in the resume that also appears in GitHub skill_weights,
    we sum the GitHub weight. This rewards resumes that have skills the
    GitHub profile is *strong* in, not just any skill overlap.

    Result is normalised by the total weight of all GitHub skills.

    Returns a float in [0, 1].
    """
    if not gh_weights or not resume_skills:
        return 0.0

    resume_skill_set = set(resume_skills)
    total_weight = sum(gh_weights.values()) or 1.0
    matched_weight = sum(w for skill, w in gh_weights.items() if skill in resume_skill_set)

    return min(matched_weight / total_weight, 1.0)


def compute_domain_similarity(
    gh_weights: Dict[str, float],
    resume_skills: List[str],
    top_n: int = 15,
) -> float:
    """
    Skill-based Jaccard similarity between the top-N GitHub skills (by weight)
    and the resume's skill set.

    Using skills directly is more robust than project-domain inference because
    GitHub project domains are often labelled 'general', losing domain signal.

    top_n : Number of highest-weighted GitHub skills to use as the comparison set.

    Returns a float in [0, 1].
    """
    if not gh_weights or not resume_skills:
        return 0.0

    # Take the top-N GitHub skills by weight
    sorted_skills = sorted(gh_weights.items(), key=lambda x: -x[1])
    gh_top_skills: set = {skill for skill, _ in sorted_skills[:top_n]}
    resume_skill_set: set = set(resume_skills)

    intersection = gh_top_skills & resume_skill_set
    union = gh_top_skills | resume_skill_set
    return len(intersection) / len(union) if union else 0.0


def compute_experience_alignment(
    gh_experience: str,
    resume_experience: str,
) -> float:
    """
    Maps both experience levels to numeric tiers and returns an alignment
    score based on tier distance.

    Tier distance → score:
       0 (exact match) → 1.0
       1 (adjacent)    → 0.5
       2 (far apart)   → 0.0 (heavy penalty for large mismatches)

    Returns a float in [0, 1].
    """
    gh_tier = _exp_tier(gh_experience)
    res_tier = _exp_tier(resume_experience)
    distance = abs(gh_tier - res_tier)

    if distance == 0:
        return 1.0
    elif distance == 1:
        return 0.5
    else:
        return 0.0  # e.g., advanced GitHub vs entry resume


def _composite_score(
    skill_sim: float,
    domain_sim: float,
    exp_align: float,
) -> float:
    return round(0.5 * skill_sim + 0.3 * domain_sim + 0.2 * exp_align, 4)


def _identity_type(score: float) -> str:
    """Classify the match strength as strong / moderate / weak."""
    if score >= 0.75:
        return "strong"
    elif score >= 0.50:
        return "moderate"
    else:
        return "weak"


def _confidence(score: float) -> str:
    if score > 0.75:
        return "high"
    elif score >= 0.50:
        return "medium"
    else:
        return "low"


# ---------------------------------------------------------------------------
# Vectorized batch matching
# ---------------------------------------------------------------------------

class ProfileMatcher:
    """
    Matches every GitHub profile to the single best-fitting resume profile.

    Vectorization strategy:
      1. Build a global skill vocabulary (all skills seen across both datasets).
      2. Represent each resume as a binary membership vector over the vocab.
      3. For each GitHub profile, compute weighted skill score as a dot product
         against all resume vectors simultaneously using numpy.
      4. Domain similarity and experience alignment are computed per-candidate
         only for the top-K shortlisted resumes (K=200) — this keeps the
         expensive Python loops short.
    """

    TOP_K = 200  # Shortlist candidates from skill score before full scoring

    def __init__(
        self,
        gh_dir: Path,
        resume_dir: Path,
        output_dir: Path,
    ):
        self.gh_dir = gh_dir
        self.resume_dir = resume_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _build_resume_matrix(
        self, resumes: List[Dict]
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Returns:
          matrix (R × V) — binary skill membership for each resume
          vocab  (list of V skills)
        """
        # Build vocabulary from all resume skills
        all_skills: set = set()
        for res in resumes:
            all_skills.update(res.get("skills", []))
        vocab = sorted(all_skills)
        skill_idx = {s: i for i, s in enumerate(vocab)}
        V = len(vocab)
        R = len(resumes)

        matrix = np.zeros((R, V), dtype=np.float32)
        for r_idx, res in enumerate(resumes):
            for skill in res.get("skills", []):
                if skill in skill_idx:
                    matrix[r_idx, skill_idx[skill]] = 1.0

        return matrix, vocab, skill_idx

    def _gh_weight_vector(
        self, gh_weights: Dict[str, float], skill_idx: Dict[str, int], V: int
    ) -> np.ndarray:
        """Convert a GitHub skill_weights dict to a dense weight vector."""
        vec = np.zeros(V, dtype=np.float32)
        total = sum(gh_weights.values()) or 1.0
        for skill, w in gh_weights.items():
            if skill in skill_idx:
                vec[skill_idx[skill]] = w / total  # normalise by total weight
        return vec

    def run(self) -> None:
        t0 = time.time()
        logger.info("=== Profile Matcher started ===")

        # -- Load data --
        logger.info("Loading GitHub profiles…")
        gh_profiles = _load_json_dir(self.gh_dir)
        logger.info("Loading resume profiles…")
        resume_profiles = _load_json_dir(self.resume_dir)
        logger.info(f"  GitHub : {len(gh_profiles)} | Resumes: {len(resume_profiles)}")

        if not gh_profiles or not resume_profiles:
            logger.error("Missing profile data. Aborting.")
            return

        # -- Build resume matrix --
        logger.info("Building resume skill matrix…")
        res_matrix, vocab, skill_idx = self._build_resume_matrix(resume_profiles)
        # Pre-index resume fields for fast access
        resume_roles_list = [r.get("roles", []) for r in resume_profiles]
        resume_traj_list = [r.get("career_trajectory", []) for r in resume_profiles]
        resume_exp_list = [r.get("experience_level", "mid") for r in resume_profiles]
        resume_ids = [r.get("id", f"resume_{i:05d}") for i, r in enumerate(resume_profiles)]
        V = len(vocab)

        matched = 0
        failed = 0
        identity_counts: Dict[str, int] = {"strong": 0, "moderate": 0, "weak": 0}
        conf_counts: Dict[str, int] = {"high": 0, "medium": 0, "low": 0}

        logger.info("Matching github profiles to resumes…")

        for gh_idx, gh in enumerate(gh_profiles):
            try:
                username = gh.get("username", f"gh_{gh_idx}")
                gh_weights = gh.get("skill_weights", {})
                gh_projects = gh.get("projects", [])
                gh_exp = gh.get("experience_estimate", "intermediate")

                # -- Step 1: Fast skill similarity via dot product --
                gh_vec = self._gh_weight_vector(gh_weights, skill_idx, V)
                # dot product → (R,) array of raw skill scores
                raw_skill_scores = res_matrix.dot(gh_vec)

                # Shortlist top-K by raw skill score
                top_k_indices = np.argpartition(raw_skill_scores, -self.TOP_K)[-self.TOP_K:]
                top_k_indices = top_k_indices[np.argsort(raw_skill_scores[top_k_indices])[::-1]]

                # -- Step 2: Full scoring on shortlist --
                best_score = -1.0
                best_idx = int(top_k_indices[0])

                for r_idx in top_k_indices:
                    r_idx = int(r_idx)

                    # Skill similarity (proper weighted overlap)
                    skill_sim = compute_skill_similarity(
                        gh_weights,
                        resume_profiles[r_idx].get("skills", []),
                    )

                    # Domain similarity — skill-based Jaccard on top-N weights
                    domain_sim = compute_domain_similarity(
                        gh_weights,
                        resume_profiles[r_idx].get("skills", []),
                    )

                    # Experience alignment
                    exp_align = compute_experience_alignment(
                        gh_exp,
                        resume_exp_list[r_idx],
                    )

                    score = _composite_score(skill_sim, domain_sim, exp_align)

                    if score > best_score:
                        best_score = score
                        best_idx = r_idx
                        best_features = {
                            "skill_similarity": round(skill_sim, 4),
                            "domain_similarity": round(domain_sim, 4),
                            "experience_alignment": round(exp_align, 4),
                        }

                identity = _identity_type(best_score)
                confidence = _confidence(best_score)
                identity_counts[identity] += 1
                conf_counts[confidence] += 1

                result = {
                    "github_id": username,
                    "matched_resume_id": resume_ids[best_idx],
                    "match_score": best_score,
                    "matching_features": best_features,
                    "identity_type": identity,
                    "use_for_unification": best_score >= 0.5,
                    "confidence": confidence,
                }

                out_path = self.output_dir / f"{username}.json"
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)

                matched += 1

                if matched % 50 == 0 or matched == len(gh_profiles):
                    logger.info(f"  Progress: {matched}/{len(gh_profiles)} matched")

            except Exception as e:
                logger.error(f"Error matching {gh.get('username', gh_idx)}: {e}")
                failed += 1

        # -- Save consolidated results --
        all_results = []
        for fpath in sorted(self.output_dir.glob("*.json")):
            if fpath.name.startswith("_"):
                continue
            try:
                with open(fpath) as f:
                    all_results.append(json.load(f))
            except Exception:
                pass

        master_path = self.output_dir / "_all_matches.json"
        with open(master_path, "w", encoding="utf-8") as f:
            json.dump(all_results, f, indent=2)

        elapsed = time.time() - t0
        logger.info("=== Matching Complete ===")
        logger.info(f"  Matched        : {matched}")
        logger.info(f"  Failed         : {failed}")
        logger.info(f"  Time           : {elapsed:.2f}s")
        logger.info(f"  Identity types : {identity_counts}")
        logger.info(f"  Confidence     : {conf_counts}")
        useful = sum(1 for r in all_results if r.get("use_for_unification"))
        logger.info(f"  For unification: {useful}/{matched} profiles ({100*useful//max(matched,1)}%)")
        logger.info(f"  Output         : {self.output_dir.resolve()}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub ↔ Resume Profile Matcher")
    parser.add_argument("--github",  type=Path, default=Path("data/processed/github_profiles"))
    parser.add_argument("--resumes", type=Path, default=Path("data/processed/resume_profiles"))
    parser.add_argument("--output",  type=Path, default=Path("data/processed/matched_profiles"))
    args = parser.parse_args()

    matcher = ProfileMatcher(
        gh_dir=args.github,
        resume_dir=args.resumes,
        output_dir=args.output,
    )
    matcher.run()
