import os
import json
import logging
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone

from src.core.interfaces import IScraper

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger(__name__)

class GitHubScraper(IScraper):
    """
    Standalone scraper to fetch GitHub user data using the REST API.
    """
    BASE_URL = "https://api.github.com"

    def __init__(self, token=None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "TCC-Ingestion-Scraper"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"
        else:
            logger.warning("No GITHUB_TOKEN found. Rate limits will be strictly enforced.")

    def fetch_user_profile(self, username):
        """Fetch basic user info including followers."""
        url = f"{self.BASE_URL}/users/{username}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def fetch_repositories(self, username):
        """Fetch all public repositories for a user."""
        url = f"{self.BASE_URL}/users/{username}/repos"
        params = {"type": "owner", "sort": "updated", "per_page": 100}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def fetch_total_commits(self, username):
        """Fetch total commit count using the Search API."""
        url = f"{self.BASE_URL}/search/commits"
        params = {"q": f"author:{username}"}
        # Search API requires a specific media type for commits
        headers = self.headers.copy()
        headers["Accept"] = "application/vnd.github.cloak-preview"
        
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json().get("total_count", 0)
        else:
            logger.warning(f"Failed to fetch commit count: {response.status_code}")
            return 0

    def scrape(self, username):
        """
        Main method to aggregate user data into requested schema.
        """
        logger.info(f"Scraping GitHub data for user: {username}")
        
        try:
            profile = self.fetch_user_profile(username)
            repos_raw = self.fetch_repositories(username)
            total_commits = self.fetch_total_commits(username)

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

            data = {
                "username": username,
                "repositories": repositories,
                "languages": sorted(list(languages_set)),
                "total_commits": str(total_commits),
                "followers": str(profile.get("followers", 0))
            }

            return data

        except Exception as e:
            logger.error(f"Error scraping {username}: {e}")
            raise

if __name__ == "__main__":
    import sys
    
    # Simple CLI for testing
    test_user = sys.argv[1] if len(sys.argv) > 1 else "octocat"
    
    scraper = GitHubScraper()
    try:
        user_data = scraper.scrape(test_user)
        print(json.dumps(user_data, indent=2))
    except Exception as e:
        print(f"Failed to fetch data: {e}")
