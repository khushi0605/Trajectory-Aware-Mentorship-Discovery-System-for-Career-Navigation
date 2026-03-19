import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.interfaces import ICollector
from src.core.utils import save_json
from src.ingestion.collectors.github_client import GitHubClient, GITHUB_API_BASE
from src.storage.raw_repo import RawRepo
from src.ingestion.routing.data_router import DataRouter

logger = logging.getLogger("src.ingestion.collectors.github")

class GitHubCollector(ICollector):
    """Async collector for comprehensive GitHub developer data."""
    
    def __init__(self, source_name: str = "github", config: Optional[Dict[str, Any]] = None):
        self.source_name = source_name
        self.config = config or {}
        self.repo = RawRepo()
        self.router = DataRouter()
        
        self.client = GitHubClient(
            token=self.config.get("github_token"),
            max_concurrency=self.config.get("concurrency", 5),
            requests_per_second=self.config.get("rate_limit", 5),
        )

    def discover(self, **kwargs) -> List[str]:
        """GitHub discovery (placeholder for now, returns provided usernames)."""
        return kwargs.get("usernames", [])

    async def _collect_user(self, username: str) -> Dict[str, Any]:
        logger.info(f"Collecting data for user={username}")
        
        try:
            # 1. Fetch Profile for followers
            profile = await self.client.get(f"{GITHUB_API_BASE}/users/{username}")
            
            # 2. Fetch Repositories
            repos_raw = await self.client.get_all_pages(
                f"{GITHUB_API_BASE}/users/{username}/repos",
                params={"sort": "updated", "type": "owner"},
                max_pages=5
            )
            
            # 3. Commit search for Total Commits
            # Search API for commits by author
            total_commits = 0
            try:
                search_res = await self.client.get(
                    f"{GITHUB_API_BASE}/search/commits",
                    params={"q": f"author:{username}"}
                )
                total_commits = search_res.get("total_count", 0)
            except Exception as e:
                logger.warning(f"Failed to fetch commit count for {username}: {e}")

            # 4. Map and Aggregate
            repositories = []
            languages_set = set()
            
            for repo in repos_raw:
                lang = repo.get("language")
                if lang:
                    languages_set.add(lang)
                
                repositories.append({
                    "name": repo.get("name"),
                    "description": repo.get("description"),
                    "language": lang,
                    "stars": repo.get("stargazers_count"),
                    "topics": repo.get("topics", []),
                    "created_at": repo.get("created_at")
                })

            # Assemble Final Record
            return {
                "username": username,
                "repositories": repositories,
                "languages": list(languages_set),
                "total_commits": str(total_commits), # Matching user's string format in schema
                "followers": str(profile.get("followers", 0)),
                "collected_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as exc:
            logger.error(f"Failed to collect for {username}: {exc}")
            return {
                "username": username,
                "error": str(exc),
                "collected_at": datetime.now(timezone.utc).isoformat()
            }

    def collect(self, identifier: str) -> Dict[str, Any]:
        """Fetch raw data for a specific GitHub user (legacy sync wrapper)."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            res = loop.run_until_complete(self._collect_user(identifier))
            path = self.router.get_raw_path(self.source_name, "profiles", identifier)
            self.repo.store(res, path)
            loop.run_until_complete(self.client.close())
            return res
        finally:
            loop.close()

    def run(self, **kwargs) -> Path:
        """Run discovery and collection in a single event loop."""
        usernames = self.discover(**kwargs)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            for uname in usernames:
                res = loop.run_until_complete(self._collect_user(uname))
                path = self.router.get_raw_path(self.source_name, "profiles", uname)
                self.repo.store(res, path)
            
            # Critical: close session before closing loop
            loop.run_until_complete(self.client.close())
        finally:
            loop.close()
            
        return Path("data/raw/profiles")
