from __future__ import annotations
from dataclasses import dataclass
import os
import yaml
from pathlib import Path

@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str

@dataclass(frozen=True)
class ChromaConfig:
    persist_directory: str
    collection_name: str
    embedding_model: str

@dataclass(frozen=True)
class RetrievalParams:
    top_k_chroma: int
    neo4j_result_limit: int
    timeout_seconds: int
    eacr_behavioral_limit: int

@dataclass(frozen=True)
class RetrieverConfig:
    neo4j: Neo4jConfig
    chroma: ChromaConfig
    params: RetrievalParams

    @classmethod
    def load(cls, path: str = "configs/retrieval.yaml") -> RetrieverConfig:
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")
            
        def expand_env_vars(data):
            if isinstance(data, dict):
                return {k: expand_env_vars(v) for k, v in data.items()}
            elif isinstance(data, list):
                return [expand_env_vars(i) for i in data]
            elif isinstance(data, str):
                import re
                pattern = re.compile(r'\${(\w+)(?::-([^}]*))?}')
                def replace(match):
                    var_name = match.group(1)
                    default_value = match.group(2)
                    return os.getenv(var_name, default_value if default_value is not None else match.group(0))
                return pattern.sub(replace, data)
            return data

        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            
        data = expand_env_vars(data)
            
        return cls(
            neo4j=Neo4jConfig(**data.get("neo4j", {})),
            chroma=ChromaConfig(**data.get("chroma", {})),
            params=RetrievalParams(**data.get("retrieval_params", {}))
        )
