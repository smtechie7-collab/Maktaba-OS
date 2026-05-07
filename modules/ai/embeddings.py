"""
Vector Embeddings and Semantic Search for Maktaba-OS.

This module provides:
- Text vectorization using sentence transformers
- Semantic similarity search
- Vector database operations
- Efficient indexing and retrieval
"""

from typing import List, Dict, Optional, Any, Tuple, Union
import numpy as np
import logging
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path

# Optional imports - gracefully handle missing dependencies
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    import faiss
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SentenceTransformer = None
    cosine_similarity = None
    faiss = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False

from .context import TextChunk

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """Represents a document with its vector embedding."""
    id: str
    content: str
    embedding: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "embedding": self.embedding.tolist() if self.embedding is not None else None,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VectorDocument':
        """Create from dictionary."""
        return cls(
            id=data["id"],
            content=data["content"],
            embedding=np.array(data["embedding"]) if data["embedding"] else None,
            metadata=data["metadata"],
            created_at=datetime.fromisoformat(data["created_at"])
        )


class EmbeddingModel:
    """
    Wrapper for sentence transformer models with caching and optimization.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize the embedding model.

        Args:
            model_name: Name of the sentence transformer model to use
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not available. Install with: pip install sentence-transformers"
            )

        self.model_name = model_name
        self.model = None
        self._load_model()

    def _load_model(self) -> None:
        """Load the sentence transformer model."""
        try:
            self.model = SentenceTransformer(self.model_name)
            logger.info(f"Loaded embedding model: {self.model_name}")
        except Exception as e:
            logger.error(f"Failed to load model {self.model_name}: {e}")
            raise

    def encode(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """
        Encode text(s) into vector embeddings.

        Args:
            texts: Single text or list of texts to encode
            batch_size: Batch size for processing

        Returns:
            Numpy array of embeddings
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        if isinstance(texts, str):
            texts = [texts]

        try:
            embeddings = self.model.encode(texts, batch_size=batch_size, convert_to_numpy=True)
            return embeddings
        except Exception as e:
            logger.error(f"Failed to encode texts: {e}")
            raise

    def get_dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        return self.model.get_sentence_embedding_dimension() if self.model else 0


