import asyncio
import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from retrieval import RAGRetriever, RetrieverConfig

async def main():
    load_dotenv()
    
    # Load config
    try:
        config = RetrieverConfig.load("configs/retrieval.yaml")
        print("✅ Config loaded successfully.")
    except Exception as e:
        print(f"❌ Config loading failed: {e}")
        return

    # Initialize retriever
    retriever = RAGRetriever(config)
    print("✅ Retriever initialized.")

    # Sample query with Machine Learning data
    query_dict = {
        "background": "Data Analyst",
        "skills": ["Python", "PyTorch", "Calculus"],
        "interest": "machine learning",
        "goal": "machine_learning_scientist"
    }

    print(f"\n🔍 Retrieving context for query: {json.dumps(query_dict, indent=2)}")
    
    try:
        context = await retriever.retrieve(query_dict)
        
        print("\n--- Retrieval Results ---")
        print(f"Trajectory Paths found: {len(context.trajectory_paths)}")
        if context.trajectory_paths:
            print(f"Sample Path: {context.trajectory_paths[0].decision_text} -> {context.trajectory_paths[0].target_role}")
            
        print(f"Behavioral Signals found: {len(context.behavioral_signals)}")
        if context.behavioral_signals:
            print(f"Sample Signal: [{context.behavioral_signals[0].signal_type}] {context.behavioral_signals[0].text}")
            
        print(f"Narrative Chunks found: {len(context.narrative_chunks)}")
        if context.narrative_chunks:
            # Print first 100 chars of the first chunk
            chunk_text = context.narrative_chunks[0].text[:100].replace('\n', ' ') + "..."
            print(f"Sample Narrative: {chunk_text}")
        
        print("\n--- Metadata ---")
        print(json.dumps(context.metadata.model_dump(), indent=2))
        
        if context.metadata.failed_sources:
            print(f"\n⚠️ Warning: Some sources failed: {context.metadata.failed_sources}")
            
        print("\n✅ Verification complete.")
        
    except Exception as e:
        print(f"❌ Retrieval failed: {e}")
    finally:
        retriever.close()

if __name__ == "__main__":
    asyncio.run(main())
