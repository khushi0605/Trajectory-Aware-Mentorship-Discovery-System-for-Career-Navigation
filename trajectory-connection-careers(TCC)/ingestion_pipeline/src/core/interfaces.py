import abc
from typing import Any, Dict, List, Optional
from pathlib import Path

class ICollector(abc.ABC):
    """Interface for all data collectors."""
    
    @abc.abstractmethod
    def discover(self, **kwargs) -> List[str]:
        """Discover potential entities (usernames, IDs) for collection."""
        return []

    @abc.abstractmethod
    def collect(self, identifier: str) -> Dict[str, Any]:
        """Fetch raw data for a specific entity."""
        return {}
    
    @abc.abstractmethod
    def run(self, **kwargs) -> Path:
        """Run the full discovery and collection lifecycle."""
        return Path(".")

class IScraper(abc.ABC):
    """Interface for dynamic web scrapers."""
    
    @abc.abstractmethod
    def scrape(self, url: str) -> str:
        """Scrape content from a URL."""
        return ""
