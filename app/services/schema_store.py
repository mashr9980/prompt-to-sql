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

    def __init__(self, database_service: DatabaseService, model_name: str = "all-MiniLM-L6-v2", storage_path: str = "knowledge_base"):
        self.database_service = database_service
        self.model = SentenceTransformer(model_name)
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        self.index = None
        self.schema_texts: List[str] = []
        self.table_names: List[str] = []
        self.table_metadata: Dict[str, Dict[str, Any]] = {}
        
        self.business_logic_texts: List[str] = []
        self.business_logic_metadata: List[Dict[str, Any]] = []
        
        self.combined_texts: List[str] = []
        self.text_types: List[str] = []
        self.text_identifiers: List[str] = []
        
        self.is_metadata_loaded = False
        self.is_business_logic_loaded = False
        self.metadata_upload_time: Optional[datetime] = None
        self.business_logic_upload_time: Optional[datetime] = None
        
        self._load_from_disk()

    def _get_metadata_file(self) -> Path:
        return self.storage_path / "metadata.json"

    def _get_business_logic_file(self) -> Path:
        return self.storage_path / "business_logic.json"

    def _get_index_file(self) -> Path:
        return self.storage_path / "vector_index.faiss"

    def _get_combined_texts_file(self) -> Path:
        return self.storage_path / "combined_texts.pkl"

    def _get_text_metadata_file(self) -> Path:
        return self.storage_path / "text_metadata.pkl"

    def _save_to_disk(self) -> None:
        try:
            metadata_to_save = {
                "table_metadata": self.table_metadata,
                "is_metadata_loaded": self.is_metadata_loaded,
                "metadata_upload_time": self.metadata_upload_time.isoformat() if self.metadata_upload_time else None
            }
            
            with open(self._get_metadata_file(), 'w', encoding='utf-8') as f:
                json.dump(metadata_to_save, f, indent=2, ensure_ascii=False)
            
            business_logic_to_save = {
                "business_logic_texts": self.business_logic_texts,
                "business_logic_metadata": self.business_logic_metadata,
                "is_business_logic_loaded": self.is_business_logic_loaded,
                "business_logic_upload_time": self.business_logic_upload_time.isoformat() if self.business_logic_upload_time else None
            }
            
            with open(self._get_business_logic_file(), 'w', encoding='utf-8') as f:
                json.dump(business_logic_to_save, f, indent=2, ensure_ascii=False)
            
            combined_data = {
                "combined_texts": self.combined_texts,
                "text_types": self.text_types,
                "text_identifiers": self.text_identifiers,
                "schema_texts": self.schema_texts,
                "table_names": self.table_names
            }
            
            with open(self._get_combined_texts_file(), 'wb') as f:
                pickle.dump(combined_data, f)
            
            if self.index is not None:
                faiss.write_index(self.index, str(self._get_index_file()))
            
            logger.info("Knowledge base saved to disk successfully")
            
        except Exception as e:
            logger.error(f"Failed to save knowledge base to disk: {e}")

    def _load_from_disk(self) -> None:
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
            
            business_logic_file = self._get_business_logic_file()
            if business_logic_file.exists():
                with open(business_logic_file, 'r', encoding='utf-8') as f:
                    business_data = json.load(f)
                
                self.business_logic_texts = business_data.get("business_logic_texts", [])
                self.business_logic_metadata = business_data.get("business_logic_metadata", [])
                self.is_business_logic_loaded = business_data.get("is_business_logic_loaded", False)
                
                upload_time_str = business_data.get("business_logic_upload_time")
                if upload_time_str:
                    self.business_logic_upload_time = datetime.fromisoformat(upload_time_str)
            
            combined_file = self._get_combined_texts_file()
            if combined_file.exists():
                with open(combined_file, 'rb') as f:
                    combined_data = pickle.load(f)
                
                self.combined_texts = combined_data.get("combined_texts", [])
                self.text_types = combined_data.get("text_types", [])
                self.text_identifiers = combined_data.get("text_identifiers", [])
                self.schema_texts = combined_data.get("schema_texts", [])
                self.table_names = combined_data.get("table_names", [])
            
            index_file = self._get_index_file()
            if index_file.exists():
                self.index = faiss.read_index(str(index_file))
            
            if self.is_metadata_loaded or self.is_business_logic_loaded:
                logger.info(f"Knowledge base loaded from disk: {len(self.table_names)} tables, {len(self.business_logic_texts)} business logic entries")
            
        except Exception as e:
            logger.warning(f"Failed to load knowledge base from disk: {e}")
            self._reset_state()

    def _reset_state(self) -> None:
        self.index = None
        self.schema_texts = []
        self.table_names = []
        self.table_metadata = {}
        self.business_logic_texts = []
        self.business_logic_metadata = []
        self.combined_texts = []
        self.text_types = []
        self.text_identifiers = []
        self.is_metadata_loaded = False
        self.is_business_logic_loaded = False
        self.metadata_upload_time = None
        self.business_logic_upload_time = None

    def process_business_logic_file(self, file_content: str, file_name: str = "business_logic.txt") -> Dict[str, Any]:
        try:
            logger.info(f"Processing business logic file: {file_name}")
            
            chunks = self._split_business_logic_content(file_content)
            
            if not chunks:
                raise ValueError("No meaningful content found in business logic file")
            
            self.business_logic_texts = []
            self.business_logic_metadata = []
            
            processed_chunks = 0
            for i, chunk in enumerate(chunks):
                try:
                    chunk_metadata = {
                        "chunk_id": f"business_logic_{i}",
                        "source_file": file_name,
                        "content_type": "business_logic",
                        "chunk_index": i,
                        "processed_at": datetime.utcnow().isoformat()
                    }
                    
                    self.business_logic_texts.append(chunk)
                    self.business_logic_metadata.append(chunk_metadata)
                    processed_chunks += 1
                    
                except Exception as e:
                    logger.warning(f"Error processing business logic chunk {i}: {e}")
                    continue
            
            if not self.business_logic_texts:
                raise ValueError("No valid business logic chunks found")
            
            self.is_business_logic_loaded = True
            self.business_logic_upload_time = datetime.utcnow()
            
            self._rebuild_combined_index()
            self._save_to_disk()
            
            logger.info(f"Successfully processed business logic: {processed_chunks} chunks from {file_name}")
            
            return {
                "success": True,
                "processed_chunks": processed_chunks,
                "total_chunks": len(chunks),
                "upload_time": self.business_logic_upload_time.isoformat(),
                "message": f"Business logic processed successfully. {processed_chunks} chunks indexed and saved to disk."
            }
            
        except Exception as e:
            logger.error(f"Error processing business logic: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to process business logic file"
            }

    def _split_business_logic_content(self, content: str) -> List[str]:
        chunks = []
        
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        
        for paragraph in paragraphs:
            if len(paragraph) < 50:
                continue
            
            if len(paragraph) > 1000:
                sentences = [s.strip() for s in paragraph.split('.') if s.strip()]
                current_chunk = ""
                
                for sentence in sentences:
                    if len(current_chunk + sentence) < 800:
                        current_chunk += sentence + ". "
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = sentence + ". "
                
                if current_chunk:
                    chunks.append(current_chunk.strip())
            else:
                chunks.append(paragraph)
        
        if not chunks and content.strip():
            chunk_size = 500
            overlap = 50
            words = content.split()
            
            for i in range(0, len(words), chunk_size - overlap):
                chunk_words = words[i:i + chunk_size]
                chunk = " ".join(chunk_words)
                if len(chunk.strip()) > 50:
                    chunks.append(chunk.strip())
        
        return chunks

    def _rebuild_combined_index(self) -> None:
        logger.info("Rebuilding combined vector index...")
        
        self.combined_texts = []
        self.text_types = []
        self.text_identifiers = []
        
        for i, (table_name, schema_text) in enumerate(zip(self.table_names, self.schema_texts)):
            self.combined_texts.append(schema_text)
            self.text_types.append("schema")
            self.text_identifiers.append(table_name)
        
        for i, (business_text, metadata) in enumerate(zip(self.business_logic_texts, self.business_logic_metadata)):
            enhanced_business_text = f"Business Logic: {business_text}"
            self.combined_texts.append(enhanced_business_text)
            self.text_types.append("business_logic")
            self.text_identifiers.append(metadata["chunk_id"])
        
        if not self.combined_texts:
            logger.warning("No texts available for combined index")
            return
        
        logger.info(f"Creating embeddings for {len(self.combined_texts)} texts (schema + business logic)...")
        embeddings = self.model.encode(self.combined_texts)
        dim = embeddings.shape[1]
        
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(np.array(embeddings, dtype="float32"))
        
        logger.info(f"Combined vector index rebuilt with {len(self.combined_texts)} texts")

    def process_metadata(self, metadata_json: Dict[str, Any]) -> Dict[str, Any]:
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
            
            self.schema_texts = enriched_texts
            self.table_names = table_names
            self.is_metadata_loaded = True
            self.metadata_upload_time = datetime.utcnow()
            
            self._rebuild_combined_index()
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
        if self.index is None:
            self.build_from_database()
            if self.index is None:
                return []
        
        vector = self.model.encode([query])
        distances, indices = self.index.search(np.array(vector, dtype="float32"), k)
        
        results = []
        for idx in indices[0]:
            if idx < len(self.combined_texts) if self.combined_texts else len(self.table_names):
                if self.combined_texts:
                    text_type = self.text_types[idx]
                    identifier = self.text_identifiers[idx]
                    content = self.combined_texts[idx]
                    
                    if text_type == "schema":
                        metadata = self.table_metadata.get(identifier, {})
                        results.append((identifier, content, metadata))
                    elif text_type == "business_logic":
                        business_metadata = None
                        for meta in self.business_logic_metadata:
                            if meta["chunk_id"] == identifier:
                                business_metadata = meta
                                break
                        
                        if business_metadata is None:
                            business_metadata = {"type": "business_logic", "chunk_id": identifier}
                        
                        results.append((identifier, content, business_metadata))
                else:
                    table_name = self.table_names[idx]
                    schema_text = self.schema_texts[idx]
                    metadata = self.table_metadata.get(table_name, {})
                    results.append((table_name, schema_text, metadata))
        
        return results

    def get_table_details(self, table_name: str) -> Optional[Dict[str, Any]]:
        return self.table_metadata.get(table_name)

    def get_status(self) -> Dict[str, Any]:
        return {
            "metadata_loaded": self.is_metadata_loaded,
            "business_logic_loaded": self.is_business_logic_loaded,
            "upload_time": self.metadata_upload_time.isoformat() if self.metadata_upload_time else None,
            "business_logic_upload_time": self.business_logic_upload_time.isoformat() if self.business_logic_upload_time else None,
            "total_tables": len(self.table_names),
            "total_business_logic_chunks": len(self.business_logic_texts),
            "index_built": self.index is not None,
            "storage_path": str(self.storage_path),
            "files_exist": {
                "metadata": self._get_metadata_file().exists(),
                "business_logic": self._get_business_logic_file().exists(),
                "vector_index": self._get_index_file().exists(),
                "combined_texts": self._get_combined_texts_file().exists()
            }
        }

    def clear_all(self) -> None:
        self._reset_state()
        
        try:
            for file_path in [
                self._get_metadata_file(),
                self._get_business_logic_file(),
                self._get_index_file(),
                self._get_combined_texts_file(),
                self._get_text_metadata_file()
            ]:
                if file_path.exists():
                    os.remove(file_path)
            
            logger.info("Knowledge base cleared completely and files removed")
        except Exception as e:
            logger.error(f"Error removing files during clear: {e}")

    def rebuild_index(self) -> None:
        if not self.is_metadata_loaded and not self.is_business_logic_loaded:
            raise ValueError("No metadata or business logic loaded to rebuild index from")
        
        logger.info("Rebuilding vector index...")
        self._rebuild_combined_index()
        self._save_to_disk()
        logger.info("Vector index rebuilt and saved")