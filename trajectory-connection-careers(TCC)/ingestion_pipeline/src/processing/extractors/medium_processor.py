import argparse
import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple

import pandas as pd
from dotenv import load_dotenv

# Optional LLM imports
try:
    import google.generativeai as genai
    from pydantic import BaseModel, Field
    HAS_LLM_DEPS = True
except ImportError:
    HAS_LLM_DEPS = False

# ---------------------------------------------------------------------------
# Logging Setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/medium_processor.log", mode="a"),
    ],
)
logger = logging.getLogger("medium_processor")
Path("logs").mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# LLM Schema Definition (Only evaluated if LLM deps are present)
# ---------------------------------------------------------------------------
if HAS_LLM_DEPS:
    class Signals(BaseModel):
        learning_velocity: float = Field(description="Score between 0.0 and 1.0 mapping learning velocity.")
        project_depth: float = Field(description="Score between 0.0 and 1.0 indicating depth of the technical project/concept.")
        practical_exposure: float = Field(description="Score between 0.0 and 1.0 indicating hands-on practical focus.")
        leadership: float = Field(description="Score between 0.0 and 1.0 indicating leadership, mentoring, or strategic direction.")

    class ExperienceInsight(BaseModel):
        what_you_learn: str = Field(description="Explanation of the concept in simple terms (e.g., 'how neural networks process data').")
        how_you_learn: str = Field(description="The learning format (e.g., 'step-by-step guided implementation').")
        difficulty: str = Field(description="One of: beginner, intermediate, advanced.")
        time_estimate: str = Field(description="Estimated time (e.g., '1-3 hours').")
        real_world_relevance: str = Field(description="Real-world application of the skill.")
        confidence_signal: str = Field(description="Reassuring metadata (e.g., 'a foundational concept for NLP').")
        experience_outcome: str = Field(description="Capability obtained (e.g., 'ability to implement word embeddings').")

    class StructuredFeatures(BaseModel):
        summary: str = Field(description="1-2 line summary of the technical narrative.")
        themes: List[str] = Field(
            description="List of themes chosen from: machine_learning, backend, frontend, data_science, devops, system_design, career_growth, internships, research."
        )
        skills: Dict[str, float] = Field(description="Dictionary of extracted technical skills mapping to their relevance weights (0.0 to 1.0).")
        career_stage: str = Field(description="One of: beginner, intermediate, advanced.")
        experience_type: str = Field(description="One of: project, tutorial, career_story, internship, research, opinion.")
        signals: Signals
        semantic_tags: List[str] = Field(description="5-10 short, action-based, retrieval-friendly phrases capturing the essence.")
        experience_insight: ExperienceInsight
        confidence_score: float = Field(description="Confidence from 0 to 1.0.")

# ---------------------------------------------------------------------------
# Advanced Deterministic Rules Engine for Compressed Signals
# ---------------------------------------------------------------------------

# Phrase Skills mapping string -> list of skills (specific to general)
PHRASE_SKILLS = {
    "word2vec": ["word2vec", "nlp", "machine_learning"],
    "gensim": ["gensim", "nlp", "machine_learning"],
    "embedding": ["embeddings", "nlp", "machine_learning"],
    "graph neural network": ["graph_neural_networks", "deep_learning", "machine_learning"],
    "gradient descent": ["gradient_descent", "machine_learning"],
    "backpropagation": ["backpropagation", "deep_learning", "machine_learning"],
    "recommender system": ["recommender_systems", "machine_learning"],
    "hypothesis testing": ["hypothesis_testing", "statistics", "data_science"],
    "latent matrix factorization": ["matrix_factorization", "machine_learning"],
    "natural language processing": ["nlp", "machine_learning"],
    "computer vision": ["computer_vision", "machine_learning"],
    "reinforcement learning": ["reinforcement_learning", "machine_learning"],
    "time series": ["time_series_analysis", "data_science", "machine_learning"],
    "data pipeline": ["data_engineering", "backend"],
    "object detection": ["object_detection", "computer_vision", "deep_learning"],
    "sentiment analysis": ["sentiment_analysis", "nlp", "machine_learning"],
    "neural network": ["neural_networks", "deep_learning", "machine_learning"],
    "logistic regression": ["logistic_regression", "machine_learning", "statistics"],
    "random forest": ["random_forest", "machine_learning"],
    "decision tree": ["decision_trees", "machine_learning"],
    "support vector machine": ["svm", "machine_learning"],
    "continuous integration": ["ci_cd", "devops"],
    "continuous deployment": ["ci_cd", "devops"],
    "rest api": ["rest_api", "backend", "system_design"],
    "graphql api": ["graphql", "backend", "system_design"],
    "microservices architecture": ["microservices", "system_design", "backend"],
}

