"""
Tests for translation and localization AI features.
"""

import pytest
from modules.ai.translation import (
    TranslationAgent,
    create_translation_agent,
    TerminologyManager,
    TranslationMemory,
    TranslationSegment,
    TerminologyEntry
)
from modules.ai.agent import AgentConfig, AgentCapability, AgentContext
from modules.ai.service import AIService, AIServiceConfig, ServiceRequest, ServiceResponse, ModelProvider
from typing import List, Any, Dict


class DummyTranslationService(AIService):
    def __init__(self):
        config = AIServiceConfig(provider=ModelProvider.OPENAI, api_key="test")
        super().__init__(config)

    async def generate_text(self, request: ServiceRequest) -> ServiceResponse:
        content = request.messages[-1]["content"]
        return ServiceResponse(
            content=f"TRANSLATED: {content}",
            model_used=request.model,
            tokens_used=20,
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
def dummy_translation_service() -> DummyTranslationService:
    return DummyTranslationService()


@pytest.fixture
def translation_agent(dummy_translation_service: DummyTranslationService) -> TranslationAgent:
    config = AgentConfig(
        name="translator_test",
        description="Test translation agent",
        capabilities=[AgentCapability.TRANSLATION],
        model_provider=ModelProvider.OPENAI.value,
        model_name="gpt-4",
        temperature=0.3,
        max_tokens=1600
    )
    return TranslationAgent(config, dummy_translation_service)


@pytest.mark.asyncio
async def test_translation_agent_translate_task(translation_agent: TranslationAgent):
    context = AgentContext(language="en")
    response = await translation_agent.process(
        {
            "task_type": "translate",
            "content": "This is a test.",
            "source_language": "en",
            "target_language": "ar",
            "domain": "religion",
            "locale": "MENA"
        },
        context
    )

    assert response.content.startswith("TRANSLATED:")
    assert response.metadata["task_type"] == "translate"
    assert response.model_used == "gpt-4"


@pytest.mark.asyncio
async def test_translation_agent_localize_task(translation_agent: TranslationAgent):
    context = AgentContext(language="en")
    response = await translation_agent.process(
        {
            "task_type": "localize",
            "content": "Blessings upon you.",
            "source_language": "en",
            "target_language": "ar",
            "domain": "religion",
            "locale": "Gulf"
        },
        context
    )

    assert response.content.startswith("TRANSLATED:")
    assert response.metadata["task_type"] == "localize"


def test_terminology_manager_lookup_and_suggest():
    manager = TerminologyManager()
    manager.add_entry(TerminologyEntry(
        source_term="Islam",
        target_term="الإسلام",
        source_language="en",
        target_language="ar",
        domain="religion"
    ))

    entry = manager.find("Islam", "en", "ar")
    assert entry is not None
    assert entry.target_term == "الإسلام"

    suggestions = manager.suggest("Islamm", "en", "ar")
    assert suggestions
    assert suggestions[0].source_term == "Islam"


def test_translation_memory_search():
    memory = TranslationMemory()
    memory.add_segment(TranslationSegment(
        source_text="The Quran is holy.",
        translated_text="القرآن مقدس.",
        source_language="en",
        target_language="ar",
        domain="religion"
    ))

    matches = memory.search("The Quran is holy.", "en", "ar", threshold=0.5)
    assert len(matches) >= 1
    assert matches[0].translated_text == "القرآن مقدس."


def test_translation_memory_tmx_export_import(tmp_path):
    memory = TranslationMemory()
    memory.add_segment(TranslationSegment(
        source_text="Peace be upon you.",
        translated_text="السلام عليكم.",
        source_language="en",
        target_language="ar",
        domain="religion"
    ))

    tmx_path = tmp_path / "memory.tmx"
    memory.export_tmx(str(tmx_path))

    loaded = TranslationMemory()
    loaded.import_tmx(str(tmx_path))
    assert len(loaded.segments) == 1
    assert loaded.segments[0].translated_text == "السلام عليكم."


def test_terminology_manager_tmx_export_import(tmp_path):
    manager = TerminologyManager()
    manager.add_entry(TerminologyEntry(
        source_term="Allah",
        target_term="الله",
        source_language="en",
        target_language="ar",
        domain="religion"
    ))

    tmx_path = tmp_path / "glossary.tmx"
    manager.export_tmx(str(tmx_path))

    loaded = TerminologyManager()
    loaded.import_tmx(str(tmx_path))
    assert loaded.entries
    assert loaded.entries[0].source_term == "Allah"
