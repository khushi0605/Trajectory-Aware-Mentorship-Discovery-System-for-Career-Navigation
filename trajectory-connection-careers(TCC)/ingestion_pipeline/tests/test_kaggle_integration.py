import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path.cwd()))

from src.ingestion.collectors.kaggle_collector import KaggleCollector

logging.basicConfig(level=logging.INFO)

def test_kaggle_integration():
    print("--- Starting Kaggle Integration Test ---")
    try:
        collector = KaggleCollector()
        
        # 1. Test Discovery
        print("\n[1] Testing Discovery...")
        # Limiting to 2 for speed
        usernames = collector.discover(competition="titanic", limit=2)
        print(f"Discovered users: {usernames}")
        
        if not usernames:
            print("No users discovered. Check competition ID or API connectivity.")
            return

        # 2. Test Collection
        print("\n[2] Testing Collection for first user...")
        user_to_collect = usernames[0]
        data = collector.collect(user_to_collect)
        
        print(f"Collected data for {user_to_collect}")
        print(f"Stored at: data/raw/kaggle/profiles/{user_to_collect}.json")
        
        print("\n--- Integration Test Successful ---")
        
    except Exception as e:
        print(f"\n--- Integration Test Failed: {e} ---")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_kaggle_integration()
