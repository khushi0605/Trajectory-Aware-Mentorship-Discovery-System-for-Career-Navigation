import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

from dotenv import load_dotenv

# Optional imports handled gracefully
try:
    import chromadb
    from chromadb.utils import embedding_functions
except ImportError:
    print("chromadb not installed. Please install with: pip install chromadb openai")
    sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("chroma_ingestor")

class MediumChromaIngestor:
    def __init__(self, 
                 input_path: str = "data/processed/experiences/medium_narratives.json",
                 db_directory: str = "data/chroma_db",
                 collection_name: str = "medium_narratives",
                 batch_size: int = 500):
        
        load_dotenv()
        
        self.input_path = Path(input_path)
        self.db_directory = Path(db_directory)
        self.collection_name = collection_name
        self.batch_size = batch_size
        
        # Verify API key
        # Removed: using local embedding model instead.
            
        # Initialize ChromaDB Client
        logger.info(f"Initializing ChromaDB Client at {self.db_directory}")
        self.client = chromadb.PersistentClient(path=str(self.db_directory))
        
        # Configure Local Offline Embedding Function (all-MiniLM-L6-v2 is the default)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        # Create or Get Collection
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn
        )
        logger.info(f"Connected to collection: {self.collection_name}")

    def load_data(self) -> List[Dict[str, Any]]:
        if not self.input_path.exists():
            logger.error(f"Input file not found: {self.input_path}")
            sys.exit(1)
            
        logger.info(f"Loading JSON data from {self.input_path}")
        with open(self.input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        logger.info(f"Loaded {len(data)} narratives.")
        return data

    def prepare_batches(self, narratives: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Split data into manageable chunks for the embedding API."""
        return [narratives[i:i + self.batch_size] for i in range(0, len(narratives), self.batch_size)]

    def ingest(self):
        narratives = self.load_data()
        if not narratives:
            logger.warning("No data found to ingest.")
            return

        batches = self.prepare_batches(narratives)
        total_batches = len(batches)
        
        logger.info(f"Starting ingestion of {len(narratives)} records across {total_batches} batches...")
        
        processed_count = 0
        
        for idx, batch in enumerate(batches, 1):
            ids = []
            documents = []
            metadatas = []
            
            for item in batch:
                n_id = item.get("narrative_id")
                if not n_id:
                    continue
                    
                text = item.get("text", "")
                summary = item.get("summary", "")
                themes = item.get("themes", [])
                skills = item.get("skills", {})
                
                # Format specific context components
                theme_str = " ".join(themes)
                skill_str = " ".join(skills.keys()) if isinstance(skills, dict) else " ".join(skills)
                
                # Combined Representation exactly as specified
                combined_text = f"{text} {summary} {theme_str} {skill_str}".strip()
                
                # Serialize any nested dictionaries/lists in metadata to strings 
                # (Chroma DB requires metadata values to be str, int, float, or bool)
                safe_metadata = {}
                for key, value in item.items():
                    if value is None:
                        safe_metadata[key] = ""
                    elif isinstance(value, (dict, list)):
                        safe_metadata[key] = json.dumps(value)
                    else:
                        safe_metadata[key] = value
                
                ids.append(str(n_id))
                documents.append(combined_text)
                metadatas.append(safe_metadata)
            
            if not ids:
                continue
                
            try:
                self.collection.upsert(
                    ids=ids,
                    documents=documents,
                    metadatas=metadatas
                )
                processed_count += len(ids)
                logger.info(f"Successfully processed batch {idx}/{total_batches} ({processed_count}/{len(narratives)} records)")
            except Exception as e:
                logger.error(f"Failed to upsert batch {idx}: {e}")
                
        logger.info(f"✅ Ingestion Complete. {processed_count} narratives successfully stored in '{self.collection_name}' collection.")
        count = self.collection.count()
        logger.info(f"Total documents currently in collection: {count}")

if __name__ == "__main__":
    ingestor = MediumChromaIngestor()
    ingestor.ingest()
