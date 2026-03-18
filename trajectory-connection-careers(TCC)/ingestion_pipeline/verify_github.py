import asyncio
import json
import os
import sys

# Ensure project root is in path
sys.path.append(os.getcwd())

from src.ingestion.collectors.github_collector import GitHubCollector

async def verify_github(username):
    # Use GITHUB_TOKEN if available for higher rate limits
    token = os.environ.get("GITHUB_TOKEN")
    collector = GitHubCollector(config={"github_token": token})
    
    print(f"Starting GitHub verification for: {username}")
    try:
        # We use the internal async method for verification
        data = await collector._collect_user(username)
        
        if "error" in data:
            print(f"\nCollection Failed: {data['error']}")
        else:
            print("\nExtracted Data Summary:")
            print(f"Username: {data.get('username')}")
            print(f"Followers: {data.get('followers')}")
            print(f"Total Commits: {data.get('total_commits')}")
            print(f"Languages: {', '.join(data.get('languages', []))}")
            print(f"Repository Count: {len(data.get('repositories', []))}")
            
            if data.get('repositories'):
                first_repo = data['repositories'][0]
                print(f"\nExample Repository: {first_repo['name']}")
                print(f"  Description: {first_repo['description']}")
                print(f"  Stars: {first_repo['stars']}")
                print(f"  Topics: {', '.join(first_repo['topics'])}")
            
            # Save for inspection
            output_file = f"github_verification_{username}.json"
            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"\nFull data saved to {output_file}")
            
    except Exception as e:
        print(f"Verification failed: {e}")
    finally:
        await collector.client.close()

if __name__ == "__main__":
    uname = sys.argv[1] if len(sys.argv) > 1 else "torvalds"
    asyncio.run(verify_github(uname))
