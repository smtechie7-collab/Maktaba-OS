"""
Tests for the ContentGenerationAgent module.
"""

import pytest
import asyncio
from typing import Any, Dict, List

from modules.ai.content_agent import (
    ContentGenerationAgent,
    create_content_generation_agent
)
from modules.ai.agent import AgentConfig, AgentCapability, AgentContext
from modules.ai.service import (
    AIService, AIServiceConfig, ServiceRequest, ServiceResponse, ModelProvider
)


class DummyContentService(AIService):
    """Mock AI service for content generation testing."""
    
    def __init__(self):
        config = AIServiceConfig(provider=ModelProvider.OPENAI, api_key="test")
        super().__init__(config)

    async def generate_text(self, request: ServiceRequest) -> ServiceResponse:
        # Simulate different responses based on task type in the prompt
        content = request.messages[-1]["content"]
        
        if "Write" in content or "Generate" in content:
            generated = f"Generated content: This is a {request.max_tokens}-token sample text for the topic."
        elif "Expand" in content:
            generated = "This is the expanded version with more details and comprehensive information."
        elif "Rewrite" in content:
            generated = "Here is the rewritten text with a different style and approach."
        else:
            generated = "Default generated response."
        
        return ServiceResponse(
            content=generated,
            model_used=request.model,
            tokens_used=request.max_tokens or 1000,
            finish_reason="stop",
            metadata={"temperature": request.temperature},
            cost=0.01,
            processing_time=0.5
        )

    async def list_models(self) -> List[Any]:
        return []

    async def check_health(self) -> bool:
        """Check if the service is healthy."""
        return True


@pytest.fixture
def content_service() -> DummyContentService:
    return DummyContentService()


@pytest.fixture
def content_agent(content_service: DummyContentService) -> ContentGenerationAgent:
    config = AgentConfig(
        name="test_writer",
        description="Test content generation agent",
        capabilities=[AgentCapability.TEXT_GENERATION, AgentCapability.EDITING],
        model_provider=ModelProvider.OPENAI.value,
        model_name="gpt-4",
        temperature=0.7,
        max_tokens=2048
    )
    return ContentGenerationAgent(config, content_service)


@pytest.mark.asyncio
async def test_content_agent_initialization(content_agent: ContentGenerationAgent):
    """Test agent initialization and status."""
    await content_agent.initialize()
    assert content_agent.status.value == "ready"
    assert AgentCapability.TEXT_GENERATION in content_agent.capabilities
    assert AgentCapability.EDITING in content_agent.capabilities


@pytest.mark.asyncio
async def test_process_generate_task(content_agent: ContentGenerationAgent):
    """Test content generation task."""
    await content_agent.initialize()
    
    context = AgentContext(language="en", domain="academic")
    response = await content_agent.process(
        {
            "task_type": "generate",
            "topic": "Islamic philosophy",
            "language": "en",
            "style": "academic",
            "length": "medium"
        },
        context
    )
    
    assert response.content
    assert "Generated" in response.content
    assert response.model_used == "gpt-4"
    assert response.processing_time >= 0
    assert response.metadata["task_type"] == "generate"


@pytest.mark.asyncio
async def test_process_expand_task(content_agent: ContentGenerationAgent):
    """Test content expansion task."""
    await content_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_agent.process(
        {
            "task_type": "expand",
            "content": "Islam emphasizes charity.",
            "language": "en",
            "style": "formal"
        },
        context
    )
    
    assert response.content
    assert "expanded" in response.content.lower()
    assert response.metadata["task_type"] == "expand"


@pytest.mark.asyncio
async def test_process_rewrite_task(content_agent: ContentGenerationAgent):
    """Test content rewriting task."""
    await content_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_agent.process(
        {
            "task_type": "rewrite",
            "content": "Prayer is fundamental to faith.",
            "style": "narrative"
        },
        context
    )
    
    assert response.content
    assert "rewritten" in response.content.lower()


@pytest.mark.asyncio
async def test_process_summarize_task(content_agent: ContentGenerationAgent):
    """Test content summarization task."""
    await content_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_agent.process(
        {
            "task_type": "summarize",
            "content": "Long text " * 100,
            "length": "short"
        },
        context
    )
    
    assert response.content
    assert response.metadata["task_type"] == "summarize"


@pytest.mark.asyncio
async def test_process_outline_task(content_agent: ContentGenerationAgent):
    """Test outline generation task."""
    await content_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_agent.process(
        {
            "task_type": "outline",
            "topic": "Islamic ethics",
            "style": "academic"
        },
        context
    )
    
    assert response.content
    assert response.metadata["task_type"] == "outline"


@pytest.mark.asyncio
async def test_process_title_task(content_agent: ContentGenerationAgent):
    """Test title generation task."""
    await content_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_agent.process(
        {
            "task_type": "title",
            "topic": "Religious tolerance"
        },
        context
    )
    
    assert response.content
    assert response.metadata["task_type"] == "title"


@pytest.mark.asyncio
async def test_process_multilingual_content(content_agent: ContentGenerationAgent):
    """Test content generation in multiple languages."""
    await content_agent.initialize()
    
    for lang_code, lang_name in [("ar", "Arabic"), ("ur", "Urdu"), ("hi", "Hindi")]:
        context = AgentContext(language=lang_code)
        response = await content_agent.process(
            {
                "task_type": "generate",
                "topic": "spiritual wisdom",
                "language": lang_code,
                "style": "poetic"
            },
            context
        )
        
        assert response.content
        assert response.metadata["language"] == lang_code


