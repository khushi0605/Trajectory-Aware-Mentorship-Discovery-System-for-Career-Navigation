import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.app.runner import run_pipeline

async def test_e2e():
    load_dotenv()
    
    # Input from spec
    user_input = "I'm a CS student, I know Python and some ML basics, I'm interested in computer vision. I don't know if I should go research or industry."
    
    print("🚀 Running E2E Pipeline Test...")
    
    try:
        state = await run_pipeline(user_input)
        
        print("\n--- [FINAL ASSERTIONS] ---")
        
        # 1. User Profile
        assert state.get("user_profile") is not None, "user_profile is None"
        assert state["user_profile"].background != "", "background is empty"
        assert state["user_profile"].goal != "", "goal is empty"
        print("✅ User Profile Assertion Passed")
        
        # 2. Retrieval Context
        assert state.get("retrieval_context") is not None, "retrieval_context is None"
        print(f"DEBUG: neo4j_path_count = {state['retrieval_context'].metadata.neo4j_path_count}")
        assert state["retrieval_context"].metadata.neo4j_path_count > 0, "No Neo4j paths found (Data mismatch?)"
        print("✅ Retrieval Context Assertion Passed")
        
        # 3. Career Paths
        assert state.get("career_paths") is not None, "career_paths is None"
        assert len(state["career_paths"].recommended_paths) > 0, "No recommended paths found"
        print("✅ Career Paths Assertion Passed")
        
        # 4. Mentor Ranking
        assert state.get("mentor_ranking") is not None, "mentor_ranking is None"
        assert len(state["mentor_ranking"].top_mentors) > 0, "No mentors ranked"
        print("✅ Mentor Ranking Assertion Passed")
        
        # 5. Outreach Drafts
        assert state.get("outreach_drafts") is not None, "outreach_drafts is None"
        assert len(state["outreach_drafts"]) > 0, "No outreach drafts generated"
        print("✅ Outreach Drafts Assertion Passed")
        
        # 6. Errors and Completion
        assert len(state["errors"]) == 0, f"Errors found in state: {state['errors']}"
        assert len(state["completed_agents"]) >= 6, f"Expected at least 6 agents to complete, got {len(state['completed_agents'])}"
        print("✅ Pipeline Logic Assertion Passed")
        
        print("\n✨ ALL E2E ASSERTIONS PASSED! ✨")
        
    except Exception as e:
        print(f"\n❌ E2E Test Failed: {e}")
        # Print state if possible for debugging
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_e2e())
