import json
import re
import logging
from pydantic import BaseModel, ValidationError
from src.core.exceptions import LLMParseError

logger = logging.getLogger("llm.response_parser")

class ResponseParser:
    @staticmethod
    def parse_json(raw: str) -> dict:
        """
        Cleans and parses a JSON string from LLM output.
        Handles markdown fences and stripping whitespace.
        """
        if not raw:
            raise LLMParseError("Received empty response from LLM")

        # Strip markdown fences if present
        cleaned = re.sub(r'^```json\s*|\s*```$', '', raw.strip(), flags=re.MULTILINE)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Check for truncation (common if max_tokens is low or output is long)
            logger.error(f"Malformed JSON (first 500 chars): {cleaned[:500]}")
            if cleaned.count('{') > cleaned.count('}'):
                logger.error(f"Detected truncated JSON: {cleaned}")
                raise LLMParseError(f"LLM output appears truncated: {e}")
            
            raise LLMParseError(f"Malformed JSON in LLM response: {e}")

    @staticmethod
    def validate_against(raw: str, schema: type[BaseModel]) -> BaseModel:
        """
        Parses JSON and validates it against a Pydantic schema.
        """
        data = ResponseParser.parse_json(raw)
        try:
            return schema(**data)
        except ValidationError as e:
            logger.error(f"Schema validation failed for {schema.__name__}: {e}")
            raise LLMParseError(f"LLM output does not match schema {schema.__name__}: {e}")
