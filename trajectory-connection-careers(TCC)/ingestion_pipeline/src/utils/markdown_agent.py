import json
import os

class MarkdownGeneratorAgent:
    """Converts the final structured TCC pipeline state into a Markdown report."""
    
    @staticmethod
    def generate_report(profile_id: str, state: dict, output_dir: str = "outputs/tcc_results/"):
        os.makedirs(output_dir, exist_ok=True)
        
        profile = state.get("user_profile", {})
        # If user_profile is a Pydantic object, convert it
        if hasattr(profile, "model_dump"):
            profile = profile.model_dump()
        elif hasattr(profile, "dict"):
            profile = profile.dict()
            
        debate = state.get("debate_result", {}).get("final_verdict", {}) if isinstance(state.get("debate_result"), dict) else {}
        critic = state.get("debate_result", {}).get("critic_stance", {}) if isinstance(state.get("debate_result"), dict) else {}
        
        insights = state.get("experience_insights", {})
        if hasattr(insights, "model_dump"):
            insights = insights.model_dump()
        elif hasattr(insights, "dict"):
            insights = insights.dict()
            
        mentor_ranking = state.get("mentor_ranking", {})
        if hasattr(mentor_ranking, "model_dump"):
            mentor_ranking = mentor_ranking.model_dump()
        elif hasattr(mentor_ranking, "dict"):
            mentor_ranking = mentor_ranking.dict()
            
        mentors = mentor_ranking.get("top_mentors", [])

        md = f"# GG-MAD Trajectory Report: {profile_id}\n\n"
        md += f"**Background:** {profile.get('background', 'N/A')}\n"
        md += f"**Goal:** {profile.get('goal', 'N/A')}\n\n"
        
        md += "## 1. Multi-Agent Debate Consensus\n"
        md += f"**Recommended Path:** {debate.get('consensus_path', 'N/A')}\n"
        md += f"**Confidence:** {debate.get('confidence', 0.0) * 100}%\n"
        md += f"**Reasoning:** {debate.get('reasoning', 'N/A')}\n\n"
        
        md += "## 2. Critic Feasibility Flags\n"
        for risk in critic.get("risks", []):
            md += f"- ⚠ {risk}\n"
            
        md += "\n## 3. Experience Analysis (Neo4j Grounding)\n"
        md += f"**Key Skills to Acquire:** {', '.join(insights.get('key_skills_to_acquire', []))}\n"
        for struggle in insights.get("common_struggles", []):
            md += f"- **Common Hurdle:** {struggle.get('theme')} (Frequency: {struggle.get('frequency')})\n"

        md += "\n## 4. Mentor Discovery\n"
        for m in mentors:
            md += f"- **{m.get('candidate_id')}** (Reachability: {m.get('reachability_score')})\n"
            md += f"  - *Path Taken:* {m.get('path_taken')}\n"
            md += f"  - *Relevance:* {m.get('why_relevant')}\n"

        file_path = os.path.join(output_dir, f"{profile_id}_report.md")
        with open(file_path, "w") as f:
            f.write(md)
            
        return md, file_path
