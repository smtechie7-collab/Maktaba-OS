"""
Tests for the content intelligence module.
"""

import pytest
import asyncio
from typing import Any, Dict, List

from modules.ai.content_intelligence import ContentIntelligenceAgent, ContentQualityReport, StyleAnalysisReport, PlagiarismCheckResult
from modules.ai.agent import AgentConfig, AgentCapability, AgentContext
from modules.ai.service import AIService, AIServiceConfig, ServiceRequest, ServiceResponse, ModelProvider


class DummyAIService(AIService):
    def __init__(self):
        config = AIServiceConfig(provider=ModelProvider.OPENAI, api_key="test")
        super().__init__(config)

    async def generate_text(self, request: ServiceRequest) -> ServiceResponse:
        return ServiceResponse(
            content="Generated response for testing.",
            model_used=request.model,
            tokens_used=50,
            finish_reason="stop",
            metadata={"test": True},
            cost=0.0,
            processing_time=0.01
        )

    async def list_models(self) -> List[Any]:
        return []

    async def check_health(self) -> bool:
        return True


@pytest.fixture
def dummy_service() -> DummyAIService:
    return DummyAIService()


@pytest.fixture
def content_intel_agent(dummy_service: DummyAIService) -> ContentIntelligenceAgent:
    config = AgentConfig(
        name="test_intel",
        description="Test intelligence agent",
        capabilities=[AgentCapability.TEXT_ANALYSIS, AgentCapability.REVIEW],
        model_provider=ModelProvider.OPENAI.value,
        model_name="gpt-4",
        temperature=0.3,
        max_tokens=1200
    )
    return ContentIntelligenceAgent(config, dummy_service)


@pytest.mark.asyncio
async def test_process_suggestion_task(content_intel_agent: ContentIntelligenceAgent):
    context = AgentContext(language="en")
    response = await content_intel_agent.process(
        {
            "task_type": "suggestion",
            "content": "A short draft about charity and service.",
            "topic": "community support",
            "language": "en",
            "style": "informal"
        },
        context
    )

    assert response.content == "Generated response for testing."
    assert response.model_used == "gpt-4"
    assert response.error_message is None


@pytest.mark.asyncio
async def test_process_footnote_task(content_intel_agent: ContentIntelligenceAgent):
    context = AgentContext(language="en")
    response = await content_intel_agent.process(
        {
            "task_type": "footnote",
            "content": "Salah is performed five times every day by practicing Muslims.",
            "language": "en",
            "style": "academic"
        },
        context
    )

    assert response.content == "Generated response for testing."
    assert response.metadata["task_type"] == "footnote"
    assert response.error_message is None


@pytest.mark.asyncio
async def test_process_citation_task(content_intel_agent: ContentIntelligenceAgent):
    context = AgentContext(language="en")
    response = await content_intel_agent.process(
        {
            "task_type": "citation",
            "content": "The Five Pillars of Islam are fundamental practices for Muslims.",
            "language": "en",
            "style": "academic",
            "reference_style": "APA"
        },
        context
    )

    assert response.content == "Generated response for testing."
    assert response.metadata["task_type"] == "citation"
    assert response.error_message is None


def test_build_footnote_prompt_includes_topic(content_intel_agent: ContentIntelligenceAgent):
    prompt = content_intel_agent._build_prompt(
        "footnote",
        "Salah is performed five times every day by practicing Muslims.",
        "daily prayer rituals",
        "en",
        "academic",
        {}
    )

    assert "daily prayer rituals" in prompt
    assert "footnotes" in prompt.lower()


def test_build_citation_prompt_includes_reference_style_and_source_type(content_intel_agent: ContentIntelligenceAgent):
    prompt = content_intel_agent._build_prompt(
        "citation",
        "The Five Pillars of Islam are fundamental practices for Muslims.",
        "Islamic practice",
        "en",
        "academic",
        {"reference_style": "MLA", "source_type": "article"}
    )

    assert "MLA" in prompt
    assert "article" in prompt
    assert "Islamic practice" in prompt


@pytest.mark.asyncio
async def test_process_collaborative_task(content_intel_agent: ContentIntelligenceAgent):
    context = AgentContext(language="en", conversation_history=[
        {"role": "user", "content": "Can you help improve the introduction?"},
        {"role": "assistant", "content": "Sure, what tone are you aiming for?"}
    ])
    response = await content_intel_agent.process(
        {
            "task_type": "collaborate",
            "content": "This introduction should explain the importance of ethical scholarship.",
            "topic": "Islamic education",
            "language": "en",
            "style": "academic"
        },
        context
    )

    assert response.content == "Generated response for testing."
    assert response.metadata["task_type"] == "collaborate"
    assert response.error_message is None


