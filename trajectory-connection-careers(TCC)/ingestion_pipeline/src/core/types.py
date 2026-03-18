from datetime import datetime
from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class SourceType(str, Enum):
    GITHUB = "github"
    KAGGLE = "kaggle"
    BLOG = "blog"

class CareerSignal(BaseModel):
    source: SourceType
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data: Dict[str, Any]

class Trajectory(CareerSignal):
    """Structured path data (Roles, Skills)."""
    username: str
    roles: List[Dict[str, Any]] = []
    skills: List[str] = []

class Experience(CareerSignal):
    """Narrative/Unstructured data (Blogs, Articles)."""
    title: str
    url: str
    content: str

class Profile(CareerSignal):
    """General profile model for users (GitHub, Kaggle, etc.)."""
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    links: List[str] = []
    metadata: Dict[str, Any] = {}

class Skill(BaseModel):
    name: str
    category: Optional[str] = None
    level: Optional[str] = None
