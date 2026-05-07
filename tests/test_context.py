"""
Tests for AI context management and chunking strategies.
"""

import pytest
from modules.ai.context import (
    AIContextManager, ContextWindow, TextChunk, ChunkingStrategy
)


class TestTextChunk:
    """Test TextChunk data structure."""
    
    def test_text_chunk_creation(self):
        """Test creating a text chunk."""
        chunk = TextChunk(
            content="Sample content",
            start_position=0,
            end_position=14,
            chunk_type="sentence",
            metadata={"source": "test"}
        )
        
        assert chunk.content == "Sample content"
        assert chunk.start_position == 0
        assert chunk.end_position == 14
        assert chunk.chunk_type == "sentence"
        assert chunk.metadata["source"] == "test"
    
    def test_text_chunk_with_embedding(self):
        """Test text chunk with embedding vector."""
        chunk = TextChunk(
            content="Text with embedding",
            start_position=0,
            end_position=19,
            chunk_type="paragraph",
            embedding=[0.1, 0.2, 0.3]
        )
        
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 3


class TestContextWindow:
    """Test context window management."""
    
    def test_context_window_creation(self):
        """Test creating a context window."""
        window = ContextWindow(max_tokens=1000, reserved_tokens=100)
        
        assert window.max_tokens == 1000
        assert window.reserved_tokens == 100
        assert window.available_tokens == 900
        assert len(window.chunks) == 0
    
    def test_available_tokens_calculation(self):
        """Test available tokens calculation."""
        window = ContextWindow(max_tokens=1000, reserved_tokens=200)
        
        assert window.available_tokens == 800
        
        chunk = TextChunk("short", 0, 5, "test")
        window.add_chunk(chunk)
        
        # After adding chunk, available tokens decrease
        assert window.available_tokens < 800
    
    def test_add_chunk_success(self):
        """Test adding chunk to context window."""
        window = ContextWindow(max_tokens=1000, reserved_tokens=100)
        
        chunk = TextChunk("Sample text", 0, 11, "sentence")
        result = window.add_chunk(chunk)
        
        assert result is True
        assert len(window.chunks) == 1
        assert window.chunks[0].content == "Sample text"
    
    def test_add_chunk_exceeds_limit(self):
        """Test adding chunk when limit exceeded."""
        window = ContextWindow(max_tokens=100, reserved_tokens=50)
        
        # Large chunk that exceeds available tokens
        large_chunk = TextChunk("A" * 1000, 0, 1000, "test")
        result = window.add_chunk(large_chunk)
        
        assert result is False
        assert len(window.chunks) == 0
    
    def test_can_add_chunk(self):
        """Test checking if chunk can be added."""
        window = ContextWindow(max_tokens=100, reserved_tokens=20)
        
        small_chunk = TextChunk("small", 0, 5, "test")
        large_chunk = TextChunk("A" * 1000, 0, 1000, "test")
        
        assert window.can_add_chunk(small_chunk) is True
        assert window.can_add_chunk(large_chunk) is False
    
    def test_remove_chunk(self):
        """Test removing chunk from context."""
        window = ContextWindow(max_tokens=1000, reserved_tokens=100)
        
        chunk1 = TextChunk("First", 0, 5, "test")
        chunk2 = TextChunk("Second", 6, 12, "test")
        
        window.add_chunk(chunk1)
        window.add_chunk(chunk2)
        
        assert len(window.chunks) == 2
        
        removed = window.remove_chunk(0)
        assert removed is not None
        assert removed.content == "First"
        assert len(window.chunks) == 1
    
    def test_remove_invalid_index(self):
        """Test removing chunk with invalid index."""
        window = ContextWindow(max_tokens=1000, reserved_tokens=100)
        
        removed = window.remove_chunk(0)
        assert removed is None
        
        removed = window.remove_chunk(999)
        assert removed is None
    
    def test_clear_context(self):
        """Test clearing all chunks from context."""
        window = ContextWindow(max_tokens=1000, reserved_tokens=100)
        
        for i in range(5):
            chunk = TextChunk(f"Chunk {i}", i*10, i*10+10, "test")
            window.add_chunk(chunk)
        
        assert len(window.chunks) == 5
        
        window.clear()
        
        assert len(window.chunks) == 0
        assert window.total_tokens == 0
        assert window.available_tokens == 900
    
    def test_get_content(self):
        """Test retrieving combined content."""
        window = ContextWindow(max_tokens=1000, reserved_tokens=100)
        
        window.add_chunk(TextChunk("First part", 0, 10, "test"))
        window.add_chunk(TextChunk("Second part", 11, 22, "test"))
        
        content = window.get_content()
        
        assert "First part" in content
        assert "Second part" in content
        assert "\n\n" in content  # Default separator


