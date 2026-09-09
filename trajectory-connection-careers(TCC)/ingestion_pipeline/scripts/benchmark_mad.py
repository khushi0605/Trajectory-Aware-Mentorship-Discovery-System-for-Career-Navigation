"""
benchmark_mad.py — Dedicated evaluation script for Multi-Agent Debate Dynamics.
Runs 15 profiles and extracts specific insights comparing single-agent to debate consensus.
"""
import asyncio
import time
import logging
import difflib
from dataclasses import dataclass
from typing import Dict, Any, List

from dotenv import load_dotenv
load_dotenv()

# We only care about explicit errors
logging.basicConfig(level=logging.ERROR)
for _n in ["agents.debate", "llm.client"]:
    logging.getLogger(_n).setLevel(logging.ERROR)

PROFILES = [
    # Student
    ("student", "My experience_level is 'student'. CS student with Python, TensorFlow and 2 GitHub ML projects. Target: ml_engineer"),
    ("student", "My experience_level is 'student'. Grad student with NLP thesis and 3 deep-learning publications. Target: research_scientist"),
    
    # Junior
    ("junior", "My experience_level is 'junior'. Junior SWE with 1 year Python and scikit-learn. Target: ml_engineer"),
    ("junior", "My experience_level is 'junior'. Frontend developer with 1.5 yrs experience. Target: machine_learning_engineer"),

    # Mid
    ("mid", "My experience_level is 'mid'. Data engineer with 5 yrs ETL experience pivoting to machine_learning_engineer"),
]

def similar(a: str, b: str) -> bool:
    if not (a and b): return False
    # If one contains the other, that's broad agreement
    if a.lower() in b.lower() or b.lower() in a.lower(): return True
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() > 0.5

@dataclass
class ProfileResult:
    level: str
    single_agent_path: str = ""
    optimist_path: str = ""
    realist_path: str = ""
    consensus_path: str = ""
    confidence: float = 0.0
    num_risks: int = 0
    debate_lat: float = 0.0
    mentor_matched: bool = False

async def run_mad_benchmark():
    from src.app.graph import app
    results: List[ProfileResult] = []
    
    print(f"Running MAD Benchmark on {len(PROFILES)} profiles...")
    for i, (level, query) in enumerate(PROFILES):
        print(f" [{i+1}/{len(PROFILES)}] {level} / {query[:40]}... (processing)")
        res = ProfileResult(level=level)
        
        init = {"raw_user_input": query, "completed_agents": [], "errors": [], "feedback_loop_count": 0}
        
        t_debate_start = 0
        try:
            async for event in app.astream(init):
                for node, updates in event.items():
                    # Safely handle node updates
                    if not updates or not isinstance(updates, dict):
                        continue

                    if node == "career_reasoning":
                        # Capture single agent logic
                        cp = updates.get("career_paths")
                        # It might be a dict or a Pydantic object
                        if cp:
                            if hasattr(cp, "recommended_paths") and cp.recommended_paths:
                                res.single_agent_path = cp.recommended_paths[0].path_description
                            elif isinstance(cp, dict) and "recommended_paths" in cp and cp["recommended_paths"]:
                                res.single_agent_path = cp["recommended_paths"][0].get("path_description", "")
                        t_debate_start = time.time()
                    
                    elif node == "multi_agent_debate":
                        res.debate_lat = time.time() - t_debate_start
                        dr = updates.get("debate_result")
                        if dr and isinstance(dr, dict):
                            opt = dr.get("optimist_stance", {})
                            real = dr.get("realist_stance", {})
                            crit = dr.get("critic_stance", {})
                            verd = dr.get("final_verdict", {})
                            res.optimist_path = opt.get("recommended_path", "")
                            res.realist_path = real.get("recommended_path", "")
                            res.consensus_path = verd.get("consensus_path", "")
                            res.confidence = verd.get("confidence", 0.0)
                            res.num_risks = len(crit.get("risks", []))
                            
                    elif node == "mentor_discovery":
                        mr = updates.get("mentor_ranking")
                        if mr:
                            if hasattr(mr, "top_mentors") and len(mr.top_mentors) > 0:
                                res.mentor_matched = True
                            elif isinstance(mr, dict) and "top_mentors" in mr and len(mr["top_mentors"]) > 0:
                                res.mentor_matched = True
            
            results.append(res)
            print(f"done (conf: {res.confidence:.2f})")
            await asyncio.sleep(2) # rate limit bumper
            
        except Exception as e:
            print(f"ERROR: {e}")
            
    # Aggregation
    def calc_metrics(subset: List[ProfileResult]):
        n = len(subset)
        if n == 0: return (0, 0, 0, 0, 0, 0, 0, 0)
        
        opt_eq_real = sum(1 for r in subset if similar(r.optimist_path, r.realist_path))
        critic_flip = sum(1 for r in subset if not similar(r.consensus_path, r.optimist_path) and not similar(r.consensus_path, r.realist_path))
        diff_single = sum(1 for r in subset if not similar(r.consensus_path, r.single_agent_path))
        sum_conf = sum(r.confidence for r in subset)
        sum_risks = sum(r.num_risks for r in subset)
        sum_lat = sum(r.debate_lat for r in subset)
        mentors = sum(1 for r in subset if r.mentor_matched)
        
        return (
            n,
            (opt_eq_real / n) * 100,
            (critic_flip / n) * 100,
            (diff_single / n) * 100,
            sum_conf / n,
            sum_risks / n,
            sum_lat / n,
            (mentors / n) * 100
        )
        
    metrics = {
        "Student": calc_metrics([r for r in results if r.level == "student"]),
        "Junior": calc_metrics([r for r in results if r.level == "junior"]),
        "Mid": calc_metrics([r for r in results if r.level == "mid"]),
        "Overall": calc_metrics(results)
    }
    
    W = 120
    print(f"\n{'='*W}")
    print("  TABLE 3 — MULTI-AGENT DEBATE DYNAMICS")
    print(f"{'='*W}")
    
    cols = ["Metric", "Student", "Junior", "Mid", "Overall"]
    print(f"{cols[0]:<40} | {cols[1]:<12} | {cols[2]:<12} | {cols[3]:<12} | {cols[4]:<12}")
    print("-" * W)
    
    row_names = [
        "n profiles",
        "Optimist = Realist (pre-Critic)",
        "Critic flip rate (verdict changed)",
        "Consensus differs from single agent",
        "Mean confidence score",
        "Risk flags identified (mean per profile)",
        "Avg debate latency (s)",
        "Mentor match rate post-debate"
    ]
    
    formats = [
        "{0:d}", "{1:.0f}%", "{2:.0f}%", "{3:.0f}%", "{4:.2f}", "{5:.1f}", "{6:.1f}", "{7:.0f}%"
    ]
    
    groups = ["Student", "Junior", "Mid", "Overall"]
    for i in range(len(row_names)):
        vals = []
        for g in groups:
            m = metrics[g]
            val = m[i]
            vals.append(val)
            
        r_name = row_names[i]
        # format string
        fmts = []
        for j in range(4):
            if i == 0:
                s = str(vals[j])
            elif i in [1,2,3,7]:
                s = f"{vals[j]:.0f}%"
            elif i == 4:
                s = f"{vals[j]:.2f}"
            else:
                s = f"{vals[j]:.1f}"
            fmts.append(s)
            
        print(f"{r_name:<40} | {fmts[0]:<12} | {fmts[1]:<12} | {fmts[2]:<12} | {fmts[3]:<12}")
        

if __name__ == "__main__":
    asyncio.run(run_mad_benchmark())
