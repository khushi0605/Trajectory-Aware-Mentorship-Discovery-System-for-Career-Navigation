import streamlit as st
import os
import sys
import asyncio
import pandas as pd

# Ensure src is in the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from src.eval.evaluation_agent import EvaluationAgent
from src.llm import LLMClient, load_llm_config

load_dotenv()
llm_config = load_llm_config("configs/llm.yaml")
llm = LLMClient(llm_config)

st.set_page_config(page_title="GG-MAD Evaluation Dashboard", layout="wide")

TCC_DIR = "outputs/tcc_refined_results"
GEMINI_DIR = "outputs/gemini_llm_results"

st.title("📊 GG-MAD Evaluation & Results Tabulation")
st.markdown("""
This dashboard runs an LLM-as-a-Judge evaluation comparing the GG-MAD Pipeline against the Baseline Gemini LLM. 
Scores are calculated on a **1-10 scale** across four academic metrics:
*   **Empirical Grounding (EG):** Reliance on dataset-backed facts vs. parametric hallucinations.
*   **Feasibility Risk (FRA):** Identification of structural credential gaps.
*   **Actionability (ANP):** Concrete next steps and near-peer mentor matches.
*   **Goal Alignment (GSA):** Realistic mapping of current skills to future goals.
""")

def get_matching_files():
    """Finds matching profile outputs between the two directories."""
    tcc_files = {f.split('_')[0]: os.path.join(TCC_DIR, f) for f in os.listdir(TCC_DIR) if f.endswith('.md')}
    gemini_files = {f.split('_')[0]: os.path.join(GEMINI_DIR, f) for f in os.listdir(GEMINI_DIR) if f.endswith('.md')}
    
    common_profiles = set(tcc_files.keys()).intersection(set(gemini_files.keys()))
    
    # Sort them by integer ID to keep the evaluation orderly
    def get_int_id(pid):
        try:
            return int(pid)
        except:
            return pid
            
    sorted_profiles = sorted(list(common_profiles), key=get_int_id)
    return [{"profile_id": p, "tcc_path": tcc_files[p], "gemini_path": gemini_files[p]} for p in sorted_profiles]

async def run_evaluations():
    pairs = get_matching_files()
    if not pairs:
        st.error("No matching files found in the output directories.")
        return

    agent = EvaluationAgent(llm)
    progress_bar = st.progress(0)
    results_data = []

    st.header("1. Individual Profile Evaluations")
    
    import time
    
    for i, pair in enumerate(pairs):
        pid = pair["profile_id"]
        
        # 1. Use st.status for dynamic, visible progress
        with st.status(f"⏳ Evaluating Profile {pid}...", expanded=True) as status:
            try:
                st.write("📄 Loading Markdown files...")
                with open(pair["tcc_path"], "r") as f: tcc_text = f.read()
                with open(pair["gemini_path"], "r") as f: gemini_text = f.read()
                
                st.write("🤖 Sending to Evaluation Agent (LLM-as-a-judge)... *(This may take 30-60 seconds)*")
                
                start_time = time.time()
                
                # ACTUAL AGENT CALL (Ensure agent is instantiated before the loop)
                eval_result = await agent.evaluate_pair(tcc_text, gemini_text)
                
                duration = round(time.time() - start_time, 2)
                st.write(f"✅ Received LLM response in {duration} seconds!")
                
                # Display highly readable side-by-side metrics
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("GG-MAD (System A)")
                    st.metric("Empirical Grounding", eval_result.system_a_empirical_grounding)
                    st.metric("Feasibility Risk", eval_result.system_a_feasibility_risk)
                    st.metric("Actionability", eval_result.system_a_actionability)
                    st.metric("Goal Alignment", eval_result.system_a_goal_alignment)
                
                with col2:
                    st.subheader("Gemini Baseline (System B)")
                    st.metric("Empirical Grounding", eval_result.system_b_empirical_grounding)
                    st.metric("Feasibility Risk", eval_result.system_b_feasibility_risk)
                    st.metric("Actionability", eval_result.system_b_actionability)
                    st.metric("Goal Alignment", eval_result.system_b_goal_alignment)
                    
                st.info(f"**Judge Rationale:** {eval_result.rationale}")
                st.success(f"**Winner:** {eval_result.winner}")
                
                # Save for aggregation
                results_data.append({
                    "Profile ID": pid,
                    "TCC_EG": eval_result.system_a_empirical_grounding,
                    "TCC_FRA": eval_result.system_a_feasibility_risk,
                    "TCC_ANP": eval_result.system_a_actionability,
                    "TCC_GSA": eval_result.system_a_goal_alignment,
                    "Gemini_EG": eval_result.system_b_empirical_grounding,
                    "Gemini_FRA": eval_result.system_b_feasibility_risk,
                    "Gemini_ANP": eval_result.system_b_actionability,
                    "Gemini_GSA": eval_result.system_b_goal_alignment,
                })
                
                # Close the status box successfully
                status.update(label=f"✅ Profile {pid} Evaluated ({duration}s)", state="complete", expanded=False)
                
            except Exception as e:
                # 2. Maximum Error Visibility
                st.error(f"❌ Failed to evaluate Profile {pid}")
                st.error(f"Exact Error: {str(e)}")
                status.update(label=f"❌ Error on Profile {pid}", state="error", expanded=True)
                
                # Continue to the next profile instead of crashing the whole batch
                continue 
            
            # --- ADD VRAM COOLDOWN HERE ---
            # Wait 10 seconds before starting the next profile to allow local memory to clear
            if i < len(pairs) - 1:
                st.write("⏳ *Cooling down local inference server for 10 seconds to free VRAM...*")
                await asyncio.sleep(10)
            # ------------------------------
            
        progress_bar.progress((i + 1) / len(pairs))

    # --- GENERATE PAPER-READY TABLES ---
    st.divider()
    st.header("2. Research Paper Tables")
    
    df = pd.DataFrame(results_data)
    
    # Calculate Averages
    avg_data = {
        "Metric": ["Empirical Grounding (EG)", "Feasibility Risk (FRA)", "Actionability (ANP)", "Goal Alignment (GSA)"],
        "Gemini Baseline (Mean)": [df["Gemini_EG"].mean(), df["Gemini_FRA"].mean(), df["Gemini_ANP"].mean(), df["Gemini_GSA"].mean()],
        "GG-MAD (Mean)": [df["TCC_EG"].mean(), df["TCC_FRA"].mean(), df["TCC_ANP"].mean(), df["TCC_GSA"].mean()],
    }
    avg_df = pd.DataFrame(avg_data)
    
    # Calculate % Improvement
    avg_df["Improvement (%)"] = (((avg_df["GG-MAD (Mean)"] - avg_df["Gemini Baseline (Mean)"]) / avg_df["Gemini Baseline (Mean)"]) * 100).round(1).astype(str) + "%"
    
    st.subheader("Table 1: Quantitative Performance Comparison")
    st.markdown("Use this table directly in your **Results & Evaluation** section.")
    st.dataframe(avg_df, use_container_width=True)
    
    # LaTeX Export for Overleaf/Word
    st.download_button(
        label="📥 Download Table as CSV (For LaTeX/Excel)",
        data=avg_df.to_csv(index=False),
        file_name="ggmad_quantitative_results.csv",
        mime="text/csv"
    )

if st.button("▶️ Run Full Evaluation Pipeline", type="primary"):
    asyncio.run(run_evaluations())
