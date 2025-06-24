import json
import logging
import pickle
import os
from typing import List, Tuple, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

from .database import DatabaseService

logger = logging.getLogger(__name__)


class PersistentEnhancedSchemaVectorStore:
    """Enhanced vector store with persistent storage for metadata and vector index."""

    def __init__(self, database_service: DatabaseService, model_name: str = "all-MiniLM-L6-v2", storage_path: str = "knowledge_base"):
        self.database_service = database_service
        self.model = SentenceTransformer(model_name)
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        self.index = None
        self.schema_texts: List[str] = []
        self.table_names: List[str] = []
        self.table_metadata: Dict[str, Dict[str, Any]] = {}
        self.is_metadata_loaded = False
        self.metadata_upload_time: Optional[datetime] = None
        
        self._load_from_disk()

    def _get_metadata_file(self) -> Path:
        """Get path to metadata file."""
        return self.storage_path / "metadata.json"

    def _get_index_file(self) -> Path:
        """Get path to vector index file."""
        return self.storage_path / "vector_index.faiss"

    def _get_schema_texts_file(self) -> Path:
        """Get path to schema texts file."""
        return self.storage_path / "schema_texts.pkl"

    def _get_table_names_file(self) -> Path:
        """Get path to table names file."""
        return self.storage_path / "table_names.pkl"

    def _save_to_disk(self) -> None:
        """Save all data to disk for persistence."""
        try:
            metadata_to_save = {
                "table_metadata": self.table_metadata,
                "is_metadata_loaded": self.is_metadata_loaded,
                "metadata_upload_time": self.metadata_upload_time.isoformat() if self.metadata_upload_time else None
            }
            
            with open(self._get_metadata_file(), 'w', encoding='utf-8') as f:
                json.dump(metadata_to_save, f, indent=2, ensure_ascii=False)
            
            with open(self._get_schema_texts_file(), 'wb') as f:
                pickle.dump(self.schema_texts, f)
            
            with open(self._get_table_names_file(), 'wb') as f:
                pickle.dump(self.table_names, f)
            
            if self.index is not None:
                faiss.write_index(self.index, str(self._get_index_file()))
            
            logger.info("Knowledge base saved to disk successfully")
            
        except Exception as e:
            logger.error(f"Failed to save knowledge base to disk: {e}")

    def _load_from_disk(self) -> None:
        """Load data from disk if available."""
        try:
            metadata_file = self._get_metadata_file()
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    saved_data = json.load(f)
                
                self.table_metadata = saved_data.get("table_metadata", {})
                self.is_metadata_loaded = saved_data.get("is_metadata_loaded", False)
                
                upload_time_str = saved_data.get("metadata_upload_time")
                if upload_time_str:
                    self.metadata_upload_time = datetime.fromisoformat(upload_time_str)
            
            schema_texts_file = self._get_schema_texts_file()
            if schema_texts_file.exists():
                with open(schema_texts_file, 'rb') as f:
                    self.schema_texts = pickle.load(f)
            
            table_names_file = self._get_table_names_file()
            if table_names_file.exists():
                with open(table_names_file, 'rb') as f:
                    self.table_names = pickle.load(f)
            
            index_file = self._get_index_file()
            if index_file.exists():
                self.index = faiss.read_index(str(index_file))
            
            if self.is_metadata_loaded:
                logger.info(f"Knowledge base loaded from disk: {len(self.table_names)} tables indexed")
            
        except Exception as e:
            logger.warning(f"Failed to load knowledge base from disk: {e}")
            self._reset_state()

    def _reset_state(self) -> None:
        """Reset all state variables."""
        self.index = None
        self.schema_texts = []
        self.table_names = []
        self.table_metadata = {}
        self.is_metadata_loaded = False
        self.metadata_upload_time = None

    def process_metadata(self, metadata_json: Dict[str, Any]) -> Dict[str, Any]:
        """Process uploaded metadata JSON and build vector store with persistence."""
        try:
            logger.info("Processing metadata JSON with persistence...")
            
            if "metadata" not in metadata_json or "tables" not in metadata_json:
                raise ValueError("Invalid metadata format. Expected 'metadata' and 'tables' keys.")
            
            processed_tables = 0
            enriched_texts = []
            table_names = []
            
            for table_data in metadata_json["tables"]:
                try:
                    table_name = table_data["schema"]["table_name"]
                    schema_info = table_data["schema"]
                    llm_analysis = table_data.get("llm_analysis", {})
                    
                    enriched_text = self._create_enriched_text(table_name, schema_info, llm_analysis)
                    
                    enriched_texts.append(enriched_text)
                    table_names.append(table_name)
                    
                    self.table_metadata[table_name] = {
                        "schema": schema_info,
                        "llm_analysis": llm_analysis,
                        "processed_at": table_data.get("processed_at")
                    }
                    
                    processed_tables += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing table data: {e}")
                    continue
            
            if not enriched_texts:
                raise ValueError("No valid table data found in metadata")
            
            logger.info(f"Creating embeddings for {len(enriched_texts)} tables...")
            embeddings = self.model.encode(enriched_texts)
            dim = embeddings.shape[1]
            
            self.index = faiss.IndexFlatL2(dim)
            self.index.add(np.array(embeddings, dtype="float32"))
            
            self.schema_texts = enriched_texts
            self.table_names = table_names
            self.is_metadata_loaded = True
            self.metadata_upload_time = datetime.utcnow()
            
            self._save_to_disk()
            
            logger.info(f"Successfully processed and saved {processed_tables} tables from metadata")
            
            return {
                "success": True,
                "processed_tables": processed_tables,
                "total_tables": len(metadata_json["tables"]),
                "upload_time": self.metadata_upload_time.isoformat(),
                "message": f"Metadata processed successfully. {processed_tables} tables indexed and saved to disk."
            }
            
        except Exception as e:
            logger.error(f"Error processing metadata: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to process metadata"
            }

    def _create_enriched_text(self, table_name: str, schema_info: Dict[str, Any], llm_analysis: Dict[str, Any]) -> str:
        """Create enriched text representation combining schema and LLM analysis."""
        
        text_parts = [f"Table: {table_name}"]
        
        if "columns" in schema_info:
            columns_info = []
            for col in schema_info["columns"]:
                col_text = f"{col['name']} ({col['type']}"
                if not col.get('nullable', True):
                    col_text += ", NOT NULL"
                if col.get('autoincrement'):
                    col_text += ", AUTO_INCREMENT"
                col_text += ")"
                columns_info.append(col_text)
            
            text_parts.append("Columns: " + ", ".join(columns_info))
        
        if schema_info.get("primary_keys"):
            text_parts.append("Primary Keys: " + ", ".join(schema_info["primary_keys"]))
        
        if schema_info.get("foreign_keys"):
            fk_info = []
            for fk in schema_info["foreign_keys"]:
                if isinstance(fk, dict):
                    fk_info.append(f"{fk.get('column', '')} -> {fk.get('referenced_table', '')}.{fk.get('referenced_column', '')}")
                else:
                    fk_info.append(str(fk))
            text_parts.append("Foreign Keys: " + ", ".join(fk_info))
        
        if llm_analysis.get("purpose"):
            text_parts.append("Purpose: " + llm_analysis["purpose"])
        
        if llm_analysis.get("data_patterns"):
            text_parts.append("Data Patterns: " + "; ".join(llm_analysis["data_patterns"]))
        
        if llm_analysis.get("relationships"):
            rel_info = []
            for rel in llm_analysis["relationships"]:
                if isinstance(rel, dict):
                    rel_info.append(f"Related to {rel.get('table', '')} via {rel.get('relationship_type', '')}")
                else:
                    rel_info.append(str(rel))
            text_parts.append("Relationships: " + "; ".join(rel_info))
        
        if llm_analysis.get("observations"):
            text_parts.append("Observations: " + "; ".join(llm_analysis["observations"]))
        
        if schema_info.get("sample_data"):
            sample_keys = []
            for sample in schema_info["sample_data"][:3]:
                if isinstance(sample, dict):
                    sample_keys.extend(sample.keys())
            if sample_keys:
                text_parts.append("Sample Data Fields: " + ", ".join(set(sample_keys)))
        
        return "\n".join(text_parts)

    def build_from_database(self) -> None:
        """Fallback method to build from database if no metadata is uploaded."""
        if self.is_metadata_loaded:
            logger.info("Metadata already loaded, skipping database build")
            return
            
        logger.info("Building schema store from database...")
        table_names = self.database_service.get_table_names()
        schemas = []
        
        for name in table_names:
            try:
                info = self.database_service.describe_table(name)
                schemas.append(f"Table {name}: {info}")
                self.table_names.append(name)
            except Exception as e:
                logger.warning(f"Failed to get schema for {name}: {e}")
                continue
        
        if schemas:
            embeddings = self.model.encode(schemas)
            dim = embeddings.shape[1]
            self.index = faiss.IndexFlatL2(dim)
            self.index.add(np.array(embeddings, dtype="float32"))
            self.schema_texts = schemas
            logger.info(f"Schema vector store built from database with {len(schemas)} tables")

    def search(self, query: str, k: int = 5) -> List[Tuple[str, str, Dict[str, Any]]]:
        """Search for relevant table schemas with enhanced metadata."""
        if self.index is None:
            self.build_from_database()
            if self.index is None:
                return []
        
        vector = self.model.encode([query])
        distances, indices = self.index.search(np.array(vector, dtype="float32"), k)
        
        results = []
        for idx in indices[0]:
            if idx < len(self.table_names):
                table_name = self.table_names[idx]
                schema_text = self.schema_texts[idx]
                metadata = self.table_metadata.get(table_name, {})
                results.append((table_name, schema_text, metadata))
        
        return results

    def get_table_details(self, table_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific table."""
        return self.table_metadata.get(table_name)

    def get_status(self) -> Dict[str, Any]:
        """Get status of the knowledge base."""
        return {
            "metadata_loaded": self.is_metadata_loaded,
            "upload_time": self.metadata_upload_time.isoformat() if self.metadata_upload_time else None,
            "total_tables": len(self.table_names),
            "index_built": self.index is not None,
            "storage_path": str(self.storage_path),
            "files_exist": {
                "metadata": self._get_metadata_file().exists(),
                "vector_index": self._get_index_file().exists(),
                "schema_texts": self._get_schema_texts_file().exists(),
                "table_names": self._get_table_names_file().exists()
            }
        }

    def clear_all(self) -> None:
        """Clear all metadata and reset the knowledge base."""
        self._reset_state()
        
        try:
            for file_path in [
                self._get_metadata_file(),
                self._get_index_file(),
                self._get_schema_texts_file(),
                self._get_table_names_file()
            ]:
                if file_path.exists():
                    os.remove(file_path)
            
            logger.info("Knowledge base cleared completely and files removed")
        except Exception as e:
            logger.error(f"Error removing files during clear: {e}")

    def rebuild_index(self) -> None:
        """Rebuild the vector index from existing metadata."""
        if not self.is_metadata_loaded:
            raise ValueError("No metadata loaded to rebuild index from")
        
        if not self.schema_texts:
            raise ValueError("No schema texts available for index rebuild")
        
        logger.info("Rebuilding vector index...")
        
        embeddings = self.model.encode(self.schema_texts)
        dim = embeddings.shape[1]
        
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(np.array(embeddings, dtype="float32"))
        
        self._save_to_disk()
        
        logger.info(f"Vector index rebuilt and saved with {len(self.schema_texts)} tables")