@pytest.mark.asyncio
async def test_process_outline_task(content_intel_agent: ContentIntelligenceAgent):
    """Test outline generation task."""
    await content_intel_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_intel_agent.process(
        {
            "task_type": "outline",
            "topic": "Islamic ethics",
            "style": "academic"
        },
        context
    )
    
    assert response.content == "Generated response for testing."
    assert response.metadata["task_type"] == "outline"
    assert response.error_message is None


@pytest.mark.asyncio
async def test_process_expand_task(content_intel_agent: ContentIntelligenceAgent):
    """Test content expansion task."""
    await content_intel_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_intel_agent.process(
        {
            "task_type": "expand",
            "content": "Islamic ethics emphasize justice and compassion.",
            "topic": "Islamic ethics",
            "style": "academic"
        },
        context
    )
    
    assert response.content == "Generated response for testing."
    assert response.metadata["task_type"] == "expand"
    assert response.error_message is None


@pytest.mark.asyncio
async def test_process_summarize_task(content_intel_agent: ContentIntelligenceAgent):
    """Test content summarization task."""
    await content_intel_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_intel_agent.process(
        {
            "task_type": "summarize",
            "content": "Islamic ethics is a comprehensive system that guides moral behavior, emphasizing justice, compassion, and accountability to Allah. It covers all aspects of life including business, family, and social interactions.",
            "language": "en",
            "style": "academic",
            "length": "medium"
        },
        context
    )
    
    assert response.content == "Generated response for testing."
    assert response.metadata["task_type"] == "summarize"
    assert response.error_message is None


def test_build_outline_prompt_includes_topic(content_intel_agent: ContentIntelligenceAgent):
    """Test outline prompt building."""
    prompt = content_intel_agent._build_prompt(
        "outline",
        "",
        "Islamic ethics",
        "en",
        "academic",
        {}
    )

    assert "Islamic ethics" in prompt
    assert "outline" in prompt.lower()


def test_build_expand_prompt_includes_content(content_intel_agent: ContentIntelligenceAgent):
    """Test expand prompt building."""
    prompt = content_intel_agent._build_prompt(
        "expand",
        "Islamic ethics emphasize justice.",
        "Islamic ethics",
        "en",
        "academic",
        {}
    )

    assert "Islamic ethics emphasize justice" in prompt
    assert "Expand" in prompt


@pytest.mark.asyncio
async def test_process_rewrite_task(content_intel_agent: ContentIntelligenceAgent):
    """Test content rewrite task."""
    await content_intel_agent.initialize()
    
    context = AgentContext(language="en")
    response = await content_intel_agent.process(
        {
            "task_type": "rewrite",
            "content": "This is academic content about Islamic ethics.",
            "language": "en",
            "style": "academic",
            "target_style": "casual"
        },
        context
    )
    
    assert response.content == "Generated response for testing."
    assert response.metadata["task_type"] == "rewrite"
    assert response.error_message is None


def test_build_rewrite_prompt_includes_target_style(content_intel_agent: ContentIntelligenceAgent):
    """Test rewrite prompt building."""
    prompt = content_intel_agent._build_prompt(
        "rewrite",
        "Original academic content.",
        "",
        "en",
        "academic",
        {"target_style": "casual"}
    )

    assert "casual" in prompt
    assert "rewrite" in prompt.lower()


def test_generate_quality_report(content_intel_agent: ContentIntelligenceAgent):
    report = content_intel_agent._generate_quality_report(
        "This text is clear and well structured, but it uses some long passive sentences."
    )

    assert isinstance(report, ContentQualityReport)
    assert 0.0 <= report.score <= 1.0
    assert report.recommendations


def test_generate_style_analysis(content_intel_agent: ContentIntelligenceAgent):
    report = content_intel_agent._generate_style_analysis(
        "The ensuing sections are written in a scholarly tone while the introduction is informal.",
        "scholarly"
    )

    assert isinstance(report, StyleAnalysisReport)
    assert 0.0 <= report.consistency_score <= 1.0
    assert report.tone == "scholarly"


def test_detect_plagiarism_fallback(content_intel_agent: ContentIntelligenceAgent):
    content = "The holy book is called the Quran and it guides daily life."
    known_texts = [
        {"source": "source_1", "content": "The Quran is the holy book of Islam and it guides daily life."},
        {"source": "source_2", "content": "Prayer is one of the pillars of Islam performed daily."}
    ]

    result = content_intel_agent._detect_plagiarism(content, known_texts)
    assert isinstance(result, PlagiarismCheckResult)
    assert 0.0 <= result.similarity_score <= 1.0
    assert isinstance(result.matched_snippets, list)
