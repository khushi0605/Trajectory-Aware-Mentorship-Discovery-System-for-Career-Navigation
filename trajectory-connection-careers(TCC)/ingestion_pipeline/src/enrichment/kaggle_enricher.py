"""
kaggle_enricher.py  (v2 — skill-similarity matching)
-----------------------------------------------------
Enrichment stage: Matches Kaggle processed profiles to unified
GitHub+resume profiles using cosine skill-vector similarity, then
merges their signals.

Since there is no shared identifier between the two datasets, identity
is inferred from skill overlap:

  Matching pipeline:
    1. Build a global skill vocabulary (union of all skills)
    2. Vectorize every profile as a sparse weight vector
    3. Pre-filter candidates with domain overlap (at least 1 shared domain)
    4. Compute cosine similarity for candidates only
    5. Accept matches ≥ 0.70, emit the highest-scoring pair per unified slot

  Merge pipeline (after match):
    skills     = (github × 0.6) + (kaggle × 0.4)  → top-15, sum=1
    domains    = union, top-5
    score      = github_score + log(1 + kaggle_score)
    confidence = (github × 0.6) + (kaggle × 0.4)

Data Flow:
  kaggle_processed_profiles.json
  + _all_normalized.json
        ↓  (this script)
  data/processed/unified/enriched_profiles.json

Usage:
  PYTHONPATH=. python3 src/enrichment/kaggle_enricher.py
"""

import argparse
import json
import logging
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/kaggle_enricher.log", mode="a"),
    ],
)
logger = logging.getLogger("kaggle_enricher")
Path("logs").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
KAGGLE_PROCESSED = Path("data/processed/kaggle/kaggle_processed_profiles.json")
UNIFIED_ALL      = Path("data/processed/normalized_profiles/_all_normalized.json")
OUT_DIR          = Path("data/processed/unified")
OUT_FILE         = OUT_DIR / "enriched_profiles.json"

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
GITHUB_WEIGHT        = 0.6
KAGGLE_WEIGHT        = 0.4
TOP_N_SKILLS         = 15
TOP_N_DOMAINS        = 5
STRONG_THRESHOLD     = 0.75
WEAK_THRESHOLD       = 0.65
ACCEPT_THRESHOLD     = 0.70
ML_DOMAINS: Set[str] = {"machine_learning", "nlp", "computer_vision", "data_analysis"}
TOP_CANDIDATES_K     = 3   # for bonus top_match_candidates field


# ===========================================================================
# 1. Load helpers
# ===========================================================================

def load_kaggle_profiles() -> List[Dict]:
    logger.info(f"Loading Kaggle processed profiles …")
    with open(KAGGLE_PROCESSED, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"  Loaded {len(data):,} Kaggle profiles")
    return data


def load_unified_profiles() -> List[Dict]:
    logger.info(f"Loading unified profiles …")
    with open(UNIFIED_ALL, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"  Loaded {len(data):,} unified profiles")
    return data


# ===========================================================================
# 2. Skill-vector infrastructure
# ===========================================================================

def build_skill_index(
    kaggle_profiles: List[Dict],
    unified_profiles: List[Dict],
) -> Dict[str, int]:
    """
    Build a global skill vocabulary: skill_name → column_index.
    Union of all skills from both datasets.
    """
    vocab: Dict[str, int] = {}
    for profile in kaggle_profiles + unified_profiles:
        for skill in profile.get("skills", {}):
            if skill not in vocab:
                vocab[skill] = len(vocab)
    logger.info(f"  Global skill vocabulary size: {len(vocab):,} skills")
    return vocab


def vectorize_skills(
    skills: Dict[str, float],
    vocab: Dict[str, int],
) -> List[float]:
    """
    Convert a {skill: weight} dict into a dense float vector aligned to `vocab`.
    Unknown skills (not in vocab) are ignored.
    """
    vec = [0.0] * len(vocab)
    for skill, weight in skills.items():
        idx = vocab.get(skill)
        if idx is not None:
            vec[idx] = float(weight)
    return vec


