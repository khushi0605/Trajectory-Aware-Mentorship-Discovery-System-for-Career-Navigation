"""
github_bulk_collector.py
------------------------
Collects 500-1000 unique GitHub user profiles using the GitHub REST API.

Strategies:
  1. /search/users?q=followers:>10+repos:>5   (paginated)
  2. /search/repositories?q=stars:>50          (extract owners, paginated)

Filters:
  - type == "User" (not Org)
  - >= 3 public repositories
  - >= 1 non-null programming language

Output:
  data/raw/profiles/github/{username}.json  (one file per user)

Usage:
  PYTHONPATH=. python3 src/ingestion/scrapers/github_bulk_collector.py --target 500
  PYTHONPATH=. python3 src/ingestion/scrapers/github_bulk_collector.py --target 20  # smoke test
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import requests
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/github_bulk_collector.log", mode="a"),
    ],
)
logger = logging.getLogger("github_bulk_collector")

# Output directory
OUTPUT_DIR = Path("data/raw/profiles/github")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
Path("logs").mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# GitHub API client helpers
# ---------------------------------------------------------------------------

class RateLimitError(Exception):
    """Raised when GitHub API rate limit is exceeded."""


def _build_headers(token: Optional[str]) -> Dict[str, str]:
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "TCC-BulkCollector/1.0",
    }
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def _check_rate_limit(response: requests.Response) -> None:
    """Sleep if we're close to exhausting the rate limit."""
    remaining = int(response.headers.get("X-RateLimit-Remaining", 1))
    reset_ts = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
    if remaining <= 5:
        sleep_secs = max(reset_ts - int(time.time()), 1) + 2
        logger.warning(f"Rate limit low ({remaining} left). Sleeping {sleep_secs}s until reset.")
        time.sleep(sleep_secs)


def _request(
    url: str,
    headers: Dict[str, str],
    params: Optional[Dict] = None,
    max_retries: int = 3,
) -> Optional[requests.Response]:
    """Make a GET request with retry logic and rate-limit awareness."""
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)

            # Respect rate limit headers before raising
            _check_rate_limit(resp)

            if resp.status_code == 403:
                # Secondary rate limit or forbidden — back off
                logger.warning(f"403 Forbidden from {url}. Backing off 60s (attempt {attempt}).")
                time.sleep(60 * attempt)
                continue

            if resp.status_code == 422:
                # GitHub Search returns 422 when pagination goes past limit
                logger.debug(f"422 Unprocessable entity for {url} — likely past search window.")
                return None

            if resp.status_code == 404:
                return None  # User not found, skip

            resp.raise_for_status()
            return resp

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout on {url} (attempt {attempt}/{max_retries}). Retrying...")
            time.sleep(2 ** attempt)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Request error {url} (attempt {attempt}/{max_retries}): {e}")
            time.sleep(2 ** attempt)

    logger.error(f"All {max_retries} attempts failed for {url}")
    return None


# ---------------------------------------------------------------------------
# GitHubBulkCollector
# ---------------------------------------------------------------------------

