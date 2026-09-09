import logging
import json
from typing import Dict, Any
from src.app.graph import app
from src.app.state import AgentState

logger = logging.getLogger("app.runner")

def print_agent_delta(state: AgentState):
    """
    Prints only the most recently completed agent's output.
    """
    if not state.get("completed_agents"):
        return
        
    last_agent = state["completed_agents"][-1]
    print(f"\n--- [AGENT: {last_agent.upper()} COMPLETED] ---")
    
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
    
    key = mapping.get(last_agent)
    if key and state.get(key):
        val = state[key]
        if last_agent == "multi_agent_debate":
            from src.agents.multi_agent_debate import format_debate_summary
            print(format_debate_summary(val))
        elif hasattr(val, "model_dump_json"):
            print(val.model_dump_json(indent=2))
        elif isinstance(val, list):
            # For outreach_drafts
            print(json.dumps([d.model_dump() if hasattr(d, "model_dump") else d for d in val], indent=2))
        else:
            print(val)
    elif last_agent == "experience_retrieval":
        ctx = state.get("retrieval_context")
        if ctx:
            print(f"Neo4j Paths Found: {len(ctx.trajectory_paths)}")
            print(f"Behavioral Signals: {len(ctx.behavioral_signals)}")
            print(f"Narrative Chunks: {len(ctx.narrative_chunks)}")

async def run_pipeline(raw_user_input: str) -> AgentState:
    """
    Initializes state and runs the compiled LangGraph.
    Exposes streaming output for each agent completion via stdout.
    """
    initial_state = {
        "raw_user_input": raw_user_input,
        "completed_agents": [],
        "errors": [],
        "feedback_loop_count": 0
    }
    
    print(f"🔮 Starting Pipeline for input: \"{raw_user_input}\"")
    
    final_state = initial_state
    
    async for event in app.astream(initial_state):
        if not event:
            continue
            
        for node_name, updates in event.items():
            if not updates or not isinstance(updates, dict):
                continue
            for k, v in updates.items():
                final_state[k] = v
            print_agent_delta(final_state)
            
    return final_state

async def run_pipeline_stream(raw_user_input: str):
    """
    Async generator that yields each LangGraph node's output.
    Used by Streamlit for UI observability.
    """
    initial_state = {
        "raw_user_input": raw_user_input,
        "completed_agents": [],
        "errors": [],
        "feedback_loop_count": 0
    }
    
    async for event in app.astream(initial_state):
        if not event:
            continue
        yield event

