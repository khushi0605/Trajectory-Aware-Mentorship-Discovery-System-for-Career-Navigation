from pydantic import BaseModel, Field
from typing import List, Optional, Literal

class UserProfile(BaseModel):
    background: str = Field(description="Current educational or professional background")
    skills: List[str] = Field(default_factory=list, description="Explicitly mentioned skills")
    interest: str = Field(description="Core domain or technology area of interest")
    goal: str = Field(description="Target role or career outcome")
    confusion: Optional[str] = Field(None, description="Any expressed uncertainty or conflict in career choice")
    experience_level: Literal["student", "junior", "mid", "senior"] = Field(description="Current seniority level")

class CareerPath(BaseModel):
    path_description: str = Field(description="Structured sequence of roles (e.g. A -> B -> C)")
    supporting_candidate_ids: List[str] = Field(default_factory=list, description="IDs of candidates following this path")
    avg_reachability: float = Field(description="Aggregated reachability score from graph data")
    key_decision: str = Field(description="The pivotal decision that triggered the target transition")
    estimated_hops: int = Field(description="Number of role transitions to reach goal")

class CareerPathOptions(BaseModel):
    recommended_paths: List[CareerPath] = Field(default_factory=list, description="Top 3 career trajectories from data")
    reasoning: str = Field(default="", description="Analytical explanation of why these paths were surfaced")
    data_gaps: List[str] = Field(default_factory=list, description="Information missing from the graph for this query")
    data_sufficient: bool = Field(default=False, description="Whether enough data was found to make recommendations")

class ExperienceInsight(BaseModel):
    theme: str = Field(default="", description="Core challenge or learning theme identified")
    frequency: int = Field(default=0, description="Number of candidates exhibiting this pattern")
    resolution_pattern: str = Field(default="", description="Grounded summary of how the challenge was resolved")
    supporting_evidence: List[str] = Field(default_factory=list, description="Direct quotes or candidate_ids as evidence")

class ExperienceInsights(BaseModel):
    common_struggles: List[ExperienceInsight] = Field(default_factory=list, description="Synthesized blockers encountered by peers")
    common_learning_paths: List[ExperienceInsight] = Field(default_factory=list, description="Synthesized successful learning strategies")
    key_skills_to_acquire: List[str] = Field(default_factory=list, description="Specific skills mentioned as critical for transition")
    estimated_transition_time: str = Field(default="unknown", description="Timeframe estimate grounded in evidence")

class MentorMatch(BaseModel):
    candidate_id: str = Field(description="ID of the potential mentor")
    reachability_score: float = Field(default=0.0, description="How attainable this mentor is for the user")
    skill_overlap: List[str] = Field(default_factory=list, description="Intersection of user skills and mentor's prior skills")
    path_taken: str = Field(default="", description="The mentor's specific trajectory string")
    why_relevant: str = Field(default="", description="Personalized rationale for the match")
    contact_hook: str = Field(default="", description="Specific signal to use in outreach message")

class MentorRanking(BaseModel):
    top_mentors: List[MentorMatch] = Field(default_factory=list, description="Top 3 ranked mentors")
    ranking_rationale: str = Field(default="", description="High-level reasoning for the overall ranking")

class OutreachDraft(BaseModel):
    mentor_candidate_id: str = Field(description="Target mentor's ID")
    subject_line: str = Field(default="", description="Personalized subject line")
    message_body: str = Field(default="", description="Custom connection request message")
    personalisation_hooks: List[str] = Field(default_factory=list, description="Data points used to customize the message")

class FeedbackSignal(BaseModel):
    raw_feedback: str = Field(description="Original user feedback string")
    target_agent: Literal["career_reasoning", "experience_analysis", "mentor_discovery", "outreach", "end"] = Field(default="end", description="Agent identified for refinement")
    refinement_instruction: str = Field(default="", description="Specific instruction for the re-run")
