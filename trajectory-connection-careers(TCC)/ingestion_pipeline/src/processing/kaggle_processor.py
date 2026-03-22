"""
kaggle_processor.py
--------------------
Processes structured Kaggle raw profiles (from kaggle_ingestor.py) into
normalized, skill-weighted Kaggle profiles suitable for downstream enrichment.

Data flow:
  data/processed/kaggle/kaggle_raw_profiles.json
      ↓  (this script)
  data/processed/kaggle/kaggle_processed_profiles.json

Operations applied per user:
  1. Skill extraction  : keyword match against kernel titles
  2. Vote weighting    : weight = log(1 + votes), floored at 0.1
  3. Skill aggregation : sum weighted skill contributions across all kernels
  4. Normalization     : top-N skills scaled to sum = 1.0
  5. Domain inference  : top 2–3 domains from skill→domain map
  6. Kaggle score      : log(1 + total_votes) + 0.5 * total_kernels
  7. Bonus flags       : is_ml_specialist, confidence_score

Usage:
  PYTHONPATH=. python3 src/processing/kaggle_processor.py [--limit N]
"""

import argparse
import json
import logging
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/kaggle_processor.log", mode="a"),
    ],
)
logger = logging.getLogger("kaggle_processor")
Path("logs").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# I/O paths
# ---------------------------------------------------------------------------
IN_FILE  = Path("data/processed/kaggle/kaggle_raw_profiles.json")
OUT_DIR  = Path("data/processed/kaggle")
OUT_FILE = OUT_DIR / "kaggle_processed_profiles.json"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TOP_N_SKILLS   = 15   # maximum skills kept per user
MIN_KERNELS    = 2    # users with fewer kernels are filtered out
ML_DOMAIN_THRESHOLD = 0.5  # fraction of skill weight that must be ML-domain to flag is_ml_specialist

