import importlib
from typing import Dict, Any
from src.core.interfaces import ICollector

class CollectorFactory:
    @staticmethod
    def get_collector(source_name: str, config: Dict[str, Any]) -> ICollector:
        """Instantiate a collector based on source configuration."""
        source_cfg = config.get("sources", {}).get(source_name)
        if not source_cfg:
            raise ValueError(f"No configuration found for source: {source_name}")
            
        class_path = source_cfg.get("collector_class")
        module_path, class_name = class_path.rsplit(".", 1)
        
        module = importlib.import_module(module_path)
        collector_cls = getattr(module, class_name)
        
        return collector_cls(source_name=source_name, config=source_cfg)