SINGLE_WORD_SKILLS = {
    "python": ["python"], "java": ["java"], "javascript": ["javascript", "frontend"], 
    "typescript": ["typescript", "frontend"], "ruby": ["ruby"], "go": ["go", "backend"], 
    "golang": ["go", "backend"], "rust": ["rust", "backend"], "c++": ["cpp"], "c#": ["csharp"],
    "ml": ["machine_learning"], "ai": ["machine_learning"], "dl": ["deep_learning", "machine_learning"],
    "pytorch": ["pytorch", "deep_learning", "machine_learning"], 
    "tensorflow": ["tensorflow", "deep_learning", "machine_learning"], 
    "keras": ["keras", "deep_learning", "machine_learning"], 
    "pandas": ["pandas", "data_science", "python"],
    "numpy": ["numpy", "data_science", "python"], 
    "scipy": ["scipy", "data_science", "python"], 
    "scikit-learn": ["scikit_learn", "machine_learning", "python"], 
    "sklearn": ["scikit_learn", "machine_learning", "python"],
    "nlp": ["nlp", "machine_learning"], "cv": ["computer_vision", "machine_learning"], 
    "sql": ["sql", "data_engineering", "backend"], 
    "react": ["react", "frontend", "javascript"], "angular": ["angular", "frontend", "javascript"],
    "vue": ["vue", "frontend", "javascript"], "node": ["node", "backend", "javascript"], 
    "aws": ["aws", "cloud", "devops"], "azure": ["azure", "cloud", "devops"], 
    "gcp": ["gcp", "cloud", "devops"], "docker": ["docker", "devops"], 
    "kubernetes": ["kubernetes", "devops"], "k8s": ["kubernetes", "devops"],
    "git": ["git", "devops"], "hadoop": ["hadoop", "data_engineering"], 
    "spark": ["spark", "data_engineering"], "kafka": ["kafka", "data_engineering", "backend"], 
    "statistics": ["statistics", "data_science"], "ggplot2": ["ggplot2", "data_visualization", "r"],
    "databricks": ["databricks", "data_engineering", "cloud"]
}

THEME_MAP = {
    "machine_learning": ["ml", "machine learning", "deep learning", "ai", "artificial intelligence", "pytorch", "tensorflow", "neural", "gradient descent", "model", "predict"],
    "backend": ["api", "database", "server", "microservices", "sql", "node", "django", "flask", "spring", "backend"],
    "frontend": ["ui", "ux", "react", "angular", "vue", "css", "html", "browser", "frontend", "web app"],
    "data_science": ["data", "analytics", "visualization", "pandas", "numpy", "matplotlib", "statistics", "chart", "plot"],
    "devops": ["docker", "kubernetes", "aws", "cloud", "deploy", "ci/cd", "pipeline", "infrastructure", "devops"],
    "system_design": ["architecture", "scale", "system design", "distributed", "performance", "high availability"],
    "career_growth": ["interview", "resume", "journey", "career", "salary", "hiring", "job", "developer"],
    "internships": ["intern", "internship", "student", "grad", "university"],
    "research": ["paper", "research", "published", "study", "analysis", "experiments"],
}

