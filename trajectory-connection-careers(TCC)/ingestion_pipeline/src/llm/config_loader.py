import os
import yaml
from .models import FullLLMConfig

def load_llm_config(path: str = "configs/llm.yaml") -> FullLLMConfig:
    """
    Loads LLM configuration from YAML with environment variable substitution.
    """
    def expand_env_vars(data):
        if isinstance(data, dict):
            return {k: expand_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [expand_env_vars(i) for i in data]
        elif isinstance(data, str):
            # Regex to find ${VAR} or ${VAR:-default}
            import re
            pattern = re.compile(r'\${(\w+)(?::-([^}]*))?}')
            def replace(match):
                var_name = match.group(1)
                default_value = match.group(2)
                return os.getenv(var_name, default_value if default_value is not None else match.group(0))
            return pattern.sub(replace, data)
        return data

    with open(path, "r") as f:
        config_dict = yaml.safe_load(f)
    
    expanded_config = expand_env_vars(config_dict)
    return FullLLMConfig(**expanded_config)