# ---------------------------------------------------------------------------
# Keyword → canonical skill mapping
# (multi-word phrases checked BEFORE single tokens)
# ---------------------------------------------------------------------------
KEYWORD_TO_SKILL: Dict[str, str] = {
    # Deep Learning frameworks
    "pytorch":            "pytorch",
    "tensorflow":         "tensorflow",
    "keras":              "keras",
    "jax":                "jax",
    "mxnet":              "mxnet",
    "caffe":              "caffe",

    # NLP / LLM
    "nlp":                "natural_language_processing",
    "bert":               "natural_language_processing",
    "gpt":                "natural_language_processing",
    "llm":                "natural_language_processing",
    "transformer":        "natural_language_processing",
    "language model":     "natural_language_processing",
    "text classification":"natural_language_processing",
    "sentiment":          "natural_language_processing",
    "ner":                "natural_language_processing",
    "named entity":       "natural_language_processing",
    "tokeniz":            "natural_language_processing",
    "embeddings":         "natural_language_processing",
    "word2vec":           "natural_language_processing",

    # Computer Vision
    "cnn":                "deep_learning",
    "convolutional":      "deep_learning",
    "segmentation":       "computer_vision",
    "object detection":   "computer_vision",
    "yolo":               "computer_vision",
    "resnet":             "computer_vision",
    "efficientnet":       "computer_vision",
    "image classification":"computer_vision",
    "image recognition":  "computer_vision",
    "face detection":     "computer_vision",
    "ocr":                "computer_vision",
    "unet":               "computer_vision",
    "detection":          "computer_vision",
    "vision":             "computer_vision",
    "pixel":              "computer_vision",
    "mask":               "computer_vision",

    # Deep Learning general
    "deep learning":      "deep_learning",
    "neural network":     "deep_learning",
    "lstm":               "deep_learning",
    "rnn":                "deep_learning",
    "attention":          "deep_learning",
    "autoencoder":        "deep_learning",
    "gan":                "deep_learning",
    "generative":         "deep_learning",

    # Classical ML
    "xgboost":            "xgboost",
    "lightgbm":           "lightgbm",
    "catboost":           "catboost",
    "random forest":      "machine_learning",
    "gradient boosting":  "machine_learning",
    "regression":         "machine_learning",
    "classification":     "machine_learning",
    "clustering":         "machine_learning",
    "k-means":            "machine_learning",
    "svm":                "machine_learning",
    "feature engineering":"machine_learning",
    "hyperparameter":     "machine_learning",
    "cross.validation":   "machine_learning",
    "ensemble":           "machine_learning",
    "machine learning":   "machine_learning",
    "ml ":                "machine_learning",

    # Data & EDA
    "eda":                "data_analysis",
    "exploratory":        "data_analysis",
    "visualization":      "data_analysis",
    "matplotlib":         "data_analysis",
    "seaborn":            "data_analysis",
    "plotly":             "data_analysis",
    "analysis":           "data_analysis",
    "pandas":             "data_analysis",
    "numpy":              "data_analysis",
    "statistics":         "data_analysis",
    "correlation":        "data_analysis",
    "distribution":       "data_analysis",

    # Time Series
    "time series":        "time_series",
    "forecasting":        "time_series",
    "arima":              "time_series",
    "prophet":            "time_series",
    "lstm":               "time_series",

    # Tabular / structured data
    "tabular":            "machine_learning",
    "structured":         "machine_learning",
    "feature selection":  "machine_learning",

    # Reinforcement Learning
    "reinforcement":      "reinforcement_learning",
    "q-learning":         "reinforcement_learning",
    "policy":             "reinforcement_learning",
    "reward":             "reinforcement_learning",

    # Languages / Tools
    "python":             "python",
    "sql":                "sql",
    "r ":                 "r_programming",
    "scikit":             "scikit_learn",
    "sklearn":            "scikit_learn",
    "spark":              "spark",
    "hadoop":             "big_data",
    "big data":           "big_data",

    # Medical / Bio AI
    "medical":            "medical_ai",
    "clinical":           "medical_ai",
    "cancer":             "medical_ai",
    "disease":            "medical_ai",
    "brain":              "medical_ai",
    "mri":                "medical_ai",
    "dicom":              "medical_ai",

    # Recommender Systems
    "recommendation":     "recommender_systems",
    "collaborative filtering": "recommender_systems",
    "matrix factorization":    "recommender_systems",
}

# Sorted once by length (descending) so multi-word phrases match before subwords
_SORTED_KEYWORDS: List[Tuple[str, str]] = sorted(
    KEYWORD_TO_SKILL.items(), key=lambda x: len(x[0]), reverse=True
)

# ---------------------------------------------------------------------------
# Skill → Domain map
# ---------------------------------------------------------------------------
SKILL_TO_DOMAIN: Dict[str, str] = {
    "pytorch":                    "machine_learning",
    "tensorflow":                 "machine_learning",
    "keras":                      "machine_learning",
    "jax":                        "machine_learning",
    "mxnet":                      "machine_learning",
    "caffe":                      "machine_learning",
    "natural_language_processing":"nlp",
    "deep_learning":              "machine_learning",
    "computer_vision":            "computer_vision",
    "xgboost":                    "machine_learning",
    "lightgbm":                   "machine_learning",
    "catboost":                   "machine_learning",
    "machine_learning":           "machine_learning",
    "scikit_learn":               "machine_learning",
    "data_analysis":              "data_analysis",
    "time_series":                "machine_learning",
    "reinforcement_learning":     "machine_learning",
    "python":                     "programming",
    "sql":                        "data_engineering",
    "r_programming":              "data_analysis",
    "spark":                      "data_engineering",
    "big_data":                   "data_engineering",
    "medical_ai":                 "machine_learning",
    "recommender_systems":        "machine_learning",
}

ML_DOMAINS = {"machine_learning", "nlp", "computer_vision", "data_analysis", "time_series"}