@pytest.mark.asyncio
async def test_process_error_handling(content_agent: ContentGenerationAgent):
    """Test error handling in content generation."""
    # Don't initialize to trigger error
    context = AgentContext(language="en")
    
    response = await content_agent.process(
        {"task_type": "generate", "topic": "test"},
        context
    )
    
    # Should return error response
    assert response.error_message is not None or response.content == ""


def test_create_content_generation_agent():
    """Test factory function for creating content generation agent."""
    agent = create_content_generation_agent(
        name="custom_writer",
        model_name="gpt-3.5-turbo"
    )
    
    assert agent.name == "custom_writer"
    assert agent.config.model_name == "gpt-3.5-turbo"
    assert AgentCapability.TEXT_GENERATION in agent.capabilities


def test_build_prompt_variations(content_agent: ContentGenerationAgent):
    """Test prompt building for different task types."""
    topic = "Islamic education"
    content = "Student learning is important."
    language = "en"
    style = "academic"
    length = "medium"
    
    # Test generate prompt
    prompt = content_agent._build_prompt("generate", "", topic, language, style, length)
    assert "Write" in prompt or "Generate" in prompt
    assert topic in prompt
    
    # Test expand prompt
    prompt = content_agent._build_prompt("expand", content, "", language, style, length)
    assert "Expand" in prompt
    assert content in prompt
    
    # Test rewrite prompt
    prompt = content_agent._build_prompt("rewrite", content, "", language, style, length)
    assert "Rewrite" in prompt
    
    # Test summarize prompt
    prompt = content_agent._build_prompt("summarize", content, "", language, style, length)
    assert "Summarize" in prompt
    
    # Test outline prompt
    prompt = content_agent._build_prompt("outline", "", topic, language, style, length)
    assert "outline" in prompt.lower()


def test_get_temperature_for_task(content_agent: ContentGenerationAgent):
    """Test temperature selection for different tasks."""
    temps = {
        "generate": 0.7,
        "expand": 0.6,
        "summarize": 0.3,
        "rewrite": 0.5,
        "outline": 0.4,
        "title": 0.8,
    }
    
    for task, expected_temp in temps.items():
        actual_temp = content_agent._get_temperature_for_task(task)
        assert actual_temp == expected_temp


def test_get_max_tokens_for_length(content_agent: ContentGenerationAgent):
    """Test max tokens selection for different content lengths."""
    tokens = {
        "short": 500,
        "medium": 1500,
        "long": 3000,
        "xl": 5000
    }
    
    for length, expected_tokens in tokens.items():
        actual_tokens = content_agent._get_max_tokens_for_length(length)
        assert actual_tokens == expected_tokens


def test_assess_quality_score(content_agent: ContentGenerationAgent):
    """Test content quality assessment."""
    # Empty content
    score = content_agent._assess_quality("")
    assert score == 0.0
    
    # Very short content
    score = content_agent._assess_quality("Hi")
    assert 0.0 <= score < 0.5
    
    # Good quality content
    good_content = "This is a well-structured paragraph with multiple sentences. " * 10
    score = content_agent._assess_quality(good_content)
    assert 0.5 <= score <= 1.0
    
    # Content with passive voice
    passive_content = "The work was completed by the team. " * 20
    passive_score = content_agent._assess_quality(passive_content)
    assert 0 <= passive_score <= 1.0


@pytest.mark.asyncio
async def test_get_system_prompt_multilingual(content_agent: ContentGenerationAgent):
    """Test system prompt generation for different languages."""
    # English
    prompt_en = content_agent._get_system_prompt("en", "academic")
    assert "English" not in prompt_en or "respond" not in prompt_en.lower()
    
    # Arabic
    prompt_ar = content_agent._get_system_prompt("ar", "academic")
    assert "Arabic" in prompt_ar
    
    # Urdu
    prompt_ur = content_agent._get_system_prompt("ur", "formal")
    assert "Urdu" in prompt_ur


@pytest.mark.asyncio
async def test_agent_metrics_recording(content_agent: ContentGenerationAgent):
    """Test that metrics are recorded for agent operations."""
    await content_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_agent.process(
        {
            "task_type": "generate",
            "topic": "ethics",
            "language": "en",
            "style": "academic",
            "length": "medium"
        },
        context
    )
    
    # Verify metrics were recorded
    assert content_agent.metrics.total_requests > 0
    assert content_agent.metrics.successful_requests >= 0


@pytest.mark.asyncio
async def test_process_introduction_task(content_agent: ContentGenerationAgent):
    """Test introduction generation task."""
    await content_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_agent.process(
        {
            "task_type": "introduction",
            "topic": "Religious history",
            "style": "engaging"
        },
        context
    )
    
    assert response.content
    assert response.metadata["task_type"] == "introduction"


@pytest.mark.asyncio
async def test_process_conclusion_task(content_agent: ContentGenerationAgent):
    """Test conclusion generation task."""
    await content_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_agent.process(
        {
            "task_type": "conclusion",
            "content": "The topic covered includes important aspects.",
            "style": "formal"
        },
        context
    )
    
    assert response.content
    assert response.metadata["task_type"] == "conclusion"
