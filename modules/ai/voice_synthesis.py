"""
Voice synthesis support for translation verification in Maktaba-OS.

This module adds a TTS-capable AI agent that can generate speech from translated
text and return encoded audio payloads for playback or verification.
"""

import base64
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .agent import AIAgent, AgentConfig, AgentContext, AgentResponse, AgentCapability
from .service import (
    AIService,
    AIServiceConfig,
    AudioRequest,
    AudioResponse,
    ModelProvider,
    OpenAIService,
)
from .metrics import metrics_aggregator

logger = logging.getLogger(__name__)


@dataclass
class VoiceSynthesisConfig:
    voice: str = "alloy"
    language: str = "en-US"
    audio_format: str = "wav"
    audio_model: str = "gpt-4o-mini-tts"
    voice_style: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class VoiceSynthesisAgent(AIAgent):
    """Agent that generates speech audio from translated or source text."""

    def __init__(self, config: AgentConfig, ai_service: AIService):
        super().__init__(config)
        self.ai_service = ai_service
        self.metrics = metrics_aggregator.register_agent(f"voice_synthesis_{config.name}")

    async def _validate_config(self) -> None:
        if AgentCapability.TRANSLATION not in self.config.capabilities and AgentCapability.TEXT_GENERATION not in self.config.capabilities:
            raise ValueError("VoiceSynthesisAgent requires TRANSLATION or TEXT_GENERATION capability")

        if not self.ai_service:
            raise ValueError("AI service is required for VoiceSynthesisAgent")

    async def _initialize_models(self) -> None:
        healthy = await self.ai_service.check_health()
        if not healthy:
            raise RuntimeError(f"AI service is not healthy: {self.config.model_provider}")

    async def _setup_monitoring(self) -> None:
        logger.info(f"VoiceSynthesisAgent {self.name} monitoring enabled")

    async def process(self, input_data: Dict[str, Any], context: AgentContext) -> AgentResponse:
        task_type = input_data.get("task_type", "synthesize")
        text = input_data.get("translated_text") or input_data.get("content", "")
        voice = input_data.get("voice", self.config.custom_parameters.get("voice", "alloy"))
        language = input_data.get("language", self.config.custom_parameters.get("language", "en-US"))
        audio_format = input_data.get("format", self.config.custom_parameters.get("audio_format", "wav"))
        model_name = input_data.get("model_name", self.config.model_name)

        if not text:
            return AgentResponse(content="", error_message="No text provided for voice synthesis.")

        try:
            request = AudioRequest(
                model=model_name,
                input_text=text,
                voice=voice,
                language=language,
                format=audio_format,
                metadata={
                    "task_type": task_type,
                    "source_language": input_data.get("source_language"),
                    "target_language": input_data.get("target_language"),
                },
            )
            response = await self.ai_service.generate_audio(request)
            encoded_audio = base64.b64encode(response.audio_data).decode("ascii")

            metadata = {
                "audio_base64": encoded_audio,
                "content_type": response.content_type,
                "audio_size_bytes": len(response.audio_data),
                "duration_seconds": response.duration_seconds,
                "voice": voice,
                "language": language,
                "model_used": response.model_used,
            }

            self.metrics.record_request(
                success=True,
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                response_time=response.metadata.get("processing_time", 0.0),
                provider=self.config.model_provider,
                model=response.model_used,
            )
            return AgentResponse(
                content=f"Generated audio for {task_type} in {language}.",
                metadata=metadata,
                model_used=response.model_used,
                tokens_used=0,
                processing_time=response.metadata.get("processing_time", 0.0),
            )

        except Exception as exc:
            logger.error(f"VoiceSynthesisAgent failed: {exc}")
            self.metrics.record_request(
                success=False,
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                response_time=0.0,
                provider=self.config.model_provider,
                model=self.config.model_name,
            )
            return AgentResponse(content="", error_message=str(exc))


def create_voice_synthesis_agent(
    name: str = "voice_synthesizer",
    model_provider: Any = None,
    model_name: str = "gpt-4o-mini-tts",
    api_key: Optional[str] = None,
) -> VoiceSynthesisAgent:
    provider = model_provider or ModelProvider.OPENAI
    if not isinstance(provider, ModelProvider):
        provider = ModelProvider(provider)

    service_config = AIServiceConfig(
        provider=provider,
        api_key=api_key,
    )

    if provider == ModelProvider.OPENAI:
        ai_service = OpenAIService(service_config)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    agent_config = AgentConfig(
        name=name,
        description="AI voice synthesis agent for translation verification",
        capabilities=[AgentCapability.TRANSLATION],
        model_provider=provider.value,
        model_name=model_name,
        temperature=0.3,
        max_tokens=0,
    )

    return VoiceSynthesisAgent(agent_config, ai_service)
