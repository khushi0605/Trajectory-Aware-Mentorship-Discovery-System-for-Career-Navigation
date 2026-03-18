import json
import logging
from pathlib import Path
from typing import Any, Dict
from datetime import datetime, timezone

logger = logging.getLogger("src.storage.raw_repo")

class RawRepo:
    """Repository for storing and retrieving raw ingestion signals."""
    
    def __init__(self, base_path: str = "data/raw"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def store(self, data: Dict[str, Any], path: Path) -> Path:
        """Save raw dictionary as JSON to the specified path."""
        full_path = (self.base_path / path).resolve()
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Add ingestion metadata if not present
        if "ingestion_metadata" not in data:
            data["ingestion_metadata"] = {
                "stored_at": datetime.now(timezone.utc).isoformat(),
            }
            
        try:
            with open(full_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
            logger.info(f"Raw profile stored at: {full_path}")
            return full_path
        except Exception as e:
            logger.error(f"Failed to store raw data to {full_path}: {e}")
            raise
