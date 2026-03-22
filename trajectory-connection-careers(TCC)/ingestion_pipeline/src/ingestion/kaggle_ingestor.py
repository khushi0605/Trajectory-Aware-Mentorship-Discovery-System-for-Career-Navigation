"""
kaggle_ingestor.py
------------------
Ingests structured Kaggle signals from raw Meta Kaggle CSV files.

Input files (data/raw/kaggle/):
  - Users Data.csv     : Kaggle user records
  - Kernels.csv        : Notebook metadata per user
  - Kernel Tags.csv    : tag assignments per kernel

Output:
  data/processed/kaggle/kaggle_raw_profiles.json

Each output record:
  {
    "kaggle_user_id": "12345",
    "username":        "john_doe",
    "kernels": [
      {
        "kernel_id": "cool-notebook",
        "title":     "Cool Notebook",
        "tags":      ["deep-learning", "pytorch"],
        "votes":     120
      }
    ]
  }

NOTE: This module performs ingestion and structuring ONLY.
      Skill extraction and profile merging happen downstream.

Usage:
  PYTHONPATH=. python3 src/ingestion/kaggle_ingestor.py [--limit N]
"""

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/kaggle_ingestor.log", mode="a"),
    ],
)
logger = logging.getLogger("kaggle_ingestor")
Path("logs").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------
RAW_DIR  = Path("data/raw/kaggle")
OUT_DIR  = Path("data/processed/kaggle")
OUT_FILE = OUT_DIR / "kaggle_raw_profiles.json"

USERS_CSV   = RAW_DIR / "Users Data.csv"
KERNELS_CSV = RAW_DIR / "Kernels.csv"
TAGS_CSV    = RAW_DIR / "Kernel Tags.csv"


# ---------------------------------------------------------------------------
# 1. Load Data
# ---------------------------------------------------------------------------

