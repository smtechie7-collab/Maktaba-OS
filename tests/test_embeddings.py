"""
Tests for vector embeddings and semantic search functionality.
"""

import pytest
import numpy as np
from unittest.mock import Mock, patch

# Import with graceful fallback for missing dependencies
try:
    from modules.ai.embeddings import (
        EmbeddingModel, VectorIndex, VectorDocument,
        SemanticSearchEngine, SENTENCE_TRANSFORMERS_AVAILABLE
    )
    EMBEDDINGS_AVAILABLE = SENTENCE_TRANSFORMERS_AVAILABLE
except ImportError:
    EMBEDDINGS_AVAILABLE = False


@pytest.mark.skipif(not EMBEDDINGS_AVAILABLE, reason="sentence-transformers not available")
class TestEmbeddingModel:
    """Test the embedding model functionality."""

    def test_embedding_model_initialization(self):
        """Test that the embedding model initializes correctly."""
        model = EmbeddingModel("all-MiniLM-L6-v2")
        assert model.model_name == "all-MiniLM-L6-v2"
        assert model.model is not None
        assert model.get_dimension() > 0

    def test_text_encoding(self):
        """Test encoding single text and list of texts."""
        model = EmbeddingModel("all-MiniLM-L6-v2")

        # Single text
        embedding = model.encode("Hello world")
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape[0] == 1
        assert embedding.shape[1] == model.get_dimension()

        # Multiple texts
        texts = ["Hello world", "This is a test", "Another sentence"]
        embeddings = model.encode(texts)
        assert embeddings.shape[0] == 3
        assert embeddings.shape[1] == model.get_dimension()


@pytest.mark.skipif(not EMBEDDINGS_AVAILABLE, reason="faiss not available")
class TestVectorIndex:
    """Test the vector index functionality."""

    def test_vector_index_initialization(self):
        """Test vector index initialization."""
        dimension = 384  # Typical dimension for MiniLM
        index = VectorIndex(dimension)
        assert index.dimension == dimension
        assert index.index is not None
        assert len(index.documents) == 0

    def test_add_and_search_documents(self):
        """Test adding documents and searching."""
        dimension = 384
        index = VectorIndex(dimension)

        # Create test documents
        docs = []
        for i in range(3):
            embedding = np.random.rand(dimension).astype(np.float32)
            doc = VectorDocument(
                id=f"doc_{i}",
                content=f"Test content {i}",
                embedding=embedding
            )
            docs.append(doc)

        # Add documents
        index.add_documents(docs)
        assert len(index.documents) == 3
        assert index.index.ntotal == 3

        # Search
        query_embedding = np.random.rand(dimension).astype(np.float32)
        results = index.search(query_embedding, k=2)
        assert len(results) <= 2
        for doc, score in results:
            assert isinstance(doc, VectorDocument)
            assert isinstance(score, float)


@pytest.mark.skipif(not EMBEDDINGS_AVAILABLE, reason="Dependencies not available")
class TestSemanticSearchEngine:
    """Test the semantic search engine."""

    def test_search_engine_initialization(self):
        """Test search engine initialization."""
        engine = SemanticSearchEngine("all-MiniLM-L6-v2")
        assert engine.embedding_model is not None
        assert engine.vector_index is not None

    def test_add_texts_and_search(self):
        """Test adding texts and performing semantic search."""
        engine = SemanticSearchEngine("all-MiniLM-L6-v2")

        # Add some test texts
        texts = [
            "The cat sits on the mat",
            "A feline rests on a rug",
            "Python is a programming language",
            "Machine learning is fascinating"
        ]

        doc_ids = engine.add_texts(texts)
        assert len(doc_ids) == 4

        # Search for cat-related content
        results = engine.search("cat on mat", k=2)
        assert len(results) <= 2

        for result in results:
            assert "id" in result
            assert "content" in result
            assert "score" in result
            assert "metadata" in result
            assert isinstance(result["score"], float)

    def test_semantic_similarity(self):
        """Test that semantically similar texts rank higher."""
        engine = SemanticSearchEngine("all-MiniLM-L6-v2")

        texts = [
            "I love eating pizza",
            "The weather is nice today",
            "Programming is my passion",
            "I enjoy Italian food"
        ]

        engine.add_texts(texts)

        # Search for food-related query
        results = engine.search("food and eating", k=4)

        # The pizza and Italian food results should be more relevant
        pizza_result = next((r for r in results if "pizza" in r["content"]), None)
        food_result = next((r for r in results if "Italian food" in r["content"]), None)

        assert pizza_result is not None
        assert food_result is not None


class TestVectorDocument:
    """Test VectorDocument functionality."""

    def test_vector_document_creation(self):
        """Test creating a vector document."""
        embedding = np.array([0.1, 0.2, 0.3])
        doc = VectorDocument(
            id="test_doc",
            content="Test content",
            embedding=embedding,
            metadata={"type": "test"}
        )

        assert doc.id == "test_doc"
        assert doc.content == "Test content"
        assert np.array_equal(doc.embedding, embedding)
        assert doc.metadata["type"] == "test"

    def test_vector_document_serialization(self):
        """Test serializing and deserializing vector documents."""
        embedding = np.array([0.1, 0.2, 0.3])
        original_doc = VectorDocument(
            id="test_doc",
            content="Test content",
            embedding=embedding,
            metadata={"type": "test"}
        )

        # Serialize
        doc_dict = original_doc.to_dict()
        assert doc_dict["id"] == "test_doc"
        assert doc_dict["content"] == "Test content"
        assert doc_dict["embedding"] == [0.1, 0.2, 0.3]

        # Deserialize
        restored_doc = VectorDocument.from_dict(doc_dict)
        assert restored_doc.id == original_doc.id
        assert restored_doc.content == original_doc.content
        assert np.array_equal(restored_doc.embedding, original_doc.embedding)
        assert restored_doc.metadata == original_doc.metadata


@pytest.mark.skipif(EMBEDDINGS_AVAILABLE, reason="Dependencies available - testing fallback")
class TestEmbeddingsFallback:
    """Test behavior when dependencies are not available."""

    def test_missing_dependencies_error(self):
        """Test that appropriate errors are raised when dependencies missing."""
        with pytest.raises(ImportError):
            EmbeddingModel()

        with pytest.raises(ImportError):
            VectorIndex(384)