def _magnitude(vec: List[float]) -> float:
    return math.sqrt(sum(v * v for v in vec))


def compute_cosine_similarity(
    vec_a: List[float],
    vec_b: List[float],
    mag_a: float,
    mag_b: float,
) -> float:
    """
    Cosine similarity = dot(A,B) / (||A|| × ||B||).
    Accepts precomputed magnitudes to avoid redundant sqrt calls.
    """
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    return dot / (mag_a * mag_b)


# ===========================================================================
# 3. Domain-overlap pre-filter
# ===========================================================================

def build_domain_buckets(profiles: List[Dict]) -> Dict[str, List[int]]:
    """
    domain → [list of profile indices] for fast candidate lookup.
    """
    buckets: Dict[str, List[int]] = defaultdict(list)
    for i, p in enumerate(profiles):
        for d in p.get("domains", []):
            buckets[d].append(i)
    return buckets


def get_candidate_indices(
    kaggle_domains: List[str],
    unified_domain_buckets: Dict[str, List[int]],
) -> Set[int]:
    """
    Return the set of unified profile indices that share at least one domain
    with the given Kaggle profile.
    """
    candidates: Set[int] = set()
    for d in kaggle_domains:
        candidates.update(unified_domain_buckets.get(d, []))
    return candidates


# ===========================================================================
# 4. Matching
# ===========================================================================

def match_profiles(
    kaggle_profiles: List[Dict],
    unified_profiles: List[Dict],
    vocab: Dict[str, int],
) -> Dict[int, Tuple[int, float]]:
    """
    For each Kaggle profile, find the best-matching unified profile using:
      - Domain overlap pre-filtering
      - Cosine similarity on skill vectors

    Returns:
      A mapping  unified_idx → (kaggle_idx, similarity_score)
      Each unified slot is claimed by at most one Kaggle profile (1-to-1).
    """
    # Pre-vectorize unified profiles
    unified_vecs   = [vectorize_skills(p.get("skills", {}), vocab) for p in unified_profiles]
    unified_mags   = [_magnitude(v) for v in unified_vecs]

    # Build domain pre-filter buckets for unified profiles
    unified_buckets = build_domain_buckets(unified_profiles)

    # Track which unified slots are already claimed
    claimed: Dict[int, Tuple[int, float]] = {}          # unified_idx → (kaggle_idx, score)
    kaggle_to_best: Dict[int, Tuple[int, float]] = {}   # kaggle_idx  → (unified_idx, score)

    n_kaggle = len(kaggle_profiles)

    for ki, kp in enumerate(kaggle_profiles):
        if ki % 5000 == 0:
            logger.info(f"  Matching progress: {ki:,}/{n_kaggle:,}")

        k_domains  = kp.get("domains", [])
        k_vec      = vectorize_skills(kp.get("skills", {}), vocab)
        k_mag      = _magnitude(k_vec)

        if k_mag == 0.0:
            continue  # empty skill vector — nothing to compare

        candidates = get_candidate_indices(k_domains, unified_buckets)
        if not candidates:
            continue

        best_score = 0.0
        best_ui    = -1

        for ui in candidates:
            score = compute_cosine_similarity(k_vec, unified_vecs[ui], k_mag, unified_mags[ui])
            if score > best_score:
                best_score = score
                best_ui    = ui

        if best_ui == -1 or best_score < ACCEPT_THRESHOLD:
            continue

        # 1-to-1 constraint: a unified slot can only be claimed once (by highest scorer)
        existing = claimed.get(best_ui)
        if existing is None or best_score > existing[1]:
            claimed[best_ui] = (ki, round(best_score, 4))

    return claimed


# ===========================================================================
# 5. Merge helpers
# ===========================================================================

