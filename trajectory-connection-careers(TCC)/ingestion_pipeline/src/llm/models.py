from pydantic import BaseModel
from typing import Optional

class LLMConfig(BaseModel):
    model: str
    api_key: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: int

class GroundingConfig(BaseModel):
    enforce_context_only: bool
    max_context_tokens: int

class FullLLMConfig(BaseModel):
    gemini: LLMConfig
    grounding: GroundingConfig