# ---------------------------------------------------------------------------
# 1. Load data
# ---------------------------------------------------------------------------

def load_data(limit: Optional[int] = None) -> List[Dict]:
    """Load the raw Kaggle profiles from disk."""
    logger.info(f"Loading {IN_FILE} …")
    with open(IN_FILE, "r", encoding="utf-8") as f:
        profiles = json.load(f)
    if limit:
        profiles = profiles[:limit]
    logger.info(f"  Loaded {len(profiles):,} user profiles")
    return profiles


# ---------------------------------------------------------------------------
# 2. Skill extraction from a single title
# ---------------------------------------------------------------------------

def extract_skills_from_title(title: str) -> List[str]:
    """
    Match keywords in a kernel title → return list of canonical skill names.
    Multi-word phrases are checked first (sorted by length desc).
    """
    title_lower = title.lower()
    found: List[str] = []
    seen_positions = set()

    for keyword, skill in _SORTED_KEYWORDS:
        pos = title_lower.find(keyword)
        if pos == -1:
            continue
        # Avoid overlapping matches
        span = set(range(pos, pos + len(keyword)))
        if span & seen_positions:
            continue
        seen_positions |= span
        if skill not in found:
            found.append(skill)

    return found


# ---------------------------------------------------------------------------
# 3. Compute weighted skill dict for one user's kernels
# ---------------------------------------------------------------------------

def compute_skill_weights(kernels: List[Dict]) -> Dict[str, float]:
    """
    For each kernel, compute vote-based weight and accumulate per skill.

    weight = max(log(1 + votes), 0.1)

    Skills from higher-voted kernels contribute more to the final profile.
    """
    skill_weights: Dict[str, float] = defaultdict(float)

    for kernel in kernels:
        votes  = int(kernel.get("votes", 0))
        weight = max(math.log1p(votes), 0.1)
        title  = kernel.get("title", "")
        skills = extract_skills_from_title(title)

        for skill in skills:
            skill_weights[skill] += weight

    return dict(skill_weights)


# ---------------------------------------------------------------------------
# 4. Normalize skills (top-N; sum-to-1)
# ---------------------------------------------------------------------------

def normalize_skills(skill_dict: Dict[str, float], top_n: int = TOP_N_SKILLS) -> Dict[str, float]:
    """
    Keep at most `top_n` skills, sorted by weight descending.
    Rescale all weights to sum exactly to 1.0.
    """
    if not skill_dict:
        return {}

    # Take top N by weight
    top = sorted(skill_dict.items(), key=lambda x: x[1], reverse=True)[:top_n]
    total = sum(w for _, w in top)

    return {skill: round(w / total, 4) for skill, w in top}


# ---------------------------------------------------------------------------
# 5. Domain inference
# ---------------------------------------------------------------------------