def merge_skills(
    github_skills: Dict[str, float],
    kaggle_skills: Dict[str, float],
) -> Dict[str, float]:
    all_keys = set(github_skills) | set(kaggle_skills)
    merged   = {
        sk: github_skills.get(sk, 0.0) * GITHUB_WEIGHT
            + kaggle_skills.get(sk, 0.0) * KAGGLE_WEIGHT
        for sk in all_keys
    }
    top    = sorted(merged.items(), key=lambda x: x[1], reverse=True)[:TOP_N_SKILLS]
    total  = sum(w for _, w in top)
    return {sk: round(w / total, 4) for sk, w in top} if total else {}


def merge_domains(
    github_domains: List[str],
    kaggle_domains: List[str],
) -> List[str]:
    seen: Set[str] = set()
    result: List[str] = []
    for d in list(github_domains) + list(kaggle_domains):
        if d not in seen:
            seen.add(d)
            result.append(d)
        if len(result) == TOP_N_DOMAINS:
            break
    return result


def merge_scores(unified: Dict, kaggle_score: float) -> Tuple[float, float, float]:
    gh_s      = float(unified.get("github_score", 0.0))
    normed_k  = round(math.log1p(kaggle_score), 4)
    overall   = round(gh_s + normed_k, 4)
    return gh_s, normed_k, overall


def merge_confidence(gh_conf: float, kag_conf: float) -> float:
    return round(GITHUB_WEIGHT * gh_conf + KAGGLE_WEIGHT * kag_conf, 4)


def domain_overlap_score(
    gh_domains: List[str],
    kag_domains: List[str],
) -> float:
    if not gh_domains or not kag_domains:
        return 0.0
    overlap = len(set(gh_domains) & set(kag_domains))
    union   = len(set(gh_domains) | set(kag_domains))
    return round(overlap / union, 4) if union else 0.0


def is_ml_heavy(skills: Dict[str, float]) -> bool:
    """True if > 50% of a profile's total skill weight is in ML domains."""
    ml_weight = sum(
        w for sk, w in skills.items()
        if sk in {
            "machine_learning", "deep_learning", "natural_language_processing",
            "computer_vision", "pytorch", "tensorflow", "keras",
            "xgboost", "lightgbm", "catboost", "scikit_learn",
        }
    )
    return ml_weight >= 0.5


# ===========================================================================
# 6. Enrichment
# ===========================================================================

def enrich_profiles(
    unified_profiles: List[Dict],
    kaggle_profiles: List[Dict],
    claimed: Dict[int, Tuple[int, float]],
) -> List[Dict]:
    """
    Apply Kaggle signals to claimed unified profiles.
    All other profiles pass through unchanged with has_kaggle=False defaults.
    """
    enriched = [dict(p) for p in unified_profiles]

    for ui, profile in enumerate(enriched):
        if ui not in claimed:
            # ── Unmatched: defaults ─────────────────────────────────────────
            profile["github_score"]              = float(profile.get("github_score", 0.0))
            profile["kaggle_score"]              = 0.0
            profile["overall_score"]             = profile["github_score"]
            profile["has_kaggle"]                = False
            profile["is_ml_specialist"]          = False
            profile["match_confidence"]          = 0.0
            profile["match_type"]                = "none"
            profile["source_weights"]            = {"github": 1.0, "kaggle": 0.0}
            profile["kaggle_contribution_ratio"] = 0.0
            profile["domain_overlap_score"]      = 0.0
            profile["confidence_boost"]          = False
            profile["top_match_candidates"]      = []
        else:
            # ── Matched: merge signals ───────────────────────────────────────
            ki, sim_score = claimed[ui]
            kp = kaggle_profiles[ki]

            orig_skills   = unified_profiles[ui].get("skills", {})
            orig_domains  = unified_profiles[ui].get("domains", [])

            merged_skills  = merge_skills(orig_skills, kp.get("skills", {}))
            merged_domains = merge_domains(orig_domains, kp.get("domains", []))
            gh_s, kag_s, overall = merge_scores(profile, kp.get("kaggle_score", 0.0))
            merged_conf = merge_confidence(
                float(profile.get("confidence_score", 0.0)),
                float(kp.get("confidence_score", 0.0)),
            )

            # Kaggle-only skill contribution
            kaggle_only  = set(kp.get("skills", {})) - set(orig_skills)
            contrib_ratio = round(len(kaggle_only) / max(1, len(merged_skills)), 4)

            # Bonus flags
            dom_overlap = domain_overlap_score(orig_domains, kp.get("domains", []))
            both_ml     = is_ml_heavy(orig_skills) and kp.get("is_ml_specialist", False)

            match_type  = (
                "skill_similarity_strong" if sim_score >= STRONG_THRESHOLD
                else "skill_similarity_weak"
            )

            profile["skills"]                   = merged_skills
            profile["domains"]                  = merged_domains
            profile["confidence_score"]         = merged_conf
            profile["github_score"]             = gh_s
            profile["kaggle_score"]             = kag_s
            profile["overall_score"]            = overall
            profile["has_kaggle"]               = True
            profile["is_ml_specialist"]         = bool(kp.get("is_ml_specialist", False))
            profile["match_confidence"]         = sim_score
            profile["match_type"]               = match_type
            profile["total_kernels"]            = kp.get("total_kernels", 0)
            profile["avg_votes"]                = kp.get("avg_votes", 0)
            profile["source_weights"]           = {"github": GITHUB_WEIGHT, "kaggle": KAGGLE_WEIGHT}
            profile["kaggle_contribution_ratio"]= contrib_ratio
            profile["domain_overlap_score"]     = dom_overlap
            profile["confidence_boost"]         = both_ml

    return enriched


