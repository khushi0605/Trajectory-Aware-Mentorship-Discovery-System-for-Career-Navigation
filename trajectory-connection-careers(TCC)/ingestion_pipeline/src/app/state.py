from typing import TypedDict, List, Optional
from src.retrieval.models import RetrievalContext
from src.agents.models import (
    UserProfile, CareerPathOptions, ExperienceInsights,
    MentorRanking, OutreachDraft, FeedbackSignal
)

class AgentState(TypedDict):
    """
    Shared state for the LangGraph workflow.
    LangGraph requires a TypedDict for state management.
    """
    # Input
    raw_user_input: str

    # Agent 1 output
    user_profile: Optional[UserProfile]

    # Agent 3 output (Retriever)
    retrieval_context: Optional[RetrievalContext]

    # Agent 2 output
    career_paths: Optional[CareerPathOptions]

    # Agent 4 output
    experience_insights: Optional[ExperienceInsights]

    # Agent 5 output
    mentor_ranking: Optional[MentorRanking]

    # Agent 6 output
    outreach_drafts: Optional[List[OutreachDraft]]

    # Agent 7 input/output
    feedback: Optional[FeedbackSignal]
    feedback_target_agent: Optional[str]   # which agent to re-run
    feedback_loop_count: int

    # Pipeline metadata
    errors: List[str]
    completed_agents: List[str]
