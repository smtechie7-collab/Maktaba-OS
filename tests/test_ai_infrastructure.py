"""
Basic tests for AI infrastructure components.
"""

import pytest
from modules.ai.agent import AgentConfig, AgentCapability, AgentContext
from modules.ai.service import ModelProvider, AIModel
from modules.ai.models import model_registry, OPENAI_MODELS
from modules.ai.context import AIContextManager, ChunkingStrategy
from modules.ai.metrics import AIMetrics, MetricType


def test_agent_config_validation():
    """Test agent configuration validation."""
    # Valid config
    config = AgentConfig(
        name="test_agent",
        description="Test agent",
        capabilities=[AgentCapability.TEXT_GENERATION],
        model_provider="openai",
        model_name="gpt-4"
    )
    assert config.name == "test_agent"

    # Invalid config - no capabilities
    with pytest.raises(ValueError):
        AgentConfig(
            name="test_agent",
            description="Test agent",
            capabilities=[],
            model_provider="openai",
            model_name="gpt-4"
        )


def test_ai_model_creation():
    """Test AI model creation and properties."""
    model = AIModel(
        name="gpt-4",
        provider=ModelProvider.OPENAI,
        context_window=8192,
        max_tokens=4096,
        input_cost_per_token=0.00003,
        output_cost_per_token=0.00006
    )

    assert model.name == "gpt-4"
    assert model.provider == ModelProvider.OPENAI
    assert model.context_window == 8192
    assert model.max_tokens == 4096


def test_model_registry():
    """Test model registry functionality."""
    # Test model registration
    test_model = AIModel(
        name="test-model",
        provider=ModelProvider.CUSTOM,
        context_window=4096,
        max_tokens=2048
    )

    model_registry.register_model(test_model)
    retrieved = model_registry.get_model("test-model")
    assert retrieved is not None
    assert retrieved.name == "test-model"

    # Test model listing
    openai_models = model_registry.list_models(ModelProvider.OPENAI)
    assert len(openai_models) > 0
    assert all(m.provider == ModelProvider.OPENAI for m in openai_models)


def test_context_chunking():
    """Test text chunking functionality."""
    manager = AIContextManager()

    # Test paragraph chunking
    text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
    chunks = manager._chunk_by_paragraph(text)

    assert len(chunks) == 3
    assert "First paragraph" in chunks[0].content
    assert "Second paragraph" in chunks[1].content
    assert "Third paragraph" in chunks[2].content

    # Test sentence chunking
    text = "First sentence. Second sentence! Third sentence?"
    chunks = manager._chunk_by_sentence(text)

    assert len(chunks) == 3
    assert "First sentence" in chunks[0].content
    assert "Second sentence" in chunks[1].content
    assert "Third sentence" in chunks[2].content


def test_context_window_management():
    """Test context window management."""
    from modules.ai.context import ContextWindow, TextChunk

    window = ContextWindow(max_tokens=1000, reserved_tokens=100)

    # Test adding chunks
    chunk1 = TextChunk(content="Short text", start_position=0, end_position=10, chunk_type="test")
    chunk2 = TextChunk(content="A" * 500, start_position=11, end_position=511, chunk_type="test")

    assert window.add_chunk(chunk1)
    assert window.available_tokens < 1000  # Some tokens used

    # Test content retrieval
    content = window.get_content()
    assert "Short text" in content


def test_metrics_tracking():
    """Test metrics tracking functionality."""
    metrics = AIMetrics()

    # Record some requests
    metrics.record_request(
        success=True,
        input_tokens=100,
        output_tokens=50,
        cost=0.01,
        response_time=2.5,
        provider="openai",
        model="gpt-4"
    )

    metrics.record_request(
        success=False,
        response_time=1.0,
        provider="openai",
        model="gpt-4"
    )

    # Check metrics
    assert metrics.total_requests == 2
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 1
    assert metrics.total_tokens_used == 150
    assert metrics.total_cost == 0.01
    assert metrics.error_rate == 0.5

    # Test summary
    summary = metrics.get_summary(hours=24)
    assert summary["requests"]["total"] == 2
    assert summary["cost"]["total"] == 0.01


def test_agent_context():
    """Test agent context creation."""
    context = AgentContext(
        user_id="user123",
        session_id="session456",
        language="ar",
        domain="religious"
    )

    assert context.user_id == "user123"
    assert context.session_id == "session456"
    assert context.language == "ar"
    assert context.domain == "religious"