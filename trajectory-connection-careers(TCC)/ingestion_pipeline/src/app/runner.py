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
        "experience_analysis": "experience_insights",
        "mentor_discovery": "mentor_ranking",
        "outreach": "outreach_drafts",
        "feedback": "feedback"
    }
    
    key = mapping.get(last_agent)
    if key and state.get(key):
        val = state[key]
        if hasattr(val, "model_dump_json"):
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
    Exposes streaming output for each agent completion.
    """
    initial_state = {
        "raw_user_input": raw_user_input,
        "completed_agents": [],
        "errors": [],
        "feedback_loop_count": 0
    }
    
    print(f"🔮 Starting Pipeline for input: \"{raw_user_input}\"")
    
    final_state = initial_state
    
    # We use astream to track progress if we want, or just ainvoke.
    # To satisfy the "pretty-print as it completes" requirement, 
    # we can use astream or just wrap the graph invocation.
    
    async for event in app.astream(initial_state):
        if not event:
            continue
            
        # LangGraph events often look like {node_name: {updates}}
        for node_name, updates in event.items():
            if not updates or not isinstance(updates, dict):
                continue
            # Apply updates manually if we want to print delta *after* current agent
            # However, AgentState in state.py is just a dict, so we can check it.
            # Actually, LangGraph merges them into the state passed to the loop.
            # The 'event' itself is the delta from the node.
            
            # Since we want to print the *result* of the node that just ran:
            # We'll update a local tracker
            for k, v in updates.items():
                final_state[k] = v
            
            # Now we can print based on the completed_agents list update
            print_agent_delta(final_state)
            
    return final_state
