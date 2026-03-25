import os
import yaml
import logging
import google.generativeai as genai
from typing import Dict, Any, Optional

logger = logging.getLogger("llm_layer")

class GeminiClient:
    def __init__(self, config_path: str = "configs/llm.yaml"):
        """
        Initializes the Gemini client with configuration and API key.
        """
        try:
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load LLM config from {config_path}: {e}")
            raise

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set.")

        genai.configure(api_key=api_key)
        
        self.model_name = self.config.get("model_name", "gemini-1.5-flash")
        self.temperature = self.config.get("temperature", 0.2)
        self.max_tokens = self.config.get("max_tokens", 1024)
        
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config={
                "temperature": self.temperature,
                "max_output_tokens": self.max_tokens,
                "response_mime_type": "application/json",
            }
        )

    def generate_json(self, prompt: str) -> str:
        """
        Calls Gemini model and enforces structured JSON output.
        Returns ONLY the raw JSON string.
        """
        try:
            response = self.model.generate_content(prompt)
            if not response.text:
                logger.warning("Gemini returned an empty response.")
                return "{}"
            return response.text
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