class TestChunkingStrategies:
    """Test different text chunking strategies."""
    
    def test_chunking_by_sentence(self):
        """Test sentence-based chunking."""
        manager = AIContextManager()
        
        text = "First sentence. Second sentence! Third sentence?"
        chunks = manager._chunk_by_sentence(text)
        
        assert len(chunks) == 3
        assert "First sentence" in chunks[0].content
        assert "Second sentence" in chunks[1].content
        assert "Third sentence" in chunks[2].content
    
    def test_chunking_by_paragraph(self):
        """Test paragraph-based chunking."""
        manager = AIContextManager()
        
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        chunks = manager._chunk_by_paragraph(text)
        
        assert len(chunks) == 3
        assert chunks[0].content == "First paragraph."
        assert chunks[1].content == "Second paragraph."
        assert chunks[2].content == "Third paragraph."
    
    def test_chunking_by_heading(self):
        """Test heading-based section chunking."""
        manager = AIContextManager()
        
        text = """# Introduction
        This is the introduction section.
        
        # Body
        This is the body section.
        
        # Conclusion
        This is the conclusion."""
        
        chunks = manager._chunk_by_heading(text)
        
        assert len(chunks) >= 3
    
    def test_chunking_by_token(self):
        """Test token-based chunking."""
        manager = AIContextManager()
        
        words = " ".join(["word"] * 100)
        chunks = manager._chunk_by_token(words, chunk_size=10)
        
        assert len(chunks) == 10
        for chunk in chunks:
            word_count = len(chunk.content.split())
            assert word_count == 10
    
    def test_chunking_preserves_positions(self):
        """Test that chunking preserves position metadata."""
        manager = AIContextManager()
        
        text = "First part. Second part. Third part."
        chunks = manager._chunk_by_sentence(text)
        
        for chunk in chunks:
            assert chunk.start_position >= 0
            assert chunk.end_position > chunk.start_position
    
    def test_semantic_chunking_fallback(self):
        """Test semantic chunking falls back to paragraph."""
        manager = AIContextManager()
        
        text = "Paragraph one.\n\nParagraph two."
        chunks = manager._chunk_semantically(text)
        
        # Should fall back to paragraph chunking
        assert len(chunks) == 2