class GitHubBulkCollector:
    """
    Discovers and collects GitHub user profiles at scale.
    """

    BASE_URL = "https://api.github.com"

    # Minimum quality filters
    MIN_REPOS = 3
    MIN_LANGUAGES = 1

    def __init__(self, token: Optional[str] = None, target: int = 500):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = _build_headers(self.token)
        self.target = target

        if not self.token:
            logger.warning("No GITHUB_TOKEN set. Rate limits will be very tight (60 req/hr).")

        # Tracking sets
        self._discovered: Set[str] = set()
        self._collected: int = 0
        self._skipped: int = 0
        self._failed: int = 0

    # ------------------------------------------------------------------
    # User discovery strategies
    # ------------------------------------------------------------------

    def _discover_from_user_search(self, max_pages: int = 10) -> List[str]:
        """
        Discover users via /search/users endpoint.
        Query: followers:>10 repos:>5 — gives active developers.
        GitHub caps Search API at 1000 results (10 pages × 100).
        """
        discovered = []
        queries = [
            "followers:>100 repos:>10 type:user",
            "followers:>10 repos:>5 language:python type:user",
            "followers:>10 repos:>5 language:javascript type:user",
            "followers:>10 repos:>5 language:java type:user",
            "followers:>10 repos:>5 language:go type:user",
        ]

        for query in queries:
            if len(self._discovered) >= self.target * 3:
                break  # Enough candidates
            for page in range(1, max_pages + 1):
                params = {"q": query, "per_page": 100, "page": page}
                resp = _request(f"{self.BASE_URL}/search/users", self.headers, params)
                if not resp:
                    break
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break
                for item in items:
                    login = item.get("login")
                    if login and login not in self._discovered:
                        self._discovered.add(login)
                        discovered.append(login)

                logger.info(f"[user search] Query '{query[:40]}' page {page}: +{len(items)} candidates")
                time.sleep(0.5)  # Small delay between pages

                # Stop early per query if we already have enough
                if len(self._discovered) >= self.target * 3:
                    break

        return discovered

    def _discover_from_repo_search(self, max_pages: int = 10) -> List[str]:
        """
        Discover users by extracting owners of popular repositories.
        Query: stars:>50 — gives reasonably active repos.
        """
        discovered = []
        queries = [
            "stars:>200 language:python",
            "stars:>100 language:javascript",
            "stars:>100 language:typescript",
            "stars:>50 language:rust",
            "stars:>50 language:go",
        ]

        for query in queries:
            if len(self._discovered) >= self.target * 3:
                break
            for page in range(1, max_pages + 1):
                params = {"q": query, "per_page": 100, "page": page, "sort": "stars"}
                resp = _request(f"{self.BASE_URL}/search/repositories", self.headers, params)
                if not resp:
                    break
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break
                for repo in items:
                    owner = repo.get("owner", {})
                    login = owner.get("login")
                    owner_type = owner.get("type", "")
                    # Pre-filter orgs at discovery time
                    if login and owner_type == "User" and login not in self._discovered:
                        self._discovered.add(login)
                        discovered.append(login)

                logger.info(f"[repo search] Query '{query[:40]}' page {page}: +{len(items)} repos scanned")
                time.sleep(0.5)

                if len(self._discovered) >= self.target * 3:
                    break

        return discovered

    # ------------------------------------------------------------------
    # Data collection for a single user
    # ------------------------------------------------------------------

    def _fetch_profile(self, username: str) -> Optional[Dict]:
        resp = _request(f"{self.BASE_URL}/users/{username}", self.headers)
        return resp.json() if resp else None

    def _fetch_repos(self, username: str) -> List[Dict]:
        resp = _request(
            f"{self.BASE_URL}/users/{username}/repos",
            self.headers,
            params={"type": "owner", "sort": "updated", "per_page": 100},
        )
        return resp.json() if resp else []

    def _fetch_total_commits(self, username: str) -> int:
        """Estimate total commits via /search/commits API."""
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.cloak-preview"
        resp = _request(
            f"{self.BASE_URL}/search/commits",
            headers,
            params={"q": f"author:{username}"},
        )
        if resp:
            return resp.json().get("total_count", 0)
        return 0

    def _passes_filters(self, profile: Dict, repos: List[Dict]) -> bool:
        """Apply all quality filters."""
        # Only individual users (not organizations)
        if profile.get("type") != "User":
            return False
        # Must have at least MIN_REPOS public repos
        if len(repos) < self.MIN_REPOS:
            return False
        # Must have at least one non-null language
        langs = {r.get("language") for r in repos if r.get("language")}
        if len(langs) < self.MIN_LANGUAGES:
            return False
        return True

    def _collect_user(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch and assemble profile for a single user. Returns None if filtered/failed."""
        # Skip if already collected
        output_path = OUTPUT_DIR / f"{username}.json"
        if output_path.exists():
            logger.debug(f"Skipping {username} — already collected.")
            self._skipped += 1
            return None

        profile = self._fetch_profile(username)
        if not profile:
            logger.warning(f"Could not fetch profile for {username}. Skipping.")
            self._failed += 1
            return None

        repos_raw = self._fetch_repos(username)
        time.sleep(0.3)  # Polite delay between API calls for a single user

        if not self._passes_filters(profile, repos_raw):
            logger.debug(f"Filtered out {username} (type={profile.get('type')}, repos={len(repos_raw)}).")
            self._skipped += 1
            return None

        # Build repo list
        repositories = []
        languages_set: Set[str] = set()
        for repo in repos_raw:
            lang = repo.get("language")
            if lang:
                languages_set.add(lang)
            repositories.append({
                "name": repo.get("name"),
                "description": repo.get("description"),
                "language": lang,
                "stars": repo.get("stargazers_count", 0),
                "topics": repo.get("topics", []),
                "created_at": repo.get("created_at"),
            })

        total_commits = self._fetch_total_commits(username)

        data = {
            "username": username,
            "repositories": repositories,
            "languages": sorted(list(languages_set)),
            "total_commits": str(total_commits),
            "followers": str(profile.get("followers", 0)),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save to disk
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self._collected += 1
        logger.info(f"[{self._collected}/{self.target}] Collected {username} "
                    f"({len(repositories)} repos, {len(languages_set)} langs, {total_commits} commits)")
        return data

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def run(self) -> None:
        logger.info(f"=== GitHub Bulk Collector started | Target: {self.target} users ===")
        start_time = time.time()

        # 1. Discover candidates
        logger.info("--- Phase 1: User discovery ---")
        self._discover_from_user_search()
        self._discover_from_repo_search()
        logger.info(f"Total candidates discovered: {len(self._discovered)}")

        # 2. Collect data for each candidate until target is reached
        logger.info("--- Phase 2: Data collection ---")
        for username in list(self._discovered):
            if self._collected >= self.target:
                break
            try:
                self._collect_user(username)
                time.sleep(0.5)  # Polite inter-user delay
            except Exception as e:
                logger.error(f"Unexpected error collecting {username}: {e}")
                self._failed += 1

        # 3. Summary
        elapsed = time.time() - start_time
        logger.info("=== Collection complete ===")
        logger.info(f"  Collected : {self._collected}")
        logger.info(f"  Skipped   : {self._skipped}")
        logger.info(f"  Failed    : {self._failed}")
        logger.info(f"  Time      : {elapsed:.1f}s")
        logger.info(f"  Output    : {OUTPUT_DIR.resolve()}")

        if self._collected < self.target:
            logger.warning(
                f"Only collected {self._collected}/{self.target} users. "
                "Consider expanding discovery queries or increasing max_pages."
            )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GitHub Bulk User Collector")
    parser.add_argument(
        "--target",
        type=int,
        default=500,
        help="Number of users to collect (default: 500)",
    )
    args = parser.parse_args()

    collector = GitHubBulkCollector(target=args.target)
    collector.run()
