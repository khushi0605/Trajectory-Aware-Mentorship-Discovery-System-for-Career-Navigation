import streamlit as st
import json
import asyncio
import time
import os
import sys

# Ensure src is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.app.runner import run_pipeline_stream
from src.utils.markdown_agent import MarkdownGeneratorAgent
from src.app.graph import app as graph_app # needed if I need to run pipeline directly, but run_pipeline_stream works

st.set_page_config(page_title="GG-MAD Batch Evaluator", layout="wide")

st.title("🧪 GG-MAD Batch Evaluation Harness")

# 1. Load Data
try:
    with open("test_data/batch_inputs.json", "r") as f:
        batch_data = json.load(f)
except FileNotFoundError:
    st.error("test_data/batch_inputs.json not found. Run extract_profiles.py first.")
    st.stop()

st.subheader(f"Loaded {len(batch_data)} Profiles for Testing")
st.dataframe([{"ID": d["profile_id"], "Background": d["background_and_skills"], "Goal": d["goal"]} for d in batch_data])

async def run_profile(profile_data, status):
    profile_id = profile_data["profile_id"]
    background = profile_data["background_and_skills"]
    goal = profile_data["goal"]
    
    # Combined string as raw_user_input for the pipeline
    raw_user_input = f"{background} {goal}"
    
    final_state = None
    
    # Run the streaming pipeline
    async for event in run_pipeline_stream(raw_user_input):
        for node_name, updates in event.items():
            if not updates or not isinstance(updates, dict):
                continue
            
            # Simple visibility map
            visibility_map = {
                "profile_understanding": "⏳ Agent 1: Profile Understanding...",
                "experience_retrieval": "⏳ Agent 2 & 3: Experience Retrieval...",
                "career_reasoning": "⏳ Agent 3: Career Reasoning...",
                "multi_agent_debate": "⏳ Agent: Multi-Agent Debate (Optimist vs Realist vs Critic)...",
                "experience_analysis": "⏳ Agent 4: Experience Analysis...",
                "mentor_discovery": "⏳ Agent 5: Mentor Discovery...",
                "outreach": "⏳ Agent 6: Outreach...",
                "feedback": "⏳ Agent 7: Feedback..."
            }
            
            label = visibility_map.get(node_name, f"⏳ Running {node_name}...")
            st.write(label)
            
            if "completed_agents" in updates:
                final_state = updates # Updates will be merged into state eventually, but since we are yielding event, event is just the delta. Let's just track final state manually
                
    # To get the true final state, we might need to invoke the graph or maintain a state dict
    # run_pipeline_stream doesn't return final state, it yields events. We should build the state.
    state = {
        "raw_user_input": raw_user_input,
        "completed_agents": [],
        "errors": [],
        "feedback_loop_count": 0
    }
    async for event in run_pipeline_stream(raw_user_input):
        for node_name, updates in event.items():
            if updates and isinstance(updates, dict):
                for k, v in updates.items():
                    state[k] = v
                label = visibility_map.get(node_name, f"⏳ Running {node_name}...")
                st.write(label)
    
    return state
    
if st.button("🚀 Start Batch Processing", type="primary"):
    progress_bar = st.progress(0)
    
    # Need to run asyncio event loop in streamlit
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    for i, profile_data in enumerate(batch_data):
        profile_id = profile_data["profile_id"]
        
        output_path = os.path.join("outputs/tcc_results", f"{profile_id}_report.md")
        if os.path.exists(output_path):
            st.write(f"⏭️ Skipping {profile_id}: GG-MAD Report already exists.")
            progress_bar.progress((i + 1) / len(batch_data))
            continue

        # Max Visibility: Create a status container for the current profile
        with st.status(f"Processing Profile: {profile_id}...", expanded=True) as status:
            try:
                # To capture state, we need a wrapper since run_pipeline_stream is an async generator
                async def run_and_capture(raw_user_input):
                    state = {
                        "raw_user_input": raw_user_input,
                        "completed_agents": [],
                        "errors": [],
                        "feedback_loop_count": 0
                    }
                    visibility_map = {
                        "profile_understanding": "⏳ Agent 1: Profile Understanding...",
                        "experience_retrieval": "⏳ Agent 2 & 3: Experience Retrieval...",
                        "career_reasoning": "⏳ Agent 3: Career Reasoning...",
                        "multi_agent_debate": "⏳ Agent: Multi-Agent Debate (Optimist vs Realist vs Critic)...",
                        "experience_analysis": "⏳ Agent 4: Experience Analysis...",
                        "mentor_discovery": "⏳ Agent 5: Mentor Discovery...",
                        "outreach": "⏳ Agent 6: Outreach...",
                        "feedback": "⏳ Agent 7: Feedback..."
                    }
                    async for event in run_pipeline_stream(raw_user_input):
                        for node_name, updates in event.items():
                            if updates and isinstance(updates, dict):
                                for k, v in updates.items():
                                    state[k] = v
                                label = visibility_map.get(node_name, f"⏳ Running {node_name}...")
                                st.write(label)
                    return state

                raw_input = f"Background: {profile_data['background_and_skills']} Goal: {profile_data['goal']}"
                if profile_data.get("resume_text"):
                    raw_input += f"\n\n--- RESUME ---\n{profile_data['resume_text']}"
                
                # ACTUAL PIPELINE CALL
                final_state = loop.run_until_complete(run_and_capture(raw_input))
                
                # Generate Markdown
                st.write("📝 Formatting Output to Markdown...")
                md_report, path = MarkdownGeneratorAgent.generate_report(profile_id, final_state)
                
                status.update(label=f"✅ Completed: {profile_id}", state="complete", expanded=False)
                
            except Exception as e:
                st.error(f"Failed on {profile_id}: {str(e)}")
                status.update(label=f"❌ Failed: {profile_id}", state="error", expanded=True)
                
        # Update global progress
        progress_bar.progress((i + 1) / len(batch_data))

    st.success("🎉 Batch Processing Complete! All markdown reports saved to outputs/tcc_results/")
