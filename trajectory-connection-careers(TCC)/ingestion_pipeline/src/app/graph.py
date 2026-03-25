import logging
from functools import partial
from langgraph.graph import StateGraph, START, END
from src.llm import GeminiClient, PromptBuilder, load_llm_config
from src.retrieval.rag_retriever import RAGRetriever
from src.retrieval.config.retriever_config import RetrieverConfig
from src.agents import (
    ProfileUnderstandingAgent,
    CareerReasoningAgent,
    ExperienceRetrievalAgent,
    ExperienceAnalysisAgent,
    MentorDiscoveryAgent,
    OutreachAgent,
    FeedbackAgent
)
from src.app.state import AgentState
from dotenv import load_dotenv

logger = logging.getLogger("app.graph")

def route_feedback(state: AgentState) -> str:
    """
    Conditional edge logic for human-in-the-loop feedback.
    Supports max 2 feedback loops.
    """
    signal = state.get("feedback")
    loop_count = state.get("feedback_loop_count", 0)
    
    if signal is None or signal.target_agent == "end" or loop_count >= 2:
        return END
    
    # Map target_agent slug to node name
    return signal.target_agent

def create_app():
    """
    Instantiates components and assembles the LangGraph.
    """
    load_dotenv()
    # 1. Initialize shared components
    llm_config = load_llm_config("configs/llm.yaml")
    llm_client = GeminiClient(llm_config)
    prompt_builder = PromptBuilder()
    
    # Fix: Use the config loader
    retriever_config = RetrieverConfig.load("configs/retrieval.yaml")
    retriever = RAGRetriever(retriever_config)

    # 2. Instantiate Agents
    agents = {
        "profile_understanding": ProfileUnderstandingAgent(llm_client, prompt_builder),
        "experience_retrieval": ExperienceRetrievalAgent(llm_client, prompt_builder, retriever),
        "career_reasoning": CareerReasoningAgent(llm_client, prompt_builder),
        "experience_analysis": ExperienceAnalysisAgent(llm_client, prompt_builder),
        "mentor_discovery": MentorDiscoveryAgent(llm_client, prompt_builder),
        "outreach": OutreachAgent(llm_client, prompt_builder),
        "feedback": FeedbackAgent(llm_client, prompt_builder),
    }

    # 3. Create StateGraph
    workflow = StateGraph(AgentState)

    # 4. Add Nodes
    # Using functools.partial to wrap agent.run into a plain async callable as per spec
    for name, agent in agents.items():
        workflow.add_node(name, agent.run)

    # 5. Define Edges (Strict Execution Order)
    # 1 (Profile) -> 3 (Retrieval) -> 2 (Reasoning) -> 4 (Analysis) -> 5 (Mentors) -> 6 (Outreach) -> 7 (Feedback)
    workflow.add_edge(START, "profile_understanding")
    workflow.add_edge("profile_understanding", "experience_retrieval")
    workflow.add_edge("experience_retrieval", "career_reasoning")
    workflow.add_edge("career_reasoning", "experience_analysis")
    workflow.add_edge("experience_analysis", "mentor_discovery")
    workflow.add_edge("mentor_discovery", "outreach")
    workflow.add_edge("outreach", "feedback")

    # 6. Add Conditional Edges from Feedback node
    workflow.add_conditional_edges(
        "feedback",
        route_feedback,
        {
            "career_reasoning": "career_reasoning",
            "experience_analysis": "experience_analysis",
            "mentor_discovery": "mentor_discovery",
            "outreach": "outreach",
            END: END
        }
    )

    # 7. Compile
    return workflow.compile()

# Singleton-like access if needed, but create_app() is better for tests
app = create_app()