SKILL_TO_THEME = {
    "machine_learning": "machine_learning",
    "deep_learning": "machine_learning",
    "nlp": "machine_learning",
    "computer_vision": "machine_learning",
    "data_science": "data_science",
    "statistics": "data_science",
    "data_visualization": "data_science",
    "data_engineering": "backend",
    "python": "backend",
    "java": "backend",
    "sql": "backend",
    "node": "backend",
    "backend": "backend",
    "frontend": "frontend",
    "javascript": "frontend",
    "typescript": "frontend",
    "react": "frontend",
    "vue": "frontend",
    "angular": "frontend",
    "aws": "devops",
    "gcp": "devops",
    "azure": "devops",
    "docker": "devops",
    "kubernetes": "devops",
    "ci_cd": "devops",
    "system_design": "system_design",
}

WHAT_YOU_LEARN_MAP = {
    "word2vec": "how words are converted into numerical vectors",
    "gensim": "how to build topic models and handle text processing",
    "embeddings": "how to represent sparse data dynamically as dense vectors",
    "gradient_descent": "how models optimize using iterative parameter updates",
    "computer_vision": "how algorithms process and analyze image data",
    "nlp": "how machines interpret and process text data",
    "deep_learning": "how deep architectures build hierarchical representations",
    "machine_learning": "how models identify patterns from data",
    "react": "how to build reactive user interfaces with components",
    "sql": "how to query and manipulate relational databases",
    "docker": "how to containerize applications for consistent deployment",
    "kubernetes": "how to orchestrate container deployments at scale",
    "microservices": "how to design decoupled distributed systems",
    "rest_api": "how to implement standard stateless communication protocols",
    "data_science": "how to analyze datasets and extract actionable insights",
    "pandas": "how to manipulate and analyze structured tabular data",
    "pytorch": "how to build and train dynamic neural networks",
    "tensorflow": "how to build and train scalable ML models",
    "system_design": "how to architect and scale large technical systems",
    "ci_cd": "how to automate testing and deployment pipelines"
}

# New System-Level Real World Relevance Mappings
REAL_WORLD_MAP = {
    "word2vec": "used in NLP systems like search engines, recommendation systems, and chatbots",
    "nlp": "used in search engines, voice assistants, and enterprise customer service bots",
    "deep_learning": "used in large-scale generative AI and highly complex predictive software",
    "computer_vision": "used in autonomous vehicles, medical imaging, and visual inspection systems",
    "sql": "used in backend systems and data pipelines for querying structured data",
    "react": "used to power user experiences in major high-traffic web applications globally",
    "docker": "used in CI/CD environments to package applications consistently across infrastructure",
    "kubernetes": "used by large enterprises to manage highly available container clusters",
    "microservices": "used by growing organizations to decouple logic and scale independent teams",
    "data_science": "used by analysts to drive strategic product and business intelligence operations",
    "pytorch": "used for building and training deep learning models in production",
    "machine_learning": "used across industries to power automation, optimization, and predictive features",
    "system_design": "used to guarantee massive traffic loads don't crash core infrastructure architectures",
    "pandas": "used heavily in data wrangling pipelines for cleaning and pre-processing tabular logs",
    "gradient_descent": "used as the foundational optimization engine in almost all model training pipelines",
}

# New Capability-Based Outcome Mappings (What can you DO)
OUTCOME_MAP = {
    "word2vec": "ability to implement and use word embeddings for basic NLP tasks",
    "nlp": "ability to build systems that analyze, parse, and utilize human text",
    "deep_learning": "ability to architect complex hierarchical models using neural frameworks",
    "computer_vision": "ability to write algorithms that extract features from continuous image data",
    "sql": "ability to safely query, join, and analyze complex relational tables",
    "react": "ability to build and deploy dynamic, state-driven front-end components",
    "docker": "ability to containerize and isolate application environments gracefully",
    "kubernetes": "ability to manage, auto-scale, and deploy containerized network applications",
    "microservices": "ability to break massive monoliths down into stable, isolated services",
    "data_science": "ability to derive and present mathematical insights from messy datasets",
    "pytorch": "ability to build and train neural network models",
    "machine_learning": "ability to build and evaluate predictive models logically",
    "system_design": "ability to confidently map out highly scalable, fault-tolerant infrastructure",
    "gradient_descent": "ability to optimize simple machine learning models mathematically",
    "pandas": "ability to programmatically transform and clean messy tabular datasets",
}


