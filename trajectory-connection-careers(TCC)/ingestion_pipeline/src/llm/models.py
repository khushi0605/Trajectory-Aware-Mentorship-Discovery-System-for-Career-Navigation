from pydantic import BaseModel
from typing import Optional

class LLMConfig(BaseModel):
    model: str
    api_key: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: int
    base_url: Optional[str] = None

class GroundingConfig(BaseModel):
    enforce_context_only: bool
    max_context_tokens: int

class FullLLMConfig(BaseModel):
    provider: str = "ollama"
    ollama: Optional[LLMConfig] = None
    groq: Optional[LLMConfig] = None
    openai: Optional[LLMConfig] = None
    grounding: GroundingConfig
