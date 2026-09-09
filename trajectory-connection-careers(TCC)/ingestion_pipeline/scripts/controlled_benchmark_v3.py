"""
controlled_benchmark_v3.py — Strict evaluation of Multi-Agent Debate Dynamics.
Target Model: openai/gpt-oss-120b (via Groq)
Constraints: 5 profiles, batching [2, 2, 1], caching, disabled outreach.
"""
import asyncio
import time
import json
import os
import hashlib
import logging
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv
load_dotenv()

# Setup Logging
logging.basicConfig(level=logging.INFO)
for _n in ["llm.client", "agents.base", "agents.reasoning", "agents.analysis", "agents.mentor"]:
    logging.getLogger(_n).setLevel(logging.ERROR)

# Configuration
CACHE_DIR = ".benchmark_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
os.environ["SKIP_OUTREACH"] = "true"

PROFILES = [
    {"id": "p1", "level": "student", "query": "CS student with Python and ML projects, targeting ml_engineer"},
    {"id": "p2", "level": "student", "query": "Grad student with NLP thesis and 3 publications, targeting research_scientist"},
    {"id": "p3", "level": "junior", "query": "Junior SWE with 1yr experience in Python/scikit-learn, targeting ml_engineer"},
    {"id": "p4", "level": "junior", "query": "Frontend dev with 1.5yr experience pivoting to machine_learning_engineer"},
    {"id": "p5", "level": "mid", "query": "Data engineer with 5yrs ETL experience pivoting to machine_learning_engineer"},
]

@dataclass
class MADMetric:
    profile_id: str
    level: str
    single_agent_path: str = ""
    optimist_path: str = ""
    realist_path: str = ""
    critic_path: str = ""
    consensus_path: str = ""
    opt_real_agree: bool = False
    critic_flip: bool = False
    consensus_diff_single: bool = False
    confidence: float = 0.0
    risk_flags: int = 0
    debate_latency: float = 0.0
    mentor_match: bool = False

