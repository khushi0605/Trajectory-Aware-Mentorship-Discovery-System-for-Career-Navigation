import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse
import aiohttp
from src.core.utils import async_retry

logger = logging.getLogger("src.ingestion.collectors.github_client")

GITHUB_API_BASE = "https://api.github.com"

class GitHubClient:
    """Low-level async client for the GitHub REST API."""
    def __init__(
        self,
        token: Optional[str] = None,
        max_concurrency: int = 10,
        requests_per_second: float = 5.0,
    ):
        self.token = token
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._min_interval = 1.0 / requests_per_second
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()
        self._session: Optional[aiohttp.ClientSession] = None
        self.rate_limit_remaining: Optional[int] = None
        self.rate_limit_reset: Optional[float] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "MentorshipDiscovery/2.0",
            }
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            self._session = aiohttp.ClientSession(headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    def _update_rate_limit(self, headers: dict) -> None:
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")
        if remaining is not None: self.rate_limit_remaining = int(remaining)
        if reset is not None: self.rate_limit_reset = float(reset)

    async def _wait_for_rate_limit(self) -> None:
        if self.rate_limit_remaining is not None and self.rate_limit_remaining <= 1 and self.rate_limit_reset:
            now = datetime.now(timezone.utc).timestamp()
            sleep_for = self.rate_limit_reset - now + 1
            if sleep_for > 0:
                logger.info(f"Rate limit exhausted — sleeping {sleep_for:.1f}s")
                await asyncio.sleep(sleep_for)

    async def _throttle(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request = asyncio.get_event_loop().time()

    @async_retry(max_retries=4)
    async def get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        async with self._semaphore:
            await self._wait_for_rate_limit()
            await self._throttle()
            session = await self._get_session()
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                self._update_rate_limit(resp.headers)
                if resp.status == 403 and self.rate_limit_remaining == 0:
                    raise Exception("Rate limit exceeded")
                resp.raise_for_status()
                return await resp.json()

    async def get_all_pages(self, url: str, params: Optional[Dict[str, Any]] = None, max_pages: int = 10) -> List[Any]:
        p = dict(params or {})
        p.setdefault("per_page", 100)
        all_items = []
        curr_url = url
        page = 0
        while curr_url and page < max_pages:
            page += 1
            async with self._semaphore:
                await self._wait_for_rate_limit()
                await self._throttle()
                session = await self._get_session()
                async with session.get(curr_url, params=p if page == 1 else None, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                    self._update_rate_limit(resp.headers)
                    resp.raise_for_status()
                    data = await resp.json()
                    if isinstance(data, list): all_items.extend(data)
                    else: all_items.append(data)
                    curr_url = self._parse_next_link(resp.headers.get("Link", ""))
        return all_items

    @staticmethod
    def _parse_next_link(link_header: str) -> Optional[str]:
        if not link_header: return None
        for part in link_header.split(","):
            if 'rel="next"' in part:
                return part.split(";")[0].strip().strip("<>")
        return None
