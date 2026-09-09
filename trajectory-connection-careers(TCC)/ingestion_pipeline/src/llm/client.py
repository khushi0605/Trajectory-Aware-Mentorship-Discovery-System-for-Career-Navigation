import os
import json
import asyncio
import logging
from typing import Optional, Any, Dict
from pydantic import BaseModel

from src.core.exceptions import LLMParseError, LLMRateLimitError
from src.llm.models import FullLLMConfig
from src.llm.response_parser import ResponseParser

logger = logging.getLogger("llm.client")

class UnifiedLLMClient:
    def __init__(self, config: FullLLMConfig):
        """
        Initializes the LLM client based on the provider (ollama, groq, or openai).
        """
        self.full_config = config
        self.provider = config.provider
        
        if self.provider == "ollama":
            from langchain_ollama import ChatOllama
            self.client = ChatOllama(
                model=config.ollama.model,
                base_url=config.ollama.base_url,
                temperature=config.ollama.temperature,
                timeout=config.ollama.timeout_seconds
            )
            self.config = config.ollama
        elif self.provider == "groq":
            from groq import AsyncGroq
            self.client = AsyncGroq(api_key=config.groq.api_key)
            self.config = config.groq
        elif self.provider == "openai":
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=config.openai.api_key,
                base_url=config.openai.base_url
            )
            self.config = config.openai
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def _get_extra_params(self, model_name: str) -> Dict[str, Any]:
        """
        Add model-specific parameters like reasoning_effort for GPT-OSS.
        """
        params = {}
        if "gpt-oss-120b" in model_name.lower():
            params["reasoning_effort"] = "medium"
        return params

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Single async call to the provider. Returns raw text response.
        """
        temp = temperature if temperature is not None else self.config.temperature
        max_t = max_tokens if max_tokens is not None else self.config.max_output_tokens
        
        extra_params = self._get_extra_params(self.config.model)
        
        if self.provider == "ollama":
            from langchain_core.messages import SystemMessage, HumanMessage
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            response = await self.client.ainvoke(messages)
            if not response or not response.content:
                raise LLMParseError(f"{self.provider.capitalize()} returned an empty response")
            return response.content

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use max_completion_tokens if using a reasoning model, otherwise max_tokens
                token_param = {"max_completion_tokens": max_t} if "gpt-oss" in self.config.model.lower() else {"max_tokens": max_t}

                response = await self.client.chat.completions.create(
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=temp,
                    **token_param,
                    **extra_params
                )
                
                if not response.choices or not response.choices[0].message.content:
                    raise LLMParseError(f"{self.provider.capitalize()} returned an empty response")
                    
                return response.choices[0].message.content

            except Exception as e:
                error_msg = str(e).lower()
                if "rate limit" in error_msg or "429" in error_msg or "413" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 60
                        logger.warning(f"{self.provider.upper()} API rate limit (TPM/RPM) exceeded. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise LLMRateLimitError(f"Rate limit exceeded for {self.provider.upper()} API after multiple retries")
                
                logger.error(f"{self.provider.upper()} API call failed: {e}")
                raise

    async def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        temperature: Optional[float] = None,
    ) -> BaseModel:
        """
        Calls the provider, requests JSON, and validates against the provided Pydantic schema.
        """
        temp = temperature if temperature is not None else self.config.temperature
        
        if self.provider == "ollama":
            from langchain_core.messages import SystemMessage, HumanMessage
            
            # Since qwen2.5-coder might struggle with strict json structured output via tool calling in ChatOllama natively,
            # we provide schema manually and use structured output if supported, or fallback to parsing.
            structured_llm = self.client.with_structured_output(response_schema)
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ]
            try:
                response = await structured_llm.ainvoke(messages)
                return response
            except Exception as e:
                logger.warning(f"Ollama structured output failed: {e}. Falling back to standard JSON parsing.")
                # Fallback to standard prompt-based parsing for Ollama
                schema_dict = response_schema.model_json_schema()
                if "$defs" in schema_dict: del schema_dict["$defs"] 
                schema_json = json.dumps(schema_dict, indent=2)
                full_system = f"{system_prompt}\n\nReturn ONLY a JSON object matching this schema:\n{schema_json}"
                raw_response = await self.generate(full_system, user_prompt, temperature=temp)
                return ResponseParser.validate_against(raw_response, response_schema)

        # Inject schema into system prompt for groq/openai
        schema_dict = response_schema.model_json_schema()
        if "$defs" in schema_dict: del schema_dict["$defs"] 
        schema_json = json.dumps(schema_dict, indent=2)
        
        full_system = f"{system_prompt}\n\nReturn ONLY a JSON object matching this schema:\n{schema_json}"
        extra_params = self._get_extra_params(self.config.model)

        async def _attempt_with_retry():
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    format_params = {}
                    # JSON mode is broadly supported
                    if self.provider == "groq" or "gpt" in self.config.model.lower():
                        format_params["response_format"] = {"type": "json_object"}

                    token_param = {"max_completion_tokens": self.config.max_output_tokens} if "gpt-oss" in self.config.model.lower() else {"max_tokens": self.config.max_output_tokens}

                    response = await self.client.chat.completions.create(
                        model=self.config.model,
                        messages=[
                            {"role": "system", "content": full_system},
                            {"role": "user", "content": user_prompt}
                        ],
                        temperature=temp,
                        **token_param,
                        **format_params,
                        **extra_params
                    )
                    
                    content = response.choices[0].message.content
                    if not content:
                        raise LLMParseError(f"{self.provider.capitalize()} returned an empty response")
                        
                    return ResponseParser.validate_against(content, response_schema)
                
                except Exception as e:
                    error_msg = str(e).lower()
                    if "rate limit" in error_msg or "429" in error_msg or "413" in error_msg:
                        if attempt < max_retries - 1:
                            wait_time = (attempt + 1) * 60
                            logger.warning(f"{self.provider.upper()} API rate limit (TPM/RPM) exceeded. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            raise LLMRateLimitError(f"Rate limit exceeded for {self.provider.upper()} API after multiple retries")
                    
                    if isinstance(e, LLMParseError) and attempt < max_retries - 1:
                        logger.warning(f"Parse error on attempt {attempt+1}. Retrying...")
                        continue
                    raise e

        try:
            return await _attempt_with_retry()
        except Exception as e:
            logger.error(f"Structured LLM attempt failed: {e}")
            raise e

