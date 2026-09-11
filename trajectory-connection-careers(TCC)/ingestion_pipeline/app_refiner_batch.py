import streamlit as st
import os
import asyncio
import time
import sys

# Ensure src is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.agents.report_refiner import ReportRefinerAgent
from src.llm import LLMClient, load_llm_config

st.set_page_config(page_title="TCC Report Refiner", layout="wide")

st.title("✨ GG-MAD Report Refinement Pipeline")
st.markdown("This dashboard takes the raw, clinical TCC Markdown reports and uses an LLM to rewrite them into highly actionable, phased career guides while preserving all empirical graph data.")

INPUT_DIR = "outputs/tcc_results"
OUTPUT_DIR = "outputs/tcc_refined_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def get_raw_files():
    if not os.path.exists(INPUT_DIR): return []
    files = [f for f in os.listdir(INPUT_DIR) if f.endswith('.md')]
    # Sort files numerically by the prefix ID
    files.sort(key=lambda x: int(x.split('_')[0]))
    return files

raw_files = get_raw_files()
st.subheader(f"Found {len(raw_files)} Raw Reports to Refine")

if st.button("▶️ Start Batch Refinement", type="primary"):
    config = load_llm_config("configs/llm.yaml")
    llm = LLMClient(config)
    refiner = ReportRefinerAgent(llm)
    progress_bar = st.progress(0)
    
    # Need to run asyncio event loop in streamlit
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    for i, filename in enumerate(raw_files):
        profile_id = filename.split('_')[0]
        input_path = os.path.join(INPUT_DIR, filename)
        output_path = os.path.join(OUTPUT_DIR, f"{profile_id}_refined.md")
        
        if os.path.exists(output_path):
            st.write(f"⏭️ Skipping {profile_id}: Refined report already exists.")
            progress_bar.progress((i + 1) / len(raw_files))
            continue
            
        with st.status(f"✨ Refining Profile {profile_id}...", expanded=True) as status:
            try:
                with open(input_path, "r") as f: 
                    raw_text = f.read()
                
                st.write("🤖 Sending to Refiner Agent... *(This may take 30-60 seconds)*")
                start_time = time.time()
                
                # ACTUAL AGENT CALL
                refined_text = loop.run_until_complete(refiner.refine_report(raw_text))
                
                # Save the refined output
                with open(output_path, "w") as f:
                    f.write(refined_text)
                
                duration = round(time.time() - start_time, 2)
                st.write(f"✅ Report rewritten and saved in {duration} seconds!")
                
                # Show a quick preview in the UI
                with st.expander("Preview Refined Report"):
                    st.markdown(refined_text)
                
                status.update(label=f"✅ Profile {profile_id} Refined ({duration}s)", state="complete", expanded=False)
                
            except Exception as e:
                st.error(f"❌ Failed to refine Profile {profile_id}")
                st.error(f"Exact Error: {str(e)}")
                status.update(label=f"❌ Error on Profile {profile_id}", state="error", expanded=True)
            
            # VRAM Cooldown for Local Model
            if i < len(raw_files) - 1:
                st.write("⏳ *Cooling down local inference server for 10 seconds to free VRAM...*")
                loop.run_until_complete(asyncio.sleep(10))
                
        progress_bar.progress((i + 1) / len(raw_files))
        
    st.success("🎉 All reports have been successfully refined!")
