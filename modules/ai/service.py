"""
AI Service Abstraction Layer for Maktaba-OS.

This module provides a unified interface for different AI service providers:
- OpenAI (GPT models)
- Anthropic (Claude models)
- Local models (Ollama, LM Studio)
- Model management with automatic fallback and load balancing
- Token usage tracking and cost optimization
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import asyncio
import aiohttp
import json
import logging
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class ModelProvider(Enum):
    """Supported AI model providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"
    HUGGINGFACE = "huggingface"
    CUSTOM = "custom"


@dataclass
class AIModel:
    """Represents an AI model configuration."""
    name: str
    provider: ModelProvider
    context_window: int
    max_tokens: int
    input_cost_per_token: float = 0.0  # USD per token
    output_cost_per_token: float = 0.0  # USD per token
    supports_function_calling: bool = False
    supports_vision: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AIServiceConfig:
    """Configuration for AI service providers."""
    provider: ModelProvider
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    rate_limit: int = 60  # requests per minute
    models: List[AIModel] = field(default_factory=list)
    custom_headers: Dict[str, str] = field(default_factory=dict)


@dataclass
class ServiceRequest:
    """Request to an AI service."""
    model: str
    messages: List[Dict[str, Any]]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    stop_sequences: List[str] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ServiceResponse:
    """Response from an AI service."""
    content: str
    model_used: str
    tokens_used: int
    finish_reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    cost: float = 0.0
    processing_time: float = 0.0


@dataclass
class AudioRequest:
    """Request to generate audio from text."""
    model: str
    input_text: str
    voice: str = "alloy"
    language: str = "en-US"
    format: str = "wav"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioResponse:
    """Response from an audio generation request."""
    audio_data: bytes
    content_type: str
    model_used: str
    duration_seconds: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    cost: float = 0.0


class AIServiceError(Exception):
    """Base exception for AI service errors."""
    pass


class AIServiceRateLimitError(AIServiceError):
    """Rate limit exceeded error."""
    pass


class AIServiceAuthenticationError(AIServiceError):
    """Authentication failed error."""
    pass


class AIServiceTimeoutError(AIServiceError):
    """Request timeout error."""
    pass


class AIService(ABC):
    """
    Abstract base class for AI service providers.

    This provides a unified interface for different AI services,
    handling authentication, rate limiting, and error management.
    """

    def __init__(self, config: AIServiceConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimiter(config.rate_limit)
        self.metrics = ServiceMetrics()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()

    async def initialize(self) -> None:
        """Initialize the service connection."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.config.timeout),
                headers=self._get_default_headers()
            )
        logger.info(f"Initialized {self.config.provider.value} service")

    async def cleanup(self) -> None:
        """Clean up service resources."""
        if self.session:
            await self.session.close()
            self.session = None

    @abstractmethod
    async def generate_text(self, request: ServiceRequest) -> ServiceResponse:
        """Generate text using the AI service."""
        pass

    async def generate_audio(self, request: AudioRequest) -> AudioResponse:
        """Generate audio using the AI service."""
        raise NotImplementedError("Audio generation is not implemented for this provider")

    @abstractmethod
    async def list_models(self) -> List[AIModel]:
        """List available models for this service."""
        pass

    async def check_health(self) -> bool:
        """Check if the service is healthy and accessible."""
        try:
            models = await self.list_models()
            return len(models) > 0
        except Exception as e:
            logger.error(f"Health check failed for {self.config.provider.value}: {e}")
            return False

    def _get_default_headers(self) -> Dict[str, str]:
        """Get default headers for API requests."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Maktaba-OS/1.0"
        }
        headers.update(self.config.custom_headers)
        return headers

    def _calculate_cost(self, model: AIModel, input_tokens: int, output_tokens: int) -> float:
        """Calculate the cost of a request."""
        return (
            input_tokens * model.input_cost_per_token +
            output_tokens * model.output_cost_per_token
        )