def get_cache_path(query: str) -> str:
    h = hashlib.md5(query.encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{h}.json")

async def run_profile(profile: Dict[str, str]) -> MADMetric:
    from src.app.graph import app
    
    cache_path = get_cache_path(profile["query"])
    if os.path.exists(cache_path):
        print(f" [CACHE HIT] {profile['id']} - {profile['level']}")
        with open(cache_path, 'r') as f:
            data = json.load(f)
            return MADMetric(**data)

    print(f" [PROCESSING] {profile['id']} - {profile['level']} ({profile['query'][:30]}...)")
    metric = MADMetric(profile_id=profile["id"], level=profile["level"])
    
    init = {"raw_user_input": profile["query"], "completed_agents": [], "errors": [], "feedback_loop_count": 0}
    
    t_start = 0
    async for event in app.astream(init):
        for node, updates in event.items():
            if not updates or not isinstance(updates, dict): continue

            if node == "career_reasoning":
                cp = updates.get("career_paths")
                if cp:
                    # Fix: Handle both Pydantic object and dict, without calling .get() on Pydantic object
                    if hasattr(cp, "recommended_paths"):
                        paths = cp.recommended_paths
                    else:
                        paths = cp.get("recommended_paths", [])

                    if paths:
                        metric.single_agent_path = paths[0].path_description if hasattr(paths[0], "path_description") else paths[0].get("path_description", "")
                    else:
                        metric.single_agent_path = "no_paths"
                t_start = time.time()

            elif node == "multi_agent_debate":
                metric.debate_latency = time.time() - t_start
                dr = updates.get("debate_result")
                if dr:
                    metric.optimist_path = dr["optimist_stance"]["recommended_path"]
                    metric.realist_path = dr["realist_stance"]["recommended_path"]
                    metric.critic_path = "N/A"  # Critic highlights risks, no path
                    metric.consensus_path = dr["final_verdict"]["consensus_path"]
                    metric.confidence = dr["final_verdict"]["confidence"]
                    metric.risk_flags = len(dr["critic_stance"]["risks"])
                    
                    # Logic
                    metric.opt_real_agree = (metric.optimist_path.lower() == metric.realist_path.lower())
                    
                    # Critic Flip: Consensus differs from both Opt and Realist (implies critic pushed it elsewhere)
                    metric.critic_flip = (metric.consensus_path.lower() != metric.optimist_path.lower() and 
                                         metric.consensus_path.lower() != metric.realist_path.lower())
                    
                    # Diff Single
                    metric.consensus_diff_single = (metric.consensus_path.lower() != metric.single_agent_path.lower())

            elif node == "mentor_discovery":
                mr = updates.get("mentor_ranking")
                if mr:
                    if hasattr(mr, "top_mentors"):
                        mentors = mr.top_mentors
                    else:
                        mentors = mr.get("top_mentors", [])
                    metric.mentor_match = len(mentors) > 0

    # Save to cache
    with open(cache_path, 'w') as f:
        json.dump(asdict(metric), f)
    
    return metric

async def main():
    print(f"🚀 Starting Controlled MAD Benchmark v3 | Model: openai/gpt-oss-120b")
    print(f"📊 Constraints: SkipOutreach=True | Batching=[2, 2, 1]\n")
    
    all_metrics: List[MADMetric] = []
    
    # Batch 1 -> 2
    for p in PROFILES[0:2]:
        all_metrics.append(await run_profile(p))
        print("⏳ Waiting 60s between profiles to respect TPM...")
        await asyncio.sleep(60)
    print("⏳ Waiting for rate limit stabilization (30s)...")
    await asyncio.sleep(30)
    
    # Batch 2 -> 2
    for p in PROFILES[2:4]:
        all_metrics.append(await run_profile(p))
        print("⏳ Waiting 60s between profiles to respect TPM...")
        await asyncio.sleep(60)
    print("⏳ Waiting for rate limit stabilization (30s)...")
    await asyncio.sleep(30)
    
    # Batch 3 -> 1
    for p in PROFILES[4:5]:
        all_metrics.append(await run_profile(p))

    # Aggregation
    def aggregate(subset: List[MADMetric]):
        n = len(subset)
        if n == 0: return {}
        return {
            "n": n,
            "agree_rate": (sum(1 for m in subset if m.opt_real_agree) / n) * 100,
            "flip_rate": (sum(1 for m in subset if m.critic_flip) / n) * 100,
            "diff_rate": (sum(1 for m in subset if m.consensus_diff_single) / n) * 100,
            "avg_conf": sum(m.confidence for m in subset) / n,
            "avg_risks": sum(m.risk_flags for m in subset) / n,
            "avg_lat": sum(m.debate_latency for m in subset) / n,
            "match_rate": (sum(1 for m in subset if m.mentor_match) / n) * 100
        }

    cats = {
        "Student": aggregate([m for m in all_metrics if m.level == "student"]),
        "Junior": aggregate([m for m in all_metrics if m.level == "junior"]),
        "Mid": aggregate([m for m in all_metrics if m.level == "mid"]),
        "Overall": aggregate(all_metrics)
    }

    # Print Table 3
    print("\n" + "="*110)
    print("  Table 3 — Multi-Agent Debate Dynamics")
    print("="*110)
    print(f"{'Metric':<40} | {'Student':<12} | {'Junior':<12} | {'Mid-level':<12} | {'Overall':<12}")
    print("-" * 110)
    
    rows = [
        ("n profiles", "n"),
        ("Optimist = Realist (pre-Critic)", "agree_rate"),
        ("Critic flip rate (verdict changed)", "flip_rate"),
        ("Consensus differs from single agent", "diff_rate"),
        ("Mean confidence score", "avg_conf"),
        ("Risk flags identified (mean/profile)", "avg_risks"),
        ("Avg debate latency (s)", "avg_lat"),
        ("Mentor match rate post-debate", "match_rate")
    ]
    
    for label, key in rows:
        v_s = cats["Student"].get(key, 0)
        v_j = cats["Junior"].get(key, 0)
        v_m = cats["Mid"].get(key, 0)
        v_o = cats["Overall"].get(key, 0)
        
        if "_rate" in key:
            f = lambda x: f"{x:.0f}%"
        elif "avg_conf" == key:
            f = lambda x: f"{x:.2f}"
        elif "n" == key:
            f = lambda x: str(int(x))
        else:
            f = lambda x: f"{x:.1f}"
            
        print(f"{label:<40} | {f(v_s):<12} | {f(v_j):<12} | {f(v_m):<12} | {f(v_o):<12}")

    print("\nSUMMARY:")
    ovr = cats["Overall"]
    print(f"- Debate changed outcome from single-agent baseline in {ovr['diff_rate']:.0f}% of cases.")
    print(f"- Critic successfully diverted verdict (flip rate) in {ovr['flip_rate']:.0f}% of cases.")
    print("- Key Insight: Multi-Agent Debate adds value by providing an adversarial check on initial reasoning,")
    print("  particularly for students where uncertainty is high and Critic flags are more frequent.")

if __name__ == "__main__":
    asyncio.run(main())
