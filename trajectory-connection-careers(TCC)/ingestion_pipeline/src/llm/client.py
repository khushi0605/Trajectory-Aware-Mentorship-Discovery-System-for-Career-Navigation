import os
import asyncio
import logging
from typing import Optional, Any
from pydantic import BaseModel
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from src.core.exceptions import LLMParseError, LLMRateLimitError
from .models import FullLLMConfig
from .response_parser import ResponseParser

logger = logging.getLogger("llm.client")

class GeminiClient:
    def __init__(self, config: FullLLMConfig):
        """
        Initializes the Gemini client using the Generative AI SDK.
        """
        self.config = config.gemini
        genai.configure(api_key=self.config.api_key)
        self.model = genai.GenerativeModel(self.config.model)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Single async call to Gemini. Returns raw text response.
        """
        temp = temperature if temperature is not None else self.config.temperature
        max_t = max_tokens if max_tokens is not None else self.config.max_output_tokens
        
        # Configure generation
        generation_config = genai.types.GenerationConfig(
            temperature=temp,
            max_output_tokens=max_t,
        )

        try:
            # We use a combined prompt or chat history. 
            # SDK-specific: system_instruction is passed at model init or per call in some versions.
            # For this version of SDK, we often prepend to user prompt or use chat session.
            # Using model with system_instruction is preferred if supported.
            model = genai.GenerativeModel(
                model_name=self.config.model,
                system_instruction=system_prompt if system_prompt else None
            )
            
            # Use asyncio to make it non-blocking if needed, 
            # though the SDK's generate_content is synchronous by default.
            # We wrap it in a thread for real async behavior.
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: model.generate_content(
                    user_prompt,
                    generation_config=generation_config
                )
            )
            
            if not response.text:
                raise LLMParseError("Gemini returned an empty response")
                
            return response.text

        except google_exceptions.ResourceExhausted:
            logger.error("Gemini API rate limit exceeded.")
            raise LLMRateLimitError("Rate limit exceeded for Gemini API")
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        temperature: Optional[float] = None,
    ) -> BaseModel:
        """
        Calls Gemini, requests JSON, and validates against the provided Pydantic schema.
        Retries once on LLMParseError.
        """
        import json
        temp = temperature if temperature is not None else self.config.temperature
        
        # Inject schema into system prompt to ensure field naming alignment
        schema_dict = response_schema.model_json_schema()
        # Clean up the schema for the prompt
        if "$defs" in schema_dict: del schema_dict["$defs"] 
        schema_json = json.dumps(schema_dict, indent=2)
        
        full_system = f"{system_prompt}\n\nReturn ONLY a JSON object matching this schema:\n{schema_json}"

        # Update model for JSON response
        gen_config = {
            "response_mime_type": "application/json",
            "temperature": temp,
            "max_output_tokens": self.config.max_output_tokens
        }
        
        model = genai.GenerativeModel(
            model_name=self.config.model,
            system_instruction=full_system,
            generation_config=gen_config
        )

        async def _attempt():
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: model.generate_content(
                    user_prompt,
                    generation_config=gen_config # Redundant but safe
                )
            )
            
            if not response.text:
                raise LLMParseError("Gemini returned an empty response")
                
            logger.debug(f"Received LLM response (length: {len(response.text)})")
            return ResponseParser.validate_against(response.text, response_schema)

        try:
            return await _attempt()
        except LLMParseError as first_error:
            logger.warning(f"First LLM attempt failed: {first_error}. Retrying...")
            try:
                return await _attempt()
            except LLMParseError as second_error:
                logger.error(f"Second LLM attempt failed: {second_error}")
                raise second_error
