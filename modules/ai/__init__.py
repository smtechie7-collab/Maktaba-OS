# Maktaba-OS AI Module
"""
AI-powered content creation and intelligence layer for Maktaba-OS.

This module provides:
- Modular AI agent architecture with plugin system
- AI service abstraction layer (OpenAI, Anthropic, local models)
- Model management with automatic fallback and load balancing
- Token usage tracking and cost optimization
- AI context window management for large documents
- Vector embeddings and semantic search
- Content generation and assistance
"""

from .agent import AIAgent, AgentConfig, AgentContext, AgentResponse, AgentCapability
from .service import AIService, AIServiceConfig, ServiceRequest, ServiceResponse, ModelProvider
from .models import AIModel, ModelProvider, model_registry, ModelRegistry, ModelSelector
from .context import AIContextManager, ContextWindow, TextChunk, ChunkingStrategy
from .metrics import AIMetrics, MetricsAggregator, metrics_aggregator, MetricType
from .embeddings import (
    SemanticSearchEngine,
    VectorIndex,
    EmbeddingModel,
    VectorDocument,
    initialize_semantic_search,
    get_semantic_search_engine
)
from .content_agent import ContentGenerationAgent, create_content_generation_agent
from .content_intelligence import ContentIntelligenceAgent, create_content_intelligence_agent
from .translation import TranslationAgent, create_translation_agent, TranslationMemory, TerminologyManager
from .voice_synthesis import VoiceSynthesisAgent, create_voice_synthesis_agent

__all__ = [
    # Core Infrastructure
    'AIAgent', 'AgentConfig', 'AgentContext', 'AgentResponse', 'AgentCapability',
    'AIService', 'AIServiceConfig', 'ServiceRequest', 'ServiceResponse', 'ModelProvider',
    'AIModel', 'model_registry', 'ModelRegistry', 'ModelSelector',
    'AIContextManager', 'ContextWindow', 'TextChunk', 'ChunkingStrategy',
    'AIMetrics', 'MetricsAggregator', 'metrics_aggregator', 'MetricType',

    # Semantic Search
    'SemanticSearchEngine', 'VectorIndex', 'EmbeddingModel', 'VectorDocument',
    'initialize_semantic_search', 'get_semantic_search_engine',

    # Agents
    'ContentGenerationAgent', 'create_content_generation_agent',
    'ContentIntelligenceAgent', 'create_content_intelligence_agent',
    'TranslationAgent', 'create_translation_agent',
    'VoiceSynthesisAgent', 'create_voice_synthesis_agent',

    # Localization
    'TranslationMemory', 'TerminologyManager'
]