# ---------------------------------------------------------------------------
# Processor Class
# ---------------------------------------------------------------------------
class MediumProcessor:
    """
    Processes raw Medium dataset CSV into structured experience narratives.
    Extracts rich semantic signals and actionable human-relatable insights.
    """

    def __init__(self, input_path: str, output_path: str, use_llm: bool = False):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.use_llm = use_llm
        self.llm_model = None
        
        if self.use_llm:
            if not HAS_LLM_DEPS:
                logger.error("LLM dependencies missing. Falling back to deterministic mode.")
                self.use_llm = False
            else:
                load_dotenv()
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    logger.error("GEMINI_API_KEY NOT FOUND. Falling back to deterministic mode.")
                    self.use_llm = False
                else:
                    genai.configure(api_key=api_key)
                    self.llm_model = genai.GenerativeModel("gemini-2.5-flash")
                    logger.info("LLM Enhancement enabled via Gemini 2.5 Flash.")
        
        if not self.use_llm:
            logger.info("Initializing Advanced Deterministic Mode (Experiential Inference).")

    def load_data(self) -> pd.DataFrame:
        logger.info(f"Loading raw dataset from {self.input_path}...")
        try:
            df = pd.read_csv(self.input_path)
            columns_to_check = [col for col in ['text', 'title', 'subtitle'] if col in df.columns]
            if not columns_to_check:
                logger.error("CSV must contain 'text', 'title', or 'subtitle' columns.")
                return pd.DataFrame()
                
            df = df.dropna(subset=columns_to_check, how='all')
            return df
        except Exception as e:
            logger.error(f"Failed to load CSV: {e}")
            raise

    def clean_text(self, text: str) -> str:
        if not isinstance(text, str) or not text.strip():
            return ""
        
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'http\S+', '', text)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    def chunk_text(self, text: str) -> List[str]:
        if not text:
            return []
            
        sentences = [s.strip() + '.' for s in re.split(r'[.!?]\s+', text) if s.strip()]
        
        if not sentences:
            return [text]
            
        chunks = []
        current_chunk = []
        
        for sentence in sentences:
            current_chunk.append(sentence)
            if len(current_chunk) >= 5:
                chunks.append(" ".join(current_chunk))
                current_chunk = []
                
        if current_chunk:
            if chunks and len(current_chunk) < 3:
                chunks[-1] += " " + " ".join(current_chunk)
            else:
                chunks.append(" ".join(current_chunk))
                
        if not chunks:
            return [text]
            
        return chunks

    def _infer_confidence_signal(self, stage: str, exp_type: str, primary_theme: str) -> str:
        """Generates psychologically reassuring meta-narrative."""
        domain = primary_theme.replace('_', ' ').title() if primary_theme else "the tech industry"
        
        if stage == "beginner":
            return f"this is one of the first concepts most {domain} engineers learn"
        elif stage == "intermediate":
            return f"commonly explored as a core competency in {domain}"
        elif stage == "advanced":
            return f"an advanced {domain} implementation demonstrating deep technical maturity"
            
        if exp_type == "project":
            return f"a strong indicator of practical problem-solving capability in {domain}"
            
        return "a standard starting point for practitioners in this field"

    def _extract_determenistic(self, chunk: str) -> dict:
        chunk_lower = chunk.lower()
        
        # 1. Phase-Level Skill Extraction (Specific to General mapping)
        skills = {}
        found_phrases = []
        found_words = []
        
        for phrase, skill_mapping in PHRASE_SKILLS.items():
            if re.search(r'\b' + re.escape(phrase) + r'\b', chunk_lower):
                found_phrases.append(phrase)
                for i, skill in enumerate(skill_mapping):
                    weight = 1.0 if i == 0 else max(0.4, 1.0 - (i * 0.3))
                    skills[skill] = max(skills.get(skill, 0.0), weight)
                
        for word, skill_mapping in SINGLE_WORD_SKILLS.items():
            if re.search(r'\b' + re.escape(word) + r'\b', chunk_lower):
                found_words.append(word)
                for i, skill in enumerate(skill_mapping):
                    weight = 0.8 if i == 0 else max(0.4, 0.8 - (i * 0.3))
                    skills[skill] = max(skills.get(skill, 0.0), weight)
                
        # 2. Experience Type
        exp_type = "tutorial"
        if any(w in chunk_lower for w in ["how to", "guide", "introduction", "step-by-step", "tutorial", "learn", "start"]):
            exp_type = "tutorial"
        elif any(w in chunk_lower for w in ["hands-on", "build", "implementation", "created", "developed", "project"]):
            exp_type = "project"
        elif any(w in chunk_lower for w in ["analysis", "study", "comparison", "research", "evaluate", "paper"]):
            exp_type = "research"
        elif any(w in chunk_lower for w in ["journey", "career", "interview", "my experience"]):
            exp_type = "career_story"
            
        # 3. Career Stage
        stage = "intermediate"
        if any(w in chunk_lower for w in ["beginner", "start", "starting", "basics", "introduction", "easy"]):
            stage = "beginner"
        elif any(w in chunk_lower for w in ["advanced", "scaling", "scale", "optimize", "optimization", "senior", "deep dive"]):
            stage = "advanced"
        elif exp_type == "project" or any(w in chunk_lower for w in ["hands-on", "implementation"]):
            stage = "intermediate"
            
        # 4. Themes (Direct mapping + Intelligent Inference from Skills)
        themes = set()
        for theme_name, keywords in THEME_MAP.items():
            for kw in keywords:
                if re.search(r'\b' + re.escape(kw) + r'\b', chunk_lower):
                    themes.add(theme_name)
                    break
                    
        for skill_id in skills.keys():
            if skill_id in SKILL_TO_THEME:
                themes.add(SKILL_TO_THEME[skill_id])
                
        themes = list(themes)[:4]
        
        # 5. Signals
        learning_v = 0.8 if "step-by-step" in chunk_lower or exp_type == "tutorial" else 0.5
        practical = 0.9 if "implementation" in chunk_lower or exp_type == "project" else 0.4
        depth = 0.9 if len(skills) >= 2 or exp_type == "research" else 0.5
        leadership_score = 0.7 if any(w in chunk_lower for w in ["led", "managed", "mentor", "vision"]) else 0.1
        
        signals = {
            "learning_velocity": learning_v,
            "project_depth": depth,
            "practical_exposure": practical,
            "leadership": leadership_score
        }
        
        # 6. Semantic Tags (Verb + Skill/Concept)
        tags = set()
        
        if found_phrases:
            tags.add(f"implemented {found_phrases[0]}")
            if len(found_phrases) > 1:
                tags.add(f"explored {found_phrases[1]}")
                
        if found_words:
            tags.add(f"used {found_words[0]}")
            if len(found_words) > 1 and len(tags) < 4:
                tags.add(f"worked with {found_words[1]}")
                
        if exp_type == "project":
            tags.add("built practical implementation")
        elif exp_type == "tutorial":
            tags.add("created learning guide")
            
        if themes:
            tags.add(f"focused on {themes[0].replace('_', ' ')}")
            
        # 7. Quality Guarantees & Fallback
        if not skills:
            skills = {"general_technical": 1.0}
        if not themes:
            themes = ["technology"]
        if not tags:
            tags.add("shared technical experience")
            
        total = sum(skills.values())
        skills = {k: round(v / total, 4) for k, v in skills.items()}
            
        # 8. Experience Insight Generation
        primary_concept = None
        for k in skills.keys():
            if k in WHAT_YOU_LEARN_MAP:
                primary_concept = k
                break
        
        if not primary_concept and found_phrases:
            primary_concept_name = found_phrases[0]
            what_learn = f"how {primary_concept_name} works and is implemented"
        elif primary_concept in WHAT_YOU_LEARN_MAP:
            primary_concept_name = primary_concept
            what_learn = WHAT_YOU_LEARN_MAP[primary_concept]
        else:
            primary_concept_name = themes[0] if themes else "technical concepts"
            what_learn = f"how {primary_concept_name.replace('_', ' ')} principles operate"

        how_you_learn = "guided exploration"
        if exp_type == "tutorial": how_you_learn = "step-by-step guided implementation"
        elif exp_type == "project": how_you_learn = "hands-on building and experimentation"
        elif exp_type == "research": how_you_learn = "analysis and comparison of approaches"
        elif exp_type == "career_story": how_you_learn = "experiential narrative reflection"

        diff_str = "beginner" if stage == "beginner" else "intermediate" if stage == "intermediate" else "advanced"

        time_est = "1-3 hours"
        if exp_type == "project": time_est = "3-8 hours"
        elif exp_type in ["research", "career_story"]: time_est = "5+ hours"

        # Dynamically map Real World Relevance
        relevance = REAL_WORLD_MAP.get(primary_concept, "used in real-world software and machine learning systems")

        # Dynamically map Confidence Signal
        conf_signal = self._infer_confidence_signal(stage, exp_type, themes[0] if themes else "")

        # Dynamically map Experience Outcome
        outcome = OUTCOME_MAP.get(primary_concept, f"ability to apply practical {primary_concept_name.replace('_', ' ')} logic in engineering scenarios")

        insight = {
            "what_you_learn": what_learn,
            "how_you_learn": how_you_learn,
            "difficulty": diff_str,
            "time_estimate": time_est,
            "real_world_relevance": relevance,
            "confidence_signal": conf_signal,
            "experience_outcome": outcome
        }
        
        # 9. Smart Summary
        raw_concepts = [w.capitalize() for w in found_phrases[:2]] if found_phrases else [w.capitalize() for w in found_words[:2]]
        if raw_concepts:
            concept_str = " and ".join(raw_concepts)
            summary = f"Learn {what_learn} using {concept_str}."
        else:
            summary = f"Explore an experience covering {what_learn.replace('how ', '')}."
            
        if len(chunk) > 150 and exp_type != "tutorial":
            sentences = [s.strip() for s in re.split(r'[.!?]\s+', chunk) if s.strip()]
            summary = ". ".join(sentences[:2]) + "." if sentences else summary

        # 10. Confidence Score Bonus
        confidence = 0.5
        if found_phrases:
            confidence += 0.3 * min(len(found_phrases), 1)
        if len(skills) > 1 and "general_technical" not in skills:
            confidence += 0.2
        confidence = min(round(confidence, 4), 1.0)
        
        semantic_tags = list(tags)
        
        return {
            "summary": summary,
            "themes": themes,
            "skills": skills,
            "career_stage": stage,
            "experience_type": exp_type,
            "signals": signals,
            "semantic_tags": semantic_tags,
            "experience_insight": insight,
            "confidence_score": confidence
        }

    def _extract_llm(self, chunk: str) -> dict:
        prompt = f"""
        You are extracting structured career signals from a technical narrative excerpt (a Medium article title/chunk).
        Analyze the text and extract profound, structured JSON adhering strictly to the schema.
        Be precise. Avoid generic outputs. If the text is a title, infer strongly related concepts.
        
        Text to analyze:
        "{chunk}"
        """
        try:
            response = self.llm_model.generate_content(
                prompt,
                generation_config=genai.GenerationConfig(
                    response_mime_type="application/json",
                    response_schema=StructuredFeatures,
                    temperature=0.2, 
                )
            )
            data = json.loads(response.text)
            
            tags = data.get("semantic_tags", [])
            if not tags: tags = ["shared technical experience"]
            
            summary = data.get("summary", "")
            if not summary: summary = chunk[:200] + "..." if len(chunk) > 200 else chunk
                
            skills = data.get("skills", {})
            if not skills: skills = {"general_technical": 1.0}
                
            themes = data.get("themes", [])
            if not themes: themes = ["technology"]
            
            insight = data.get("experience_insight", {
                "what_you_learn": "how these technical concepts operate",
                "how_you_learn": "guided exploration",
                "difficulty": "intermediate",
                "time_estimate": "1-3 hours",
                "real_world_relevance": "used in real-world software and machine learning systems",
                "confidence_signal": "a standard starting point for practitioners in this field",
                "experience_outcome": "ability to apply this concept in practical scenarios"
            })
                
            return {
                "summary": summary,
                "themes": themes,
                "skills": skills,
                "career_stage": data.get("career_stage", "intermediate"),
                "experience_type": data.get("experience_type", "tutorial"),
                "signals": data.get("signals", {
                    "learning_velocity": 0.5, "project_depth": 0.5,
                    "practical_exposure": 0.5, "leadership": 0.0
                }),
                "semantic_tags": tags,
                "experience_insight": insight,
                "confidence_score": data.get("confidence_score", 0.9)
            }
        except Exception as e:
            logger.warning(f"LLM Extraction failed: {e}. Falling back to deterministic.")
            return self._extract_determenistic(chunk)

    def extract_features(self, chunk: str) -> dict:
        if self.use_llm:
            return self._extract_llm(chunk)
        return self._extract_determenistic(chunk)

    def process(self, limit: int = None) -> List[dict]:
        df = self.load_data()
        
        if limit is not None:
            df = df.head(limit)
            
        narratives = []
        total_articles = len(df)
        chunks_generated = 0
        skipped = 0
        
        logger.info(f"Starting advanced experiential extraction {'with LLM' if self.use_llm else '(Deterministic)'} for {total_articles} articles...")
        
        for idx, row in df.iterrows():
            source_id = str(row.get('id', idx))
            url = str(row.get('url', ''))
            
            text_parts = []
            if 'title' in row and pd.notna(row['title']):
                text_parts.append(str(row['title']))
            if 'subtitle' in row and pd.notna(row['subtitle']):
                text_parts.append(str(row['subtitle']))
            if 'text' in row and pd.notna(row['text']):
                text_parts.append(str(row['text']))
                
            raw_text = ". ".join(text_parts).strip()
            if not raw_text:
                skipped += 1
                continue
                
            clean = self.clean_text(raw_text)
            if not clean:
                skipped += 1
                continue
                
            chunks = self.chunk_text(clean)
            
            for chunk_idx, chunk in enumerate(chunks):
                features = self.extract_features(chunk)
                
                narrative_record = {
                    "narrative_id": f"med_{source_id}_chunk_{chunk_idx}",
                    "source_id": source_id,
                    "url": url,
                    "text": chunk,
                    **features
                }
                
                narratives.append(narrative_record)
                chunks_generated += 1
                
        if total_articles > 0:
            skip_ratio = skipped / total_articles
            if skip_ratio > 0.8:
                logger.warning(f"HIGH SKIP RATE: {skip_ratio*100:.1f}% of articles produced empty output!")

        logger.info("=== Pipeline Summary ===")
        logger.info(f"Loaded {total_articles} rows")
        logger.info(f"Generated {chunks_generated} chunks")
        logger.info(f"Created {len(narratives)} narratives")
        logger.info(f"Saved to {self.output_path}")
        
        return narratives

    def save_output(self, data: List[dict]):
        logger.info(f"Ensuring output directory exists: {self.output_path.parent}")
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if not data:
            logger.info("Output data is empty. Writing empty JSON array [].")
        else:
            logger.info(f"Writing {len(data)} narratives to {self.output_path}")
            
        with open(self.output_path, 'w', encoding='utf-8') as f:
            json.dump(data if data else [], f, indent=2, ensure_ascii=False)
            
        logger.info("Save successful.")


def main():
    parser = argparse.ArgumentParser(description="Process Medium dataset into structured experiential narratives.")
    parser.add_argument("--input", default="data/raw/experiences/medium_data.csv", help="Path to raw Medium CSV.")
    parser.add_argument("--output", default="data/processed/experiences/medium_narratives.json", help="Path to save output JSON.")
    parser.add_argument("--use-llm", action="store_true", help="Enable Optional LLM (Gemini) enhancement layer.")
    parser.add_argument("--limit", type=int, default=None, help="Optional row limit for quick testing.")
    args = parser.parse_args()

    processor = MediumProcessor(
        input_path=args.input,
        output_path=args.output,
        use_llm=args.use_llm
    )
    
    narratives = processor.process(limit=args.limit)
    processor.save_output(narratives)
    
    return narratives


if __name__ == "__main__":
    main()
