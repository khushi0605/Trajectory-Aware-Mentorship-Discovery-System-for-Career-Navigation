import os
import json
import logging
import re
from typing import Dict, List, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

logger = logging.getLogger("experience_inferencer")

class ExperienceInferencer:
    """
    Extracts structured behavioral signals (learning patterns, decision points, struggles)
    from unstructured career narratives. Uses an LLM if available, otherwise falls back
    to a deterministic keyword-based heuristic extractor.
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.use_llm = bool(self.api_key and OpenAI)
        self.client = None
        
        if self.use_llm:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("ExperienceInferencer initialized with OpenAI LLM backend.")
            except Exception as e:
                logger.warning(f"Failed to init OpenAI client: {e}. Falling back to deterministic model.")
                self.use_llm = False
        else:
            logger.info("ExperienceInferencer initialized with Deterministic Fallback backend.")

    def infer_narratives(self, narratives: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Process multiple narratives and aggregate their signals into a unified profile block."""
        combined = {
            "learning_patterns": set(),
            "decision_points": [],
            "struggles": set()
        }
        
        for nav in narratives:
            text = nav.get("text", nav.get("summary", ""))
            if not text:
                continue
                
            if self.use_llm:
                extracted = self._infer_llm(text)
            else:
                extracted = self._infer_deterministic(text)
                
            combined["learning_patterns"].update(extracted.get("learning_patterns", []))
            combined["decision_points"].extend(extracted.get("decision_points", []))
            combined["struggles"].update(extracted.get("struggles", []))
            
        # Cap logic to keep profiles dense
        return {
            "learning_patterns": list(combined["learning_patterns"])[:5],
            "decision_points": combined["decision_points"][:3],
            "struggles": list(combined["struggles"])[:5]
        }

    def _infer_deterministic(self, text: str) -> Dict[str, Any]:
        """Mock deterministic extraction for users without OpenAI API Keys."""
        sentences = re.split(r'(?<=[.!?]) +', text.replace('\n', ' '))
        learning = []
        decisions = []
        struggles = []
        
        for s in sentences:
            sl = s.lower()
            if any(w in sl for w in ["learn", "study", "master", "course", "read"]):
                learning.append(s.strip())
            if any(w in sl for w in ["decid", "chose", "opt", "switch", "pivoted"]):
                decisions.append({
                    "type": "Career Choice",
                    "options": ["Status Quo", "New Path"],
                    "chosen": s.strip(),
                    "evidence": s.strip()
                })
            if any(w in sl for w in ["hard", "struggle", "difficult", "fail", "stuck", "bug"]):
                struggles.append(s.strip())
                
        return {
            "learning_patterns": learning,
            "decision_points": decisions,
            "struggles": struggles
        }

    def _infer_llm(self, text: str) -> Dict[str, Any]:
        """Real LLM extraction using GPT-4o-mini structured JSON schema matching."""
        prompt = f"""
        You are analyzing a career narrative. Extract learning patterns, decisions, and struggles.
        Return ONLY a JSON string mapping strictly to this schema:
        {{
            "learning_patterns": ["List of strings defining how the person learns"],
            "decision_points": [
                {{"type": "Choice type string", "options": ["Option A", "Option B"], "chosen": "The chosen option string", "evidence": "Direct quote or string"}}
            ],
            "struggles": ["List of strings defining career or technical difficulties"]
        }}
        
        Narrative: {text}
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                response_format={ "type": "json_object" },
                temperature=0.2
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"LLM inference failed, falling back to deterministic: {e}")
            return self._infer_deterministic(text)
