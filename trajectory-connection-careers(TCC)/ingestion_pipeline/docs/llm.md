# LLM Integration Architecture
## `src/llm/` — Phase 3 foundation

---

## Purpose

The LLM layer is the reasoning engine that sits between the retrieval layer and
the agent graph. It receives a `RetrievalContext` + a structured user query,
and produces grounded natural language responses and structured outputs.

This is a **thin wrapper** — not a framework. Its job is to format prompts,
call the Gemini API, parse responses, and enforce the grounding constraint:
the model must reason over retrieved data, not generate from training memory.

---

## Model Choice: Gemini 2.5 Flash (free tier)

- **API:** Google Generative AI (`google-generativeai` Python SDK)
- **Model string:** `gemini-2.5-flash-preview-04-17`  
  *(verify current free-tier model string at https://ai.google.dev/gemini-api/docs/models)*
- **Why this model for this system:** Fast enough for multi-agent chains,
  free tier sufficient for dev/research, structured JSON output supported
  natively via `response_mime_type: "application/json"`

---

## File Structure (new package — separate from ingestion)

```
src/
  llm/
    __init__.py                  ← exports GeminiClient, PromptBuilder
    client.py                    ← GeminiClient wrapping google-generativeai
    prompt_builder.py            ← builds system + user prompts per agent
    response_parser.py           ← parses/validates LLM JSON outputs
    models.py                    ← Pydantic types for LLM inputs/outputs
```

Config: `configs/llm.yaml` (new file)

---

## Class Design

### `GeminiClient`

Single point of contact for all LLM calls across all agents. Every agent
gets one injected instance — they never instantiate their own.

```python
# src/llm/client.py
class GeminiClient:
    def __init__(self, config: LLMConfig): ...

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel] | None = None,
        temperature: float = 0.3,
    ) -> str | dict:
        """
        Single async call to Gemini.
        If response_schema is provided, requests JSON and validates
        the response against the schema before returning.
        """
        ...

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
    ) -> BaseModel:
        """
        Convenience wrapper — always returns a validated Pydantic model.
        Raises LLMParseError if response doesn't match schema.
        """
        ...
```

### `PromptBuilder`

Builds the exact prompt pair (system + user) for each agent. Each agent
has its own builder method. Prompts are assembled here, not inside agent files.

```python
# src/llm/prompt_builder.py
class PromptBuilder:

    def for_profile_understanding(self, raw_input: str) -> tuple[str, str]: ...
    def for_career_reasoning(self, context: RetrievalContext, profile: UserProfile) -> tuple[str, str]: ...
    def for_experience_analysis(self, context: RetrievalContext, paths: list) -> tuple[str, str]: ...
    def for_mentor_discovery(self, context: RetrievalContext, profile: UserProfile) -> tuple[str, str]: ...
    def for_outreach(self, mentor: MentorMatch, user: UserProfile, experiences: list) -> tuple[str, str]: ...
    def for_feedback_integration(self, feedback: str, previous_output: dict) -> tuple[str, str]: ...
```

### `ResponseParser`

Handles the cases where Gemini returns malformed JSON, adds markdown fences,
or truncates. One place to fix parsing — not scattered across agents.

```python
# src/llm/response_parser.py
class ResponseParser:
    @staticmethod
    def parse_json(raw: str) -> dict: ...

    @staticmethod
    def validate_against(raw: str, schema: type[BaseModel]) -> BaseModel: ...
```

---

## The Grounding Constraint (critical for paper)

Every system prompt follows this template pattern. This is non-negotiable —
it is what separates your system from generic LLM career advice.

```
You are a career reasoning engine. You reason ONLY over the data provided
in the context block below. You do not generate career advice from your
training data. If the context does not contain enough information to answer,
say so explicitly.

You will be penalised for:
- Suggesting career paths not present in the context
- Inventing experiences or stories
- Recommending people not in the candidate list

Context:
{retrieval_context_formatted}
```

This framing is your paper's empirical claim made executable.

---

## Prompt Templates Per Agent

| Agent | Prompt style | Output format |
|---|---|---|
| Profile Understanding | Extraction — parse user free text into structured fields | JSON (`UserProfile`) |
| Career Reasoning | Analytical — reason over trajectory paths, list options | JSON (`CareerPathOptions`) |
| Experience Analysis | Synthesis — summarise behavioral signals into insights | JSON (`ExperienceInsights`) |
| Mentor Discovery | Ranking — score and rank candidates by reachability + match | JSON (`MentorRanking`) |
| Outreach | Generative — write personalised message using mentor's specific experiences | Plain text |
| Feedback Integration | Reflective — adjust previous outputs based on user correction | JSON (same schema as target agent) |

---

## LLM Config (`configs/llm.yaml`)

```yaml
gemini:
  model: "gemini-2.5-flash-preview-04-17"
  api_key: "${GEMINI_API_KEY}"
  temperature: 0.3
  max_output_tokens: 2048
  timeout_seconds: 30

grounding:
  enforce_context_only: true
  max_context_tokens: 6000   # stay within free-tier context window safely
```

---

## How Agents Use the LLM Layer

Agents never import `google-generativeai` directly. The pattern is always:

```python
# inside any agent node function
prompt_builder = PromptBuilder()
system, user = prompt_builder.for_career_reasoning(context, profile)
result = await llm_client.generate_structured(system, user, CareerPathOptions)
```

The `GeminiClient` and `PromptBuilder` instances are created once in the
graph entrypoint (`src/app/graph.py`) and injected into each agent node
via LangGraph's state or node config — not instantiated per-call.

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| API rate limit (free tier) | Exponential backoff, max 3 retries, then `LLMRateLimitError` |
| Malformed JSON response | `ResponseParser` strips fences, retries once, then `LLMParseError` |
| Response fails schema validation | Logs raw response, raises `LLMParseError` with schema diff |
| Context exceeds token limit | `PromptBuilder` truncates `narrative_chunks` first, then `behavioral_signals` |
| Network timeout | `asyncio.wait_for` with `timeout_seconds` from config |

---

## New dependencies to add to `requirements.txt`

```
google-generativeai>=0.8.0
langgraph>=0.2.0
langchain-google-genai>=1.0.0
```
