"""
AI Context Management for Large Documents.

This module handles:
- Context window management for large documents
- Intelligent text chunking and summarization
- Memory optimization for long conversations
- Context-aware processing
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import re
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ChunkingStrategy(Enum):
    """Strategies for splitting text into chunks."""
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    HEADING = "heading"
    TOKEN = "token"
    SEMANTIC = "semantic"


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata."""
    content: str
    start_position: int
    end_position: int
    chunk_type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None
    summary: Optional[str] = None


@dataclass
class ContextWindow:
    """Represents a context window for AI processing."""
    chunks: List[TextChunk] = field(default_factory=list)
    total_tokens: int = 0
    max_tokens: int = 4096
    reserved_tokens: int = 512  # For system prompts and responses
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def available_tokens(self) -> int:
        """Get available tokens in the context window."""
        return max(0, self.max_tokens - self.reserved_tokens - self.total_tokens)

    def can_add_chunk(self, chunk: TextChunk) -> bool:
        """Check if a chunk can be added to the context window."""
        estimated_tokens = self._estimate_tokens(chunk.content)
        return self.available_tokens >= estimated_tokens

    def add_chunk(self, chunk: TextChunk) -> bool:
        """Add a chunk to the context window."""
        if not self.can_add_chunk(chunk):
            return False

        self.chunks.append(chunk)
        self.total_tokens += self._estimate_tokens(chunk.content)
        return True

    def remove_chunk(self, index: int) -> Optional[TextChunk]:
        """Remove a chunk from the context window."""
        if 0 <= index < len(self.chunks):
            chunk = self.chunks.pop(index)
            self.total_tokens -= self._estimate_tokens(chunk.content)
            return chunk
        return None

    def clear(self) -> None:
        """Clear all chunks from the context window."""
        self.chunks.clear()
        self.total_tokens = 0

    def get_content(self, separator: str = "\n\n") -> str:
        """Get the combined content of all chunks."""
        return separator.join(chunk.content for chunk in self.chunks)

    def _estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in a text string."""
        # Rough estimation: 1 token ≈ 4 characters for English text
        return len(text) // 4


class AIContextManager:
    """
    Manages AI context for large documents and conversations.

    Features:
    - Intelligent text chunking
    - Context window optimization
    - Memory management for long conversations
    - Semantic search and retrieval
    """

    def __init__(self, max_context_tokens: int = 4096):
        self.max_context_tokens = max_context_tokens
        self.documents: Dict[str, List[TextChunk]] = {}
        self.conversations: Dict[str, ContextWindow] = {}
        self.chunkers = {
            ChunkingStrategy.SENTENCE: self._chunk_by_sentence,
            ChunkingStrategy.PARAGRAPH: self._chunk_by_paragraph,
            ChunkingStrategy.HEADING: self._chunk_by_heading,
            ChunkingStrategy.TOKEN: self._chunk_by_token,
            ChunkingStrategy.SEMANTIC: self._chunk_semantically
        }

    def add_document(self, document_id: str, content: str, strategy: ChunkingStrategy = ChunkingStrategy.PARAGRAPH) -> List[TextChunk]:
        """
        Add a document and chunk it for processing.

        Args:
            document_id: Unique identifier for the document
            content: Full document content
            strategy: Chunking strategy to use

        Returns:
            List of text chunks
        """
        chunker = self.chunkers.get(strategy, self._chunk_by_paragraph)
        chunks = chunker(content)

        # Add position metadata
        current_pos = 0
        for chunk in chunks:
            chunk.start_position = current_pos
            chunk.end_position = current_pos + len(chunk.content)
            current_pos = chunk.end_position

        self.documents[document_id] = chunks
        logger.info(f"Added document {document_id} with {len(chunks)} chunks")
        return chunks

    def get_document_chunks(self, document_id: str) -> List[TextChunk]:
        """Get chunks for a document."""
        return self.documents.get(document_id, [])

    def create_context_window(self, conversation_id: str, max_tokens: Optional[int] = None) -> ContextWindow:
        """Create a new context window for a conversation."""
        window = ContextWindow(max_tokens=max_tokens or self.max_context_tokens)
        self.conversations[conversation_id] = window
        return window

    def get_context_window(self, conversation_id: str) -> Optional[ContextWindow]:
        """Get a context window for a conversation."""
        return self.conversations.get(conversation_id)

    def optimize_context_for_query(
        self,
        document_id: str,
        query: str,
        context_window: ContextWindow,
        max_chunks: int = 5
    ) -> bool:
        """
        Optimize context window for a specific query by selecting relevant chunks.

        Args:
            document_id: Document to search
            query: User query
            context_window: Context window to populate
            max_chunks: Maximum number of chunks to include

        Returns:
            True if optimization was successful
        """
        chunks = self.documents.get(document_id, [])
        if not chunks:
            return False

        # Simple relevance scoring based on keyword matching
        # In a real implementation, this would use semantic search with embeddings
        query_words = set(re.findall(r'\b\w+\b', query.lower()))
        chunk_scores = []

        for chunk in chunks:
            chunk_words = set(re.findall(r'\b\w+\b', chunk.content.lower()))
            score = len(query_words.intersection(chunk_words))
            chunk_scores.append((chunk, score))

        # Sort by relevance score
        chunk_scores.sort(key=lambda x: x[1], reverse=True)

        # Add top chunks to context window
        context_window.clear()
        added_count = 0

        for chunk, score in chunk_scores:
            if score > 0 and added_count < max_chunks:
                if context_window.add_chunk(chunk):
                    added_count += 1
                else:
                    break  # No more space in context window

        logger.info(f"Optimized context for query '{query}': added {added_count} chunks")
        return added_count > 0

    def summarize_for_context(self, content: str, max_length: int = 200) -> str:
        """
        Create a summary of content suitable for context inclusion.

        Args:
            content: Content to summarize
            max_length: Maximum summary length

        Returns:
            Summarized content
        """
        if len(content) <= max_length:
            return content

        # Simple extractive summarization - take first and last parts
        # In a real implementation, this would use AI summarization
        words = content.split()
        if len(words) <= max_length // 5:  # Rough word count estimate
            return content

        # Take beginning and end
        begin_words = words[:max_length // 10]
        end_words = words[-(max_length // 10):]

        summary = " ".join(begin_words + ["..."] + end_words)
        return summary[:max_length]

    def cleanup_old_contexts(self, max_age_hours: int = 24) -> int:
        """Clean up old context windows to free memory."""
        # In a real implementation, this would check timestamps
        # For now, just return 0 as we don't track timestamps
        return 0

    # Chunking strategies
    def _chunk_by_sentence(self, content: str) -> List[TextChunk]:
        """Chunk text by sentences."""
        text = content.strip()
        chunks = []

        for match in re.finditer(r'[^.!?]+(?:[.!?]+|$)', text):
            sentence = match.group(0).strip()
            if sentence:
                chunks.append(TextChunk(
                    content=sentence,
                    start_position=match.start(),
                    end_position=match.end(),
                    chunk_type="sentence"
                ))

        return chunks

    def _chunk_by_paragraph(self, content: str) -> List[TextChunk]:
        """Chunk text by paragraphs."""
        text = content.strip()
        paragraphs = re.split(r'\n\s*\n', text)
        chunks = []
        current_pos = 0

        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if paragraph:
                start = text.index(paragraph, current_pos)
                end = start + len(paragraph)
                chunks.append(TextChunk(
                    content=paragraph,
                    start_position=start,
                    end_position=end,
                    chunk_type="paragraph"
                ))
                current_pos = end

        return chunks

    def _chunk_by_heading(self, content: str) -> List[TextChunk]:
        """Chunk text by headings and sections."""
        text = content.strip()
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_start = 0
        position = 0

        for line in lines:
            stripped_line = line.strip()
            is_heading = bool(re.match(r'^\s*#{1,6}\s+.*', line)) or (stripped_line.isupper() and len(stripped_line) > 10)
            if is_heading and current_chunk:
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text:
                    start = text.index(chunk_text, current_start)
                    end = start + len(chunk_text)
                    chunks.append(TextChunk(
                        content=chunk_text,
                        start_position=start,
                        end_position=end,
                        chunk_type="section"
                    ))
                    current_start = end
                    current_chunk = []

            current_chunk.append(line)
            position += len(line) + 1

        if current_chunk:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text:
                start = text.index(chunk_text, current_start)
                end = start + len(chunk_text)
                chunks.append(TextChunk(
                    content=chunk_text,
                    start_position=start,
                    end_position=end,
                    chunk_type="section"
                ))

        return chunks

    def _chunk_by_token(self, content: str, chunk_size: int = 512) -> List[TextChunk]:
        """Chunk text by token count."""
        words = content.split()
        chunks = []
        current_pos = 0

        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            chunk_text = ' '.join(chunk_words)
            start = content.index(chunk_text, current_pos)
            end = start + len(chunk_text)
            chunks.append(TextChunk(
                content=chunk_text,
                start_position=start,
                end_position=end,
                chunk_type="token_chunk",
                metadata={"token_count": len(chunk_words)}
            ))
            current_pos = end

        return chunks

    def _chunk_semantically(self, content: str) -> List[TextChunk]:
        """
        Chunk text semantically (advanced implementation would use embeddings).

        For now, falls back to paragraph chunking.
        """
        return self._chunk_by_paragraph(content)