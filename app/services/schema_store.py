import logging
from typing import List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

from .database import DatabaseService

logger = logging.getLogger(__name__)


class SchemaVectorStore:
    """Embeds table schemas and provides similarity search."""

    def __init__(self, database_service: DatabaseService, model_name: str = "all-MiniLM-L6-v2"):
        self.database_service = database_service
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.schema_texts: List[str] = []
        self.table_names: List[str] = []

    def build(self) -> None:
        """Embed all table schemas and build the FAISS index."""
        table_names = self.database_service.get_table_names()
        schemas = []
        for name in table_names:
            try:
                info = self.database_service.describe_table(name)
            except Exception as e:
                logger.warning(f"Failed to get schema for {name}: {e}")
                info = ""
            schemas.append(f"Table {name}: {info}")
            self.table_names.append(name)
        if not schemas:
            logger.warning("No schemas retrieved for embedding")
            return
        embeddings = self.model.encode(schemas)
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(np.array(embeddings, dtype="float32"))
        self.schema_texts = schemas
        logger.info("Schema vector store built with %d tables", len(schemas))

    def search(self, query: str, k: int = 5) -> List[Tuple[str, str]]:
        """Return the most relevant table schemas for a query."""
        if self.index is None:
            return []
        vector = self.model.encode([query])
        distances, indices = self.index.search(np.array(vector, dtype="float32"), k)
        results = []
        for idx in indices[0]:
            if idx < len(self.table_names):
                results.append((self.table_names[idx], self.schema_texts[idx]))
        return results