class TestAIContextManager:
    """Test AIContextManager functionality."""
    
    def test_context_manager_initialization(self):
        """Test initializing context manager."""
        manager = AIContextManager(max_context_tokens=2048)
        
        assert manager.max_context_tokens == 2048
        assert len(manager.documents) == 0
        assert len(manager.conversations) == 0
    
    def test_add_document(self):
        """Test adding document with chunking."""
        manager = AIContextManager()
        
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        chunks = manager.add_document("doc1", text, ChunkingStrategy.PARAGRAPH)
        
        assert len(chunks) == 3
        assert "doc1" in manager.documents
        assert len(manager.documents["doc1"]) == 3
    
    def test_add_document_different_strategies(self):
        """Test adding document with different chunking strategies."""
        manager = AIContextManager()
        text = "First sentence. Second sentence! Third sentence?"
        
        sent_chunks = manager.add_document("doc_sent", text, ChunkingStrategy.SENTENCE)
        assert len(sent_chunks) >= 2
        
        para_chunks = manager.add_document("doc_para", text, ChunkingStrategy.PARAGRAPH)
        assert len(para_chunks) >= 1
    
    def test_get_document_chunks(self):
        """Test retrieving document chunks."""
        manager = AIContextManager()
        
        text = "Content 1.\n\nContent 2."
        manager.add_document("test_doc", text, ChunkingStrategy.PARAGRAPH)
        
        chunks = manager.get_document_chunks("test_doc")
        assert len(chunks) == 2
    
    def test_get_nonexistent_document_chunks(self):
        """Test retrieving chunks for nonexistent document."""
        manager = AIContextManager()
        
        chunks = manager.get_document_chunks("nonexistent")
        assert chunks == []
    
    def test_create_context_window(self):
        """Test creating context window for conversation."""
        manager = AIContextManager()
        
        window = manager.create_context_window("conv1")
        
        assert window is not None
        assert "conv1" in manager.conversations
        assert window.available_tokens > 0
    
    def test_get_context_window(self):
        """Test retrieving context window."""
        manager = AIContextManager()
        
        window = manager.create_context_window("conv1")
        retrieved = manager.get_context_window("conv1")
        
        assert retrieved is window
    
    def test_get_nonexistent_context_window(self):
        """Test retrieving nonexistent context window."""
        manager = AIContextManager()
        
        window = manager.get_context_window("nonexistent")
        assert window is None
    
    def test_optimize_context_for_query(self):
        """Test optimizing context for query."""
        manager = AIContextManager()
        
        # Add document
        text = """Islamic prayer is fundamental. 
        Prayer involves physical and spiritual aspects.
        Salah is performed five times daily.
        Muslims face Mecca during prayer."""
        
        manager.add_document("doc1", text, ChunkingStrategy.PARAGRAPH)
        
        # Create context window
        window = manager.create_context_window("conv1")
        
        # Optimize for prayer-related query
        result = manager.optimize_context_for_query(
            "doc1", 
            "What is prayer in Islam?",
            window,
            max_chunks=3
        )
        
        assert result is True
        assert len(window.chunks) > 0
    
    def test_optimize_context_no_matching_chunks(self):
        """Test optimizing context when no relevant chunks found."""
        manager = AIContextManager()
        
        text = "Some unrelated content."
        manager.add_document("doc1", text, ChunkingStrategy.PARAGRAPH)
        
        window = manager.create_context_window("conv1")
        
        result = manager.optimize_context_for_query(
            "doc1",
            "Query about completely different topic that won't match",
            window
        )
        
        # Result depends on keyword matching
        assert isinstance(result, bool)
    
    def test_summarize_for_context_short_text(self):
        """Test summarizing short text."""
        manager = AIContextManager()
        
        text = "This is short."
        summary = manager.summarize_for_context(text, max_length=100)
        
        # Short text should not be truncated
        assert summary == text
    
    def test_summarize_for_context_long_text(self):
        """Test summarizing long text."""
        manager = AIContextManager()
        
        text = " ".join(["word"] * 500)
        summary = manager.summarize_for_context(text, max_length=100)
        
        # Summary should be shorter or equal to max_length
        assert len(summary) <= 100
    
    def test_cleanup_old_contexts(self):
        """Test cleaning up old contexts."""
        manager = AIContextManager()
        
        manager.create_context_window("conv1")
        manager.create_context_window("conv2")
        
        # Cleanup (returns 0 since no timestamp tracking)
        cleaned = manager.cleanup_old_contexts(max_age_hours=24)
        
        assert isinstance(cleaned, int)


class TestContextIntegration:
    """Integration tests for context management."""
    
    def test_full_document_to_context_workflow(self):
        """Test complete workflow from document to context."""
        manager = AIContextManager(max_context_tokens=1000)
        
        # Add document
        text = """Religious texts have deep significance.
        The Quran is central to Islamic faith.
        Daily prayers strengthen spiritual connection.
        Community gatherings reinforce bonds."""
        
        doc_chunks = manager.add_document("sacred", text, ChunkingStrategy.PARAGRAPH)
        assert len(doc_chunks) > 0
        
        # Create conversation context
        window = manager.create_context_window("discussion")
        
        # Optimize for query
        manager.optimize_context_for_query(
            "sacred",
            "What are the key religious practices?",
            window,
            max_chunks=2
        )
        
        # Verify context built successfully
        assert len(window.chunks) > 0
        assert window.total_tokens > 0
        assert window.available_tokens < window.max_tokens
    
    def test_multiple_documents_in_context(self):
        """Test managing multiple documents in a single context."""
        manager = AIContextManager()
        
        doc1 = "Islamic history is rich. Prophet Muhammad established Islam."
        doc2 = "The Five Pillars form the foundation. They guide Muslim life."
        
        manager.add_document("history", doc1, ChunkingStrategy.PARAGRAPH)
        manager.add_document("pillars", doc2, ChunkingStrategy.PARAGRAPH)
        
        window = manager.create_context_window("multi")
        
        # Add chunks from both documents
        hist_chunks = manager.get_document_chunks("history")
        pill_chunks = manager.get_document_chunks("pillars")
        
        for chunk in hist_chunks[:1]:
            window.add_chunk(chunk)
        
        for chunk in pill_chunks[:1]:
            window.add_chunk(chunk)
        
        assert len(window.chunks) == 2
        content = window.get_content()
        assert "history" in content or "Prophet" in content
        assert "Pillars" in content or "foundation" in content