def infer_domains(skills: Dict[str, float], top_k: int = 3) -> List[str]:
    """
    Accumulate skill weights per domain and return the top `top_k` domains.
    """
    domain_score: Dict[str, float] = defaultdict(float)
    for skill, weight in skills.items():
        domain = SKILL_TO_DOMAIN.get(skill)
        if domain:
            domain_score[domain] += weight

    top_domains = sorted(domain_score.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [d for d, _ in top_domains] if top_domains else ["general"]


# ---------------------------------------------------------------------------
# 6. Kaggle credibility score
# ---------------------------------------------------------------------------

def compute_kaggle_score(kernels: List[Dict]) -> Tuple[float, int, float]:
    """
    Returns (kaggle_score, total_kernels, avg_votes).

    kaggle_score = log(1 + total_votes) + 0.5 * total_kernels
    """
    total_votes   = sum(int(k.get("votes", 0)) for k in kernels)
    total_kernels = len(kernels)
    avg_votes     = round(total_votes / max(1, total_kernels), 2)
    score         = round(math.log1p(total_votes) + 0.5 * total_kernels, 4)
    return score, total_kernels, avg_votes


# ---------------------------------------------------------------------------
# 7. Bonus helpers
# ---------------------------------------------------------------------------

def compute_confidence(skills: Dict[str, float], total_kernels: int) -> float:
    """
    Heuristic Kaggle data confidence score [0, 1].
    Higher when: more skills extracted AND more kernels.
    """
    skill_coverage = min(len(skills) / TOP_N_SKILLS, 1.0)
    kernel_coverage = min(total_kernels / 10, 1.0)
    return round(0.6 * skill_coverage + 0.4 * kernel_coverage, 4)


def is_ml_specialist(skills: Dict[str, float]) -> bool:
    """True if ML-related domain skills account for >= 50% of total weight."""
    ml_weight = sum(
        w for skill, w in skills.items()
        if SKILL_TO_DOMAIN.get(skill) in ML_DOMAINS
    )
    return ml_weight >= ML_DOMAIN_THRESHOLD


# ---------------------------------------------------------------------------
# 8. Process all profiles
# ---------------------------------------------------------------------------

def process_profiles(
    raw_profiles: List[Dict],
    min_kernels: int = MIN_KERNELS,
) -> List[Dict]:
    """
    Iterate raw profiles and produce normalized processed records.
    Filters out users with too few kernels or no extractable skills.
    """
    processed: List[Dict] = []
    n_total    = len(raw_profiles)
    n_skipped  = 0
    skill_counts: List[int] = []

    logger.info(f"Processing {n_total:,} raw profiles …")

    for idx, user in enumerate(raw_profiles, 1):
        uid     = user.get("kaggle_user_id", "")
        kernels = user.get("kernels", [])

        # Filter: too few kernels
        if len(kernels) < min_kernels:
            n_skipped += 1
            continue

        # Step 1: Extract + weight skills
        raw_weights = compute_skill_weights(kernels)

        # Filter: no skills found
        if not raw_weights:
            n_skipped += 1
            continue

        # Step 2: Normalize
        skills = normalize_skills(raw_weights)

        # Step 3: Domains
        domains = infer_domains(skills)

        # Step 4: Kaggle score
        kaggle_score, total_kernels, avg_votes = compute_kaggle_score(kernels)

        # Step 5: Bonus fields
        confidence = compute_confidence(skills, total_kernels)
        ml_flag    = is_ml_specialist(skills)

        processed.append({
            "kaggle_user_id":  uid,
            "skills":          skills,
            "domains":         domains,
            "kaggle_score":    kaggle_score,
            "total_kernels":   total_kernels,
            "avg_votes":       avg_votes,
            "confidence_score": confidence,
            "is_ml_specialist": ml_flag,
        })
        skill_counts.append(len(skills))

        if idx % 10000 == 0:
            logger.info(f"  Progress: {idx:,}/{n_total:,}")

    avg_skills = sum(skill_counts) / max(1, len(skill_counts))
    logger.info("=== Processing Summary ===")
    logger.info(f"  Total raw profiles     : {n_total:,}")
    logger.info(f"  Profiles retained      : {len(processed):,}")
    logger.info(f"  Profiles skipped       : {n_skipped:,}")
    logger.info(f"  Avg skills / profile   : {avg_skills:.1f}")

    return processed


# ---------------------------------------------------------------------------
# 9. Save output
# ---------------------------------------------------------------------------

def save_output(profiles: List[Dict]) -> None:
    """Write final processed profiles to disk."""
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)
    logger.info(f"  Saved {len(profiles):,} profiles → {OUT_FILE}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(limit: Optional[int] = None) -> None:
    logger.info("=== Kaggle Processor started ===")
    raw_profiles = load_data(limit=limit)
    processed    = process_profiles(raw_profiles)
    save_output(processed)
    logger.info("=== Kaggle Processor complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaggle Processor")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process first N raw profiles (for testing).",
    )
    args = parser.parse_args()
    main(limit=args.limit)
