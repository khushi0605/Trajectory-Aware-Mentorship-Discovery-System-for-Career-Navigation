import json
import os
import re

def get_actionability(text):
    if not text or text == "[]": return 0
    score = 0
    # Steps: +2 per step found (max 6)
    steps = len(re.findall(r"(?:^|\s|\n)(\d[\.\)])", text))
    score += min(steps * 2, 6)
    
    # Timeline/Phases: +2
    if re.search(r"Phase\b|Timeline\b|Month\s\d|Next\s\d\smonths", text, re.I):
        score += 2
        
    # Metrics/KPIs: +2
    if re.search(r"%\b|KPI\b|metr|outcome|goal|target", text, re.I):
        score += 2
        
    return min(score, 10)

def get_risk_awareness(text):
    if not text or text == "[]": return 0
    score = 0
    # Unique categories: +2 each (max 6)
    categories = {
        "skills": ["skill", "python", "javascript", "tool", "competenc", "gap"],
        "market": ["market", "economic", "headwind", "competition", "saturation"],
        "credentials": ["cert", "degree", "education", "credential", "qualif"],
        "failure": ["risk", "fail", "barrier", "block", "obstacle", "issue"]
    }
    found_cats = 0
    for cat, keywords in categories.items():
        if any(k in text.lower() for k in keywords):
            found_cats += 1
    score += min(found_cats * 2, 6)

    # Mitigation logic: +2
    if re.search(r"mitigat|plan B|fallback|contingency|alternative", text, re.I):
        score += 2
        
    # Tone: +2 for alerting language
    if re.search(r"warning|caution|not yet|must|critical|alert", text, re.I):
        score += 2
        
    return min(score, 10)

cache_file = ".table4_cache/results_table4.json"
if not os.path.exists(cache_file):
    print(f"Error: {cache_file} not found.")
    exit(1)

with open(cache_file, "r") as f:
    results = json.load(f)

profiles = ["p1", "p3", "p5"]
methods = ["A", "B", "C", "D"]
method_names = {
    "A": "Single Agent",
    "B": "Majority Vote",
    "C": "Vanilla MAD",
    "D": "GG-MAD"
}

print("\n" + "="*50)
print("RAW RAW BENCHMARK SCORES (TABLE 4)")
print("="*50)

print("\n1. Actionability Scores (0 = Failed, 1 = Success)")
print(f"{'ProfileID':<10} | {'A':<3} | {'B':<3} | {'C':<3} | {'D':<3}")
print("-" * 30)
for pid in profiles:
    row = results.get(pid, {})
    scores = []
    for m in methods:
        text = row.get(m, {}).get("text", "")
        scores.append(str(get_actionability(text)))
    print(f"{pid:<10} | {' | '.join(scores)}")

print("\n2. Risk Awareness Scores (0 = Failed, 1 = Success)")
print(f"{'ProfileID':<10} | {'A':<3} | {'B':<3} | {'C':<3} | {'D':<3}")
print("-" * 30)
for pid in profiles:
    row = results.get(pid, {})
    scores = []
    for m in methods:
        text = row.get(m, {}).get("text", "")
        scores.append(str(get_risk_awareness(text)))
    print(f"{pid:<10} | {' | '.join(scores)}")

print("\nMethod Legends:")
print("A: Single Agent (Baseline)")
print("B: Majority Vote")
print("C: Vanilla MAD")
print("D: GG-MAD (Optimized adversarial synthesizer)")
