from pathlib import Path
from typing import Optional
from src.core.types import SourceType

class DataRouter:
    """Routes data types from various sources to their respective storage locations."""
    
    @staticmethod
    def get_raw_path(source: str, data_type: str, identifier: str) -> Path:
        """
        Generate a relative storage path based on information type.
        
        Example: profiles/github_torvalds.json
        """
        # Ensure identifier is safe for filename
        safe_id = "".join([c if c.isalnum() or c in "-_" else "_" for c in identifier])
        filename = f"{source}_{safe_id}.json"
        
        # Folder structure based on data type (e.g., profiles, experiences, skill_transitions)
        return Path(data_type) / filename
