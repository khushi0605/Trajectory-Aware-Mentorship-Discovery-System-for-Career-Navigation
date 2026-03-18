import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from src.core.interfaces import ICollector
from src.core.types import SourceType, Profile
from src.core.exceptions import CollectionError, DiscoveryError
from src.core.utils import retry
from src.storage.raw_repo import RawRepo
from src.ingestion.routing.data_router import DataRouter

try:
    from kaggle.api.kaggle_api_extended import KaggleApi
except ImportError:
    KaggleApi = None

logger = logging.getLogger("src.ingestion.collectors.kaggle")

class KaggleCollector(ICollector):
    """
    Kaggle data collector for ingesting professional trajectory signals.
    
    Supports:
    - User discovery from leaderboards.
    - Full profile & activity collection.
    - Raw-first storage via RawRepo.
    """
    
    def __init__(self, source_name: str = "kaggle", config: Optional[Dict[str, Any]] = None):
        self.source_name = SourceType.KAGGLE
        self.config = config or {}
        
        if KaggleApi is None:
            raise ImportError("Kaggle API package not installed. Run 'pip install kaggle'.")
            
        self.api = KaggleApi()
        try:
            self.api.authenticate()
        except Exception as e:
            logger.error(f"Kaggle authentication failed: {e}")
            raise
            
        self.repo = RawRepo()
        self.router = DataRouter()

    @retry(max_retries=3)
    def _api_call(self, func, *args, **kwargs):
        """Internal helper for retrying API calls."""
        return func(*args, **kwargs)

    def discover(self, **kwargs) -> List[str]:
        """
        Discover Kaggle usernames from competition leaderboards.
        
        Keywords:
            competition (str): Seed competition ID (default: "titanic")
            limit (int): Max users to discover (default: 50)
        """
        competition = kwargs.get("competition", "titanic")
        limit = kwargs.get("limit", 50)
        
        logger.info(f"Discovering users from Kaggle leaderboard: {competition}")
        try:
            results = self._api_call(self.api.competition_leaderboard_view, competition)
            if not results:
                return []
                
            # Extract distinct usernames (teamName is often the username in simple competitions)
            usernames = []
            for entry in results:
                uname = entry.teamName
                if uname and " " not in uname and uname not in usernames:
                    usernames.append(uname)
                if len(usernames) >= limit:
                    break
                    
            logger.info(f"Discovered {len(usernames)} usernames from {competition}")
            return usernames
        except Exception as e:
            logger.error(f"Failed to discover users from {competition}: {e}")
            raise DiscoveryError(f"Kaggle discovery failed: {e}")

    def collect(self, identifier: str) -> Dict[str, Any]:
        """
        Fetch full raw data for a specific Kaggle user.
        
        Signals collected:
        - Kernels (Notebooks)
        - Datasets
        - Metadata summary
        """
        logger.info(f"Collecting signals for Kaggle user: {identifier}")
        try:
            # Note: Official API doesn't have a single 'get_profile' call.
            # We aggregate activity signals as proxy for profile depth.
            
            # 1. Kernels
            kernels = self._api_call(self.api.kernels_list, user=identifier)
            kernels_raw = [k.__dict__ for k in kernels] if kernels else []
            
            # 2. Datasets
            datasets = self._api_call(self.api.dataset_list, user=identifier)
            datasets_raw = [d.__dict__ for d in datasets] if datasets else []
            
            raw_payload = {
                "username": identifier,
                "collected_at": datetime.now(timezone.utc).isoformat(),
                "signals": {
                    "kernels": kernels_raw,
                    "datasets": datasets_raw
                }
            }
            
            # 3. Store Raw
            path = self.router.get_raw_path(self.source_name, "profiles", identifier)
            self.repo.store(raw_payload, path)
            
            # 4. Optional: Basic validation using Profile model
            # Note: We keep it 'raw' but validate we have at least the identifier.
            try:
                Profile(
                    source=self.source_name,
                    username=identifier,
                    raw_data=raw_payload
                )
            except Exception as ve:
                logger.warning(f"Profile validation failed for {identifier}: {ve}")
                
            return raw_payload
            
        except Exception as e:
            logger.error(f"Failed to collect signals for {identifier}: {e}")
            raise CollectionError(f"Kaggle collection failed for {identifier}: {e}")

    def run(self, **kwargs) -> Path:
        """
        Orchestrate discovery and collection.
        
        Keywords:
            competition (str): Seed competition
            limit (int): Max users
        """
        usernames = self.discover(**kwargs)
        for uname in usernames:
            try:
                self.collect(uname)
                # Politeness delay
                time.sleep(1)
            except Exception as e:
                logger.warning(f"Skipping user {uname} due to error: {e}")
                
        return Path("data/raw/kaggle/profiles")
