import streamlit as st
import asyncio
import os
import sys
import glob
import time
import subprocess
import pandas as pd
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).resolve().parent.parent if "src" in str(Path(__file__)) else Path(__file__).resolve().parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.ingestion.resume_parser import parse_resume
from src.ingestion.resume_merger import merge_resume_with_query
from src.app.runner import run_pipeline_stream
from src.pipeline.ingestion_orchestrator import run_pipeline as run_ingestion

# Add custom CSS for aesthetics
st.set_page_config(
    page_title="TCC Mentorship Intelligence",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0e1117;
        color: #fafafa;
        font-family: 'Inter', sans-serif;
    }
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: -webkit-linear-gradient(45deg, #FF6B6B, #4ECDC4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 20px;
    }
    .status-indicator {
        display: inline-block;
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 5px;
    }
    .status-connected { background-color: #4ECDC4; }
    .status-disconnected { background-color: #FF6B6B; }
</style>
""", unsafe_allow_html=True)

def check_backend_status():
    # Simple check for Ollama and Neo4j
    import requests
    ollama_status = False
    neo4j_status = False
    
    try:
        r = requests.get("http://localhost:11434/")
        if r.status_code == 200:
            ollama_status = True
    except:
        pass

    try:
        from neo4j import GraphDatabase
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        pwd = os.getenv("NEO4J_PASSWORD", "tcc-graph")
        driver = GraphDatabase.driver(uri, auth=(user, pwd))
        driver.verify_connectivity()
        neo4j_status = True
        driver.close()
    except:
        pass
    return ollama_status, neo4j_status

def format_event_output(node_name, updates):
    # Mapping agent name to state key
    mapping = {
        "profile_understanding": "user_profile",
        "experience_retrieval": "retrieval_context",
        "career_reasoning": "career_paths",
        "multi_agent_debate": "debate_result",
        "experience_analysis": "experience_insights",
        "mentor_discovery": "mentor_ranking",
        "outreach": "outreach_drafts",
        "feedback": "feedback"
    }
    key = mapping.get(node_name)
    if key and updates.get(key):
        val = updates[key]
        if node_name == "multi_agent_debate":
            from src.agents.multi_agent_debate import format_debate_summary
            return format_debate_summary(val)
        elif hasattr(val, "model_dump_json"):
            return val.model_dump_json(indent=2)
        elif isinstance(val, list):
            import json
            return json.dumps([d.model_dump() if hasattr(d, "model_dump") else d for d in val], indent=2)
        else:
            return str(val)
    elif node_name == "experience_retrieval":
        ctx = updates.get("retrieval_context")
        if ctx:
            return f"Neo4j Paths Found: {len(ctx.trajectory_paths)}\nBehavioral Signals: {len(ctx.behavioral_signals)}\nNarrative Chunks: {len(ctx.narrative_chunks)}"
    return str(updates)

async def run_and_stream(query):
    final_output = None
    with st.status("🔮 Deep Thinking... Pipeline Initialized", expanded=True) as status:
        async for event in run_pipeline_stream(query):
            for node_name, updates in event.items():
                if not updates or not isinstance(updates, dict):
                    continue
                with st.expander(f"Agent: {node_name.replace('_', ' ').title()}"):
                    formatted = format_event_output(node_name, updates)
                    st.code(formatted, language="json" if "{" in formatted else "markdown")
                # Keep track for final feedback
                if node_name == "feedback" and updates.get("feedback"):
                    final_output = updates["feedback"]
        status.update(label="✅ Pipeline Execution Complete!", state="complete", expanded=False)
    return final_output

def main():
    st.sidebar.markdown("<h2 style='text-align: center;'>TCC Control Panel</h2>", unsafe_allow_html=True)
    
    # Toggle Mode
    mode = st.sidebar.radio("Select Mode", ["Career Mentorship", "Data Ingestion", "System Diagnostics & Benchmarks"])
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Backend Status")
    
    ollama_ok, neo4j_ok = check_backend_status()
    
    o_cls = "status-connected" if ollama_ok else "status-disconnected"
    n_cls = "status-connected" if neo4j_ok else "status-disconnected"
    
    st.sidebar.markdown(f"<div><span class='status-indicator {o_cls}'></span> Ollama ({'Connected' if ollama_ok else 'Disconnected'})</div>", unsafe_allow_html=True)
    st.sidebar.markdown(f"<div><span class='status-indicator {n_cls}'></span> Neo4j ({'Connected' if neo4j_ok else 'Disconnected'})</div>", unsafe_allow_html=True)
    
    if mode == "Career Mentorship":
        st.markdown("<div class='main-header'>Trajectory-Aware Career Intelligence</div>", unsafe_allow_html=True)
        st.markdown("Upload your resume and provide context to get tailored career trajectories and mentorship discovery.")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            resume_file = st.file_uploader("📄 Upload Resume", type=["pdf", "txt"])
            background = st.text_area("Background & Skills", height=150, placeholder="e.g. 5 years as a backend engineer working with Python...")
            goals = st.text_area("Career Goals", height=100, placeholder="e.g. Transitioning into AI architecture...")
            submit = st.button("Generate Mentorship Advice", type="primary", use_container_width=True)
            
        with col2:
            if submit:
                if not background and not goals:
                    st.warning("Please provide some background or career goals.")
                else:
                    resume_text = ""
                    if resume_file is not None:
                        # Save temp file
                        temp_path = f"/tmp/{resume_file.name}"
                        with open(temp_path, "wb") as f:
                            f.write(resume_file.getbuffer())
                        try:
                            resume_text = parse_resume(temp_path)
                            st.success(f"Resume loaded successfully!")
                        except Exception as e:
                            st.error(f"Failed to parse resume: {e}")
                    
                    user_query = f"Background: {background}\nGoals: {goals}"
                    if resume_text:
                        enriched_input = merge_resume_with_query(resume_text, user_query)
                    else:
                        enriched_input = user_query
                        
                    final_state = asyncio.run(run_and_stream(enriched_input))
                    
                    st.markdown("### 🏆 Final Mentorship Advice")
                    if final_state:
                        # Depending on feedback object structure
                        st.markdown(str(final_state))
                    else:
                        st.success("Pipeline executed successfully. View expanders for details.")

    elif mode == "Data Ingestion":
        st.markdown("<div class='main-header'>Batch Data Ingestion</div>", unsafe_allow_html=True)
        st.markdown("Trigger batch processing for data ingestion into Neo4j and ChromaDB.")
        
        source = st.selectbox("Select Source", ["github", "kaggle"])
        usernames = st.text_input("Usernames (comma separated for GitHub)", placeholder="octocat, torvalds")
        batch_limit = st.number_input("Batch Limit (for Kaggle)", min_value=1, max_value=100, value=10)
        enable_neo4j = st.checkbox("Enable Neo4j Graph Ingestion", value=True)
        enrich_eacr = st.checkbox("Execute Phase 2 EACR Enrichment", value=True)
        
        if st.button("🚀 Run Batch Ingestion", type="primary"):
            with st.spinner(f"Running batch ingestion for {source}..."):
                user_list = [u.strip() for u in usernames.split(",")] if usernames else None
                try:
                    run_ingestion(source=source, usernames=user_list, batch_limit=batch_limit, enable_neo4j=enable_neo4j, enrich_eacr=enrich_eacr)
                    st.success(f"Batch ingestion completed for {source}!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Ingestion failed: {e}")

    elif mode == "System Diagnostics & Benchmarks":
        st.markdown("<div class='main-header'>System Diagnostics & Benchmarks</div>", unsafe_allow_html=True)
        st.markdown("Run profiling, diagnostics, and evaluations directly from the UI.")
        
        script_options = {
            "Database Diagnostics": "scripts/db_stats.py",
            "Pipeline Profiler": "scripts/benchmark_pipeline.py",
            "Multi-Agent Debate Evaluation": "scripts/benchmark_mad.py",
            "Research / Table 4 Metrics": "scripts/table4_benchmark.py",
            "Controlled Experiments": "scripts/controlled_benchmark_v3.py"
        }
        
        selected_script = st.selectbox("Select Script to Run", list(script_options.keys()))
        script_path = script_options[selected_script]
        
        st.info(f"Ready to run `{script_path}`")
        
        if st.button("🚀 Run Script", type="primary"):
            st.divider()
            st.markdown("### Execution Logs")
            
            log_container = st.empty()
            
            try:
                cmd = [sys.executable, "-u", script_path]
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True, 
                    cwd=project_root,
                    bufsize=1
                )
                
                logs = []
                for line in iter(process.stdout.readline, ''):
                    logs.append(line)
                    # Show only last 100 lines to avoid UI lag
                    display_logs = logs[-100:] if len(logs) > 100 else logs
                    log_container.code("".join(display_logs), language="bash")
                    
                process.stdout.close()
                return_code = process.wait()
                
                # Show full logs at the end
                log_container.code("".join(logs), language="bash")
                
                if return_code == 0:
                    st.success(f"Script `{script_path}` completed successfully!")
                else:
                    st.error(f"Script `{script_path}` exited with code {return_code}.")
                    
                st.divider()
                st.markdown("### Output Artifacts")
                
                # Check for new files in .benchmark_cache or .table4_cache
                cache_dirs = [os.path.join(project_root, ".benchmark_cache"), os.path.join(project_root, ".table4_cache")]
                found_new = False
                
                for cdir in cache_dirs:
                    if os.path.exists(cdir):
                        # Look for CSVs generated within the last 5 minutes
                        csv_files = glob.glob(os.path.join(cdir, "*.csv"))
                        current_time = time.time()
                        
                        recent_csvs = [f for f in csv_files if current_time - os.path.getmtime(f) < 300]
                        
                        for csv_file in recent_csvs:
                            found_new = True
                            st.markdown(f"**Found recent result data: `{os.path.basename(csv_file)}`**")
                            df = pd.read_csv(csv_file)
                            st.dataframe(df, use_container_width=True)
                            
                            # Simple viz if looks like a metric table
                            numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns
                            if len(numeric_cols) > 0 and len(df) < 50:
                                with st.expander("Visualize Metrics"):
                                    # try to find a sensible index
                                    str_cols = df.select_dtypes(include=['object']).columns
                                    if len(str_cols) > 0:
                                        st.bar_chart(df.set_index(str_cols[0])[numeric_cols])
                                    else:
                                        st.bar_chart(df[numeric_cols])
                                        
                if not found_new:
                    st.info("No new CSV results were detected in the cache folders.")
                    
            except Exception as e:
                st.error(f"Error running script: {e}")

if __name__ == "__main__":
    main()