class OpenAIService(AIService):
    """OpenAI API service implementation."""

    def __init__(self, config: AIServiceConfig):
        super().__init__(config)
        if not config.api_key:
            raise ValueError("OpenAI API key is required")
        self.base_url = config.base_url or "https://api.openai.com/v1"

    def _get_default_headers(self) -> Dict[str, str]:
        headers = super()._get_default_headers()
        headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    async def generate_text(self, request: ServiceRequest) -> ServiceResponse:
        """Generate text using OpenAI API."""
        await self.rate_limiter.wait_if_needed()

        payload = {
            "model": request.model,
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "top_p": request.top_p,
            "frequency_penalty": request.frequency_penalty,
            "presence_penalty": request.presence_penalty,
            "stop": request.stop_sequences if request.stop_sequences else None,
        }

        if request.functions:
            payload["functions"] = request.functions

        start_time = time.time()

        try:
            async with self.session.post(
                f"{self.base_url}/chat/completions",
                json=payload
            ) as response:
                if response.status == 429:
                    raise AIServiceRateLimitError("Rate limit exceeded")
                elif response.status == 401:
                    raise AIServiceAuthenticationError("Invalid API key")
                elif response.status != 200:
                    raise AIServiceError(f"API error: {response.status}")

                data = await response.json()
                processing_time = time.time() - start_time

                choice = data["choices"][0]
                usage = data.get("usage", {})

                # Find model info for cost calculation
                model_info = next(
                    (m for m in self.config.models if m.name == request.model),
                    None
                )

                cost = 0.0
                if model_info:
                    cost = self._calculate_cost(
                        model_info,
                        usage.get("prompt_tokens", 0),
                        usage.get("completion_tokens", 0)
                    )

                return ServiceResponse(
                    content=choice["message"]["content"],
                    model_used=request.model,
                    tokens_used=usage.get("total_tokens", 0),
                    finish_reason=choice.get("finish_reason", "unknown"),
                    metadata={"usage": usage},
                    cost=cost,
                    processing_time=processing_time
                )

        except asyncio.TimeoutError:
            raise AIServiceTimeoutError("Request timed out")
        except aiohttp.ClientError as e:
            raise AIServiceError(f"Network error: {e}")

    async def generate_audio(self, request: AudioRequest) -> AudioResponse:
        """Generate speech audio using the OpenAI audio endpoint."""
        await self.rate_limiter.wait_if_needed()

        payload = {
            "model": request.model,
            "voice": request.voice,
            "input": request.input_text,
        }
        if request.language:
            payload["language"] = request.language

        start_time = time.time()
        async with self.session.post(
            f"{self.base_url}/audio/speech",
            json=payload
        ) as response:
            if response.status == 429:
                raise AIServiceRateLimitError("Rate limit exceeded")
            elif response.status == 401:
                raise AIServiceAuthenticationError("Invalid API key")
            elif response.status != 200:
                body = await response.text()
                raise AIServiceError(f"Audio API error: {response.status} - {body}")

            audio_bytes = await response.read()
            processing_time = time.time() - start_time
            content_type = response.headers.get("Content-Type", "application/octet-stream")

            return AudioResponse(
                audio_data=audio_bytes,
                content_type=content_type,
                model_used=request.model,
                duration_seconds=None,
                metadata={"request": payload, "processing_time": processing_time},
                cost=0.0
            )

    async def list_models(self) -> List[AIModel]:
        """List available OpenAI models."""
        try:
            async with self.session.get(f"{self.base_url}/models") as response:
                if response.status == 200:
                    data = await response.json()
                    return [
                        AIModel(
                            name=model["id"],
                            provider=ModelProvider.OPENAI,
                            context_window=self._get_context_window(model["id"]),
                            max_tokens=self._get_max_tokens(model["id"]),
                            input_cost_per_token=self._get_input_cost(model["id"]),
                            output_cost_per_token=self._get_output_cost(model["id"]),
                            supports_function_calling="gpt-4" in model["id"] or "gpt-3.5-turbo" in model["id"],
                            metadata=model
                        )
                        for model in data["data"]
                        if model["id"].startswith(("gpt-", "text-"))
                    ]
                else:
                    logger.warning(f"Failed to list OpenAI models: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error listing OpenAI models: {e}")
            return []

    def _get_context_window(self, model_name: str) -> int:
        """Get context window size for OpenAI models."""
        if "gpt-4-32k" in model_name:
            return 32768
        elif "gpt-4" in model_name:
            return 8192
        elif "gpt-3.5-turbo-16k" in model_name:
            return 16384
        else:
            return 4096

    def _get_max_tokens(self, model_name: str) -> int:
        """Get max tokens for OpenAI models."""
        return self._get_context_window(model_name) // 2

    def _get_input_cost(self, model_name: str) -> float:
        """Get input cost per token for OpenAI models."""
        costs = {
            "gpt-4-32k": 0.06 / 1000,
            "gpt-4": 0.03 / 1000,
            "gpt-3.5-turbo-16k": 0.003 / 1000,
            "gpt-3.5-turbo": 0.0015 / 1000,
        }
        return costs.get(model_name, 0.002 / 1000)

    def _get_output_cost(self, model_name: str) -> float:
        """Get output cost per token for OpenAI models."""
        costs = {
            "gpt-4-32k": 0.12 / 1000,
            "gpt-4": 0.06 / 1000,
            "gpt-3.5-turbo-16k": 0.004 / 1000,
            "gpt-3.5-turbo": 0.002 / 1000,
        }
        return costs.get(model_name, 0.004 / 1000)


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, requests_per_minute: int):
        self.requests_per_minute = requests_per_minute
        self.requests = []
        self.lock = asyncio.Lock()

    async def wait_if_needed(self) -> None:
        """Wait if rate limit would be exceeded."""
        async with self.lock:
            now = time.time()
            # Remove old requests
            self.requests = [r for r in self.requests if now - r < 60]

            if len(self.requests) >= self.requests_per_minute:
                # Wait until we can make another request
                wait_time = 60 - (now - self.requests[0])
                if wait_time > 0:
                    await asyncio.sleep(wait_time)

            self.requests.append(now)


@dataclass
class ServiceMetrics:
    """Metrics for AI service usage."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    average_response_time: float = 0.0

    def record_request(self, success: bool, tokens: int, cost: float, response_time: float) -> None:
        """Record a service request."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.total_tokens += tokens
        self.total_cost += cost
        self.average_response_time = (
            (self.average_response_time * (self.total_requests - 1) + response_time) /
            self.total_requests
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_tokens": self.total_tokens,
            "total_cost": round(self.total_cost, 4),
            "average_response_time": round(self.average_response_time, 3)
        }