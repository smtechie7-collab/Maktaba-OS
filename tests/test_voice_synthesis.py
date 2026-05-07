"""Tests for voice synthesis and audio verification features."""

import base64
import pytest

from modules.ai.service import (
    AIService,
    AIServiceConfig,
    AudioRequest,
    AudioResponse,
    AIModel,
    ModelProvider,
    OpenAIService,
)
from modules.ai.voice_synthesis import VoiceSynthesisAgent
from modules.ai.agent import AgentConfig, AgentCapability, AgentContext


class DummyAudioResponse:
    def __init__(self, audio_data: bytes, content_type: str):
        self.status = 200
        self.headers = {"Content-Type": content_type}
        self._audio_data = audio_data

    async def read(self):
        return self._audio_data

    async def text(self):
        return ""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False


class DummySession:
    def post(self, url: str, json: dict):
        assert url.endswith("/audio/speech")
        assert json["model"] == "gpt-4o-mini-tts"
        return DummyAudioResponse(b"fake-audio-bytes", "audio/wav")


class DummyOpenAIService(OpenAIService):
    def __init__(self):
        config = AIServiceConfig(provider=ModelProvider.OPENAI, api_key="test")
        super().__init__(config)
        self.session = DummySession()

    async def generate_text(self, request):
        raise NotImplementedError("Text generation is not used in this test")

    async def list_models(self):
        return [AIModel(name="gpt-4o-mini-tts", provider=ModelProvider.OPENAI, context_window=0, max_tokens=0)]


class DummyVoiceService(AIService):
    def __init__(self):
        config = AIServiceConfig(provider=ModelProvider.OPENAI, api_key="test")
        super().__init__(config)

    async def generate_text(self, request):
        raise NotImplementedError("Text generation is not used for voice synthesis tests")

    async def generate_audio(self, request: AudioRequest) -> AudioResponse:
        return AudioResponse(
            audio_data=b"hello-voice",
            content_type="audio/wav",
            model_used=request.model,
            duration_seconds=1.2,
        )

    async def list_models(self):
        return [AIModel(name="gpt-4o-mini-tts", provider=ModelProvider.OPENAI, context_window=0, max_tokens=0)]

    async def check_health(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_openai_service_generate_audio():
    service = DummyOpenAIService()
    request = AudioRequest(
        model="gpt-4o-mini-tts",
        input_text="Hello, translation verification.",
        voice="alloy",
        language="en-US",
        format="wav",
    )

    response = await service.generate_audio(request)

    assert response.audio_data == b"fake-audio-bytes"
    assert response.content_type == "audio/wav"
    assert response.model_used == "gpt-4o-mini-tts"


@pytest.mark.asyncio
async def test_voice_synthesis_agent_process_synthesize():
    dummy_service = DummyVoiceService()
    agent = VoiceSynthesisAgent(
        AgentConfig(
            name="tts_test",
            description="Test voice synthesis agent",
            capabilities=[AgentCapability.TRANSLATION],
            model_provider=ModelProvider.OPENAI.value,
            model_name="gpt-4o-mini-tts",
            temperature=0.3,
            max_tokens=0,
        ),
        dummy_service,
    )

    await agent.initialize()
    result = await agent.process(
        {
            "task_type": "synthesize",
            "content": "مرحبا بالعالم",
            "language": "ar-AE",
            "voice": "alloy",
            "format": "wav",
        },
        AgentContext(language="ar"),
    )

    assert result.content.startswith("Generated audio")
    assert result.metadata["content_type"] == "audio/wav"
    assert base64.b64decode(result.metadata["audio_base64"]) == b"hello-voice"
    assert result.model_used == "gpt-4o-mini-tts"


@pytest.mark.asyncio
async def test_voice_synthesis_agent_process_verify_translation():
    dummy_service = DummyVoiceService()
    agent = VoiceSynthesisAgent(
        AgentConfig(
            name="tts_verify",
            description="Test translation verification by voice",
            capabilities=[AgentCapability.TRANSLATION],
            model_provider=ModelProvider.OPENAI.value,
            model_name="gpt-4o-mini-tts",
            temperature=0.3,
            max_tokens=0,
        ),
        dummy_service,
    )

    await agent.initialize()
    result = await agent.process(
        {
            "task_type": "verify_translation",
            "content": "Original text should not be spoken.",
            "translated_text": "مرحبا بالعالم",
            "language": "ar-AE",
        },
        AgentContext(language="ar"),
    )

    assert result.error_message is None
    assert result.metadata["language"] == "ar-AE"
    assert base64.b64decode(result.metadata["audio_base64"]) == b"hello-voice"