def load_data(limit: Optional[int] = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load the three Meta Kaggle CSVs into DataFrames, retaining only the
    columns we actually need to keep memory usage low.

    Args:
        limit: If set, only the first `limit` rows of Users Data.csv are
               loaded (useful for testing).

    Returns:
        (users_df, kernels_df, tags_df)
    """

    logger.info("Loading Users Data.csv …")
    users_df = pd.read_csv(
        USERS_CSV,
        usecols=["Id", "UserName"],
        dtype={"Id": str, "UserName": str},
        nrows=limit,
    )
    users_df.columns = ["user_id", "username"]
    users_df.dropna(subset=["user_id", "username"], inplace=True)
    logger.info(f"  Users loaded: {len(users_df):,}")

    logger.info("Loading Kernels.csv …")
    kernels_df = pd.read_csv(
        KERNELS_CSV,
        usecols=["Id", "AuthorUserId", "CurrentUrlSlug", "TotalVotes"],
        dtype={"Id": str, "AuthorUserId": str, "CurrentUrlSlug": str},
    )
    kernels_df.columns = ["kernel_id", "author_user_id", "title", "votes"]
    kernels_df["votes"] = pd.to_numeric(kernels_df["votes"], errors="coerce").fillna(0).astype(int)
    kernels_df.dropna(subset=["kernel_id", "author_user_id", "title"], inplace=True)
    logger.info(f"  Kernels loaded: {len(kernels_df):,}")

    logger.info("Loading Kernel Tags.csv …")
    tags_df = pd.read_csv(
        TAGS_CSV,
        usecols=["KernelId", "TagId"],
        dtype={"KernelId": str, "TagId": str},
    )
    tags_df.columns = ["kernel_id", "tag_id"]
    tags_df.dropna(inplace=True)
    logger.info(f"  Tag rows loaded: {len(tags_df):,}")

    return users_df, kernels_df, tags_df


# ---------------------------------------------------------------------------
# 2. Build kernel → tag_list mapping
# ---------------------------------------------------------------------------

def build_kernel_tag_map(tags_df: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Group tag IDs by kernel_id.

    Since the raw data only has numeric tag IDs (no names file shipped with
    the Metadata CSVs), we normalise them to the string `tag_<id>` so that
    downstream processing can still filter / cluster by tag ID.

    Args:
        tags_df: DataFrame with columns [kernel_id, tag_id].

    Returns:
        dict mapping kernel_id → sorted list of normalised tag strings.
    """
    logger.info("Building kernel → tag map …")

    def _norm_tag(tag_id: str) -> str:
        return f"tag_{tag_id.strip()}"

    kernel_tag_map: Dict[str, List[str]] = (
        tags_df
        .groupby("kernel_id")["tag_id"]
        .agg(lambda ids: sorted({_norm_tag(t) for t in ids}))
        .to_dict()
    )
    logger.info(f"  Kernels with at least one tag: {len(kernel_tag_map):,}")
    return kernel_tag_map


# ---------------------------------------------------------------------------
# 3. Build per-user kernel profiles
# ---------------------------------------------------------------------------

def _normalise_title(slug: str) -> str:
    """
    Convert a URL slug (e.g. 'deep-learning-with-pytorch') into a
    human-readable title ('Deep Learning With Pytorch').
    """
    return re.sub(r"[-_]+", " ", slug).title()


def build_user_kernel_profiles(
    users_df: pd.DataFrame,
    kernels_df: pd.DataFrame,
    kernel_tag_map: Dict[str, List[str]],
    drop_untagged: bool = True,
) -> List[Dict]:
    """
    Combine Users, Kernels, and the tag map into a list of per-user dicts.

    Args:
        users_df:        User records.
        kernels_df:      Kernel records.
        kernel_tag_map:  kernel_id → [tag, ...].
        drop_untagged:   If True (default), kernels without any tags are
                         excluded — they carry no signal for downstream
                         skill or domain extraction.

    Returns:
        List of user profile dicts.
    """
    # We only keep users whose IDs appear in the kernels file (saves RAM)
    relevant_user_ids = set(kernels_df["author_user_id"].unique())
    users_df = users_df[users_df["user_id"].isin(relevant_user_ids)].copy()
    logger.info(f"  Users with at least one kernel: {len(users_df):,}")

    # Build user_id → username lookup
    user_lookup: Dict[str, str] = dict(zip(users_df["user_id"], users_df["username"]))

    # Drop duplicate kernels (same kernel_id)
    kernels_df = kernels_df.drop_duplicates(subset=["kernel_id"])

    profiles: List[Dict] = []

    author_groups = kernels_df.groupby("author_user_id")
    total = len(author_groups)
    logger.info(f"  Building profiles for {total:,} users …")

    for idx, (author_id, group) in enumerate(author_groups, 1):
        username = user_lookup.get(author_id, "")

        kernels_out: List[Dict] = []
        for _, row in group.iterrows():
            kid   = str(row["kernel_id"])
            tags  = kernel_tag_map.get(kid, [])

            if drop_untagged and not tags:
                continue

            kernels_out.append({
                "kernel_id": kid,
                "title":     _normalise_title(str(row["title"])),
                "tags":      tags,
                "votes":     int(row["votes"]),
            })

        # Skip users who have no valid kernels after filtering
        if not kernels_out:
            continue

        profiles.append({
            "kaggle_user_id": author_id,
            "username":       username,
            "kernels":        kernels_out,
        })

        if idx % 5000 == 0:
            logger.info(f"  Progress: {idx:,}/{total:,} author groups processed")

    return profiles


# ---------------------------------------------------------------------------
# 4. Save output
# ---------------------------------------------------------------------------

def save_output(profiles: List[Dict], out_path: Path) -> None:
    """
    Serialise the profile list to JSON.

    Args:
        profiles: List of user profile dicts.
        out_path: Absolute path to write the output JSON.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)
    logger.info(f"  Saved {len(profiles):,} profiles → {out_path}")


# ---------------------------------------------------------------------------
# 5. Stats summary
# ---------------------------------------------------------------------------

def print_stats(profiles: List[Dict]) -> None:
    """Log a brief summary of the generated dataset."""
    total_users   = len(profiles)
    total_kernels = sum(len(p["kernels"]) for p in profiles)
    avg_kernels   = total_kernels / max(1, total_users)

    logger.info("=== Kaggle Ingestor — Summary ===")
    logger.info(f"  Users processed       : {total_users:,}")
    logger.info(f"  Total kernels retained: {total_kernels:,}")
    logger.info(f"  Avg kernels / user    : {avg_kernels:.1f}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(limit: Optional[int] = None) -> None:
    logger.info("=== Kaggle Ingestor started ===")

    users_df, kernels_df, tags_df = load_data(limit=limit)
    kernel_tag_map = build_kernel_tag_map(tags_df)

    profiles = build_user_kernel_profiles(
        users_df,
        kernels_df,
        kernel_tag_map,
        drop_untagged=True,
    )

    save_output(profiles, OUT_FILE)
    print_stats(profiles)

    logger.info("=== Kaggle Ingestor complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kaggle Ingestor")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N users (useful for testing). Default: all.",
    )
    args = parser.parse_args()
    main(limit=args.limit)