# ===========================================================================
# 7. Save
# ===========================================================================

def save_output(enriched: List[Dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2)
    logger.info(f"  Saved {len(enriched):,} enriched profiles → {OUT_FILE}")


# ===========================================================================
# 8. Main
# ===========================================================================

def main() -> None:
    logger.info("=== Kaggle Enricher v2 (skill-similarity) started ===")

    kaggle_profiles  = load_kaggle_profiles()
    unified_profiles = load_unified_profiles()

    logger.info("Building global skill vocabulary …")
    vocab = build_skill_index(kaggle_profiles, unified_profiles)

    logger.info("Running skill-similarity matching …")
    claimed = match_profiles(kaggle_profiles, unified_profiles, vocab)

    # ── Statistics ───────────────────────────────────────────────────────────
    n_unified = len(unified_profiles)
    n_matched = len(claimed)
    scores    = [score for _, score in claimed.values()]
    n_strong  = sum(1 for s in scores if s >= STRONG_THRESHOLD)
    n_weak    = sum(1 for s in scores if ACCEPT_THRESHOLD <= s < STRONG_THRESHOLD)
    avg_sim   = round(sum(scores) / len(scores), 4) if scores else 0.0

    logger.info("=== Matching Summary ===")
    logger.info(f"  Total Kaggle profiles    : {len(kaggle_profiles):,}")
    logger.info(f"  Total unified profiles   : {n_unified:,}")
    logger.info(f"  Matches found            : {n_matched:,}  ({n_matched / n_unified * 100:.1f}%)")
    logger.info(f"  → Strong (≥0.75)         : {n_strong:,}")
    logger.info(f"  → Weak   (0.70–0.75)     : {n_weak:,}")
    logger.info(f"  Avg similarity score     : {avg_sim}")
    logger.info(f"  Unmatched unified        : {n_unified - n_matched:,}")

    logger.info("Enriching profiles …")
    enriched = enrich_profiles(unified_profiles, kaggle_profiles, claimed)

    save_output(enriched)

    ml_count  = sum(1 for p in enriched if p.get("is_ml_specialist"))
    kag_count = sum(1 for p in enriched if p.get("has_kaggle"))
    logger.info("=== Enrichment Summary ===")
    logger.info(f"  Profiles with Kaggle     : {kag_count:,}")
    logger.info(f"  ML specialists flagged   : {ml_count:,}")
    logger.info("=== Kaggle Enricher v2 complete ===")


if __name__ == "__main__":
    main()