class VectorIndex:
    """
    FAISS-based vector index for efficient similarity search.
    """

    def __init__(self, dimension: int, index_type: str = "IndexFlatIP"):
        """
        Initialize the vector index.

        Args:
            dimension: Dimension of the vectors
            index_type: Type of FAISS index to use
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("faiss not available. Install with: pip install faiss-cpu")

        self.dimension = dimension
        self.index_type = index_type
        self.index = None
        self.documents: List[VectorDocument] = []
        self.id_to_idx: Dict[str, int] = {}

        self._create_index()

    def _create_index(self) -> None:
        """Create the FAISS index."""
        if self.index_type == "IndexFlatIP":
            # Inner product (cosine similarity with normalized vectors)
            self.index = faiss.IndexFlatIP(self.dimension)
        elif self.index_type == "IndexIVFFlat":
            # IVF with flat quantization
            nlist = min(100, max(4, len(self.documents) // 39))  # Rule of thumb
            quantizer = faiss.IndexFlatIP(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, nlist)
        else:
            # Default to flat index
            self.index = faiss.IndexFlatIP(self.dimension)

    def add_documents(self, documents: List[VectorDocument]) -> None:
        """
        Add documents to the index.

        Args:
            documents: List of documents to add
        """
        if not documents:
            return

        # Extract embeddings
        embeddings = np.array([doc.embedding for doc in documents])

        # Normalize for cosine similarity
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1  # Avoid division by zero
        embeddings = embeddings / norms

        # Add to FAISS index
        self.index.add(embeddings.astype(np.float32))

        # Store documents and mapping
        start_idx = len(self.documents)
        self.documents.extend(documents)
        for i, doc in enumerate(documents):
            self.id_to_idx[doc.id] = start_idx + i

        logger.info(f"Added {len(documents)} documents to index")

    def search(self, query_embedding: np.ndarray, k: int = 5) -> List[Tuple[VectorDocument, float]]:
        """
        Search for similar documents.

        Args:
            query_embedding: Query embedding vector
            k: Number of results to return

        Returns:
            List of (document, similarity_score) tuples
        """
        if self.index.ntotal == 0:
            return []

        # Normalize query embedding
        norm = np.linalg.norm(query_embedding)
        if norm > 0:
            query_embedding = query_embedding / norm

        # Search
        query_embedding = query_embedding.reshape(1, -1).astype(np.float32)
        scores, indices = self.index.search(query_embedding, min(k, self.index.ntotal))

        # Convert to document-score pairs
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx != -1:  # Valid result
                doc = self.documents[idx]
                results.append((doc, float(score)))

        return results

    def remove_document(self, doc_id: str) -> bool:
        """
        Remove a document from the index.

        Args:
            doc_id: ID of the document to remove

        Returns:
            True if document was removed, False otherwise
        """
        if doc_id not in self.id_to_idx:
            return False

        # Note: FAISS doesn't support efficient deletion, so we mark as deleted
        # In a production system, you'd rebuild the index periodically
        idx = self.id_to_idx[doc_id]
        if idx < len(self.documents):
            # Mark document as deleted by setting embedding to zeros
            self.documents[idx].metadata["deleted"] = True
            logger.info(f"Marked document {doc_id} as deleted")
            return True

        return False

    def save(self, filepath: str) -> None:
        """
        Save the index to disk.

        Args:
            filepath: Path to save the index
        """
        data = {
            "dimension": self.dimension,
            "index_type": self.index_type,
            "documents": [doc.to_dict() for doc in self.documents if not doc.metadata.get("deleted", False)]
        }

        # Save FAISS index
        index_path = f"{filepath}.faiss"
        faiss.write_index(self.index, index_path)

        # Save metadata
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved vector index to {filepath}")

    def load(self, filepath: str) -> None:
        """
        Load the index from disk.

        Args:
            filepath: Path to load the index from
        """
        # Load metadata
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.dimension = data["dimension"]
        self.index_type = data["index_type"]
        self.documents = [VectorDocument.from_dict(doc_data) for doc_data in data["documents"]]

        # Rebuild ID mapping
        self.id_to_idx = {doc.id: i for i, doc in enumerate(self.documents)}

        # Load FAISS index
        index_path = f"{filepath}.faiss"
        self.index = faiss.read_index(index_path)

        logger.info(f"Loaded vector index from {filepath}")


class SemanticSearchEngine:
    """
    High-level semantic search engine combining embedding and indexing.
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        index_type: str = "IndexFlatIP",
        cache_dir: Optional[str] = None
    ):
        """
        Initialize the semantic search engine.

        Args:
            model_name: Name of the embedding model
            index_type: Type of vector index
            cache_dir: Directory for caching models and indices
        """
        self.model_name = model_name
        self.index_type = index_type
        self.cache_dir = Path(cache_dir) if cache_dir else None

        self.embedding_model: Optional[EmbeddingModel] = None
        self.vector_index: Optional[VectorIndex] = None

        self._initialize_components()

    def _initialize_components(self) -> None:
        """Initialize embedding model and vector index."""
        try:
            self.embedding_model = EmbeddingModel(self.model_name)
            dimension = self.embedding_model.get_dimension()
            self.vector_index = VectorIndex(dimension, self.index_type)
            logger.info("Semantic search engine initialized")
        except Exception as e:
            logger.error(f"Failed to initialize semantic search engine: {e}")
            raise

    def add_texts(self, texts: Union[str, List[str]], metadata: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """
        Add texts to the search index.

        Args:
            texts: Single text or list of texts to add
            metadata: Optional metadata for each text

        Returns:
            List of document IDs
        """
        if isinstance(texts, str):
            texts = [texts]

        if metadata is None:
            metadata = [{}] * len(texts)
        elif len(metadata) != len(texts):
            raise ValueError("Metadata list must match texts list length")

        # Generate embeddings
        embeddings = self.embedding_model.encode(texts)

        # Create documents
        documents = []
        doc_ids = []
        for i, (text, embedding, meta) in enumerate(zip(texts, embeddings, metadata)):
            doc_id = f"doc_{datetime.now().timestamp()}_{i}"
            doc = VectorDocument(
                id=doc_id,
                content=text,
                embedding=embedding,
                metadata=meta
            )
            documents.append(doc)
            doc_ids.append(doc_id)

        # Add to index
        self.vector_index.add_documents(documents)

        return doc_ids

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for semantically similar texts.

        Args:
            query: Search query
            k: Number of results to return

        Returns:
            List of search results with scores and metadata
        """
        # Encode query
        query_embedding = self.embedding_model.encode(query)

        # Search index
        results = self.vector_index.search(query_embedding, k)

        # Format results
        formatted_results = []
        for doc, score in results:
            formatted_results.append({
                "id": doc.id,
                "content": doc.content,
                "score": score,
                "metadata": doc.metadata
            })

        return formatted_results

    def save_index(self, filepath: str) -> None:
        """
        Save the search index to disk.

        Args:
            filepath: Path to save the index
        """
        self.vector_index.save(filepath)

    def load_index(self, filepath: str) -> None:
        """
        Load the search index from disk.

        Args:
            filepath: Path to load the index from
        """
        self.vector_index.load(filepath)
        # Reinitialize embedding model if needed
        if self.embedding_model is None:
            self.embedding_model = EmbeddingModel(self.model_name)


# Global instance for easy access
semantic_search_engine: Optional[SemanticSearchEngine] = None


def initialize_semantic_search(
    model_name: str = "all-MiniLM-L6-v2",
    cache_dir: Optional[str] = None
) -> SemanticSearchEngine:
    """
    Initialize the global semantic search engine.

    Args:
        model_name: Name of the embedding model
        cache_dir: Cache directory for models

    Returns:
        The initialized search engine
    """
    global semantic_search_engine
    if semantic_search_engine is None:
        semantic_search_engine = SemanticSearchEngine(
            model_name=model_name,
            cache_dir=cache_dir
        )
    return semantic_search_engine


def get_semantic_search_engine() -> Optional[SemanticSearchEngine]:
    """Get the global semantic search engine instance."""
    return semantic_search_engine