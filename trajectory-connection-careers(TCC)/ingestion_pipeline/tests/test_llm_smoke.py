import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.llm import LLMClient, PromptBuilder, load_llm_config
from src.agents.models import UserProfile

async def main():
    load_dotenv()
    
    print("🧪 Starting LLM Smoke Test...")
    
    # 1. Load Config
    try:
        config = load_llm_config("configs/llm.yaml")
        print("✅ LLMConfig loaded from configs/llm.yaml")
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        return

    # 2. Instantiate Client and Builder
    client = GroqClient(config)
    builder = PromptBuilder()
    print("✅ GroqClient and PromptBuilder instantiated.")

    # 3. Call for_profile_understanding
    raw_input = "I'm a CS student, know Python and basic ML, interested in computer vision, not sure if research or industry"
    system, user = builder.for_profile_understanding(raw_input)
    print(f"\n📝 Generated Prompts for Profile Understanding:")
    print(f"--- System ---\n{system[:100]}...")
    print(f"--- User ---\n{user}")

    # 4. Generate Structured Output
    print("\n🤖 Calling GroqClient.generate_structured()...")
    try:
        profile = await client.generate_structured(system, user, UserProfile)
        
        # 5. Assertions
        assert isinstance(profile, UserProfile), "Result is not a UserProfile object"
        assert profile.background, "Background field is empty"
        assert profile.goal, "Goal field should be present (extracted even if uncertain)"
        
        print("\n✅ Smoke Test Passed!")
        print("\n--- Extracted User Profile ---")
        print(profile.model_dump_json(indent=2))
        
    except Exception as e:
        print(f"\n❌ Smoke Test Failed: {e}")
        if hasattr(e, '__dict__'):
            print(e.__dict__)

if __name__ == "__main__":
    asyncio.run(main())
