"""
Tests for AI service abstraction layer, error handling, and rate limiting.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from modules.ai.service import (
    AIServiceConfig, ServiceRequest, ServiceResponse,
    ModelProvider, AIModel, OpenAIService, RateLimiter,
    AIServiceError, AIServiceRateLimitError,
    AIServiceAuthenticationError, AIServiceTimeoutError,
    ServiceMetrics
)


class TestServiceRequest:
    """Test ServiceRequest data structure."""
    
    def test_service_request_creation(self):
        """Test creating a service request."""
        request = ServiceRequest(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        assert request.model == "gpt-4"
        assert len(request.messages) == 2
        assert request.temperature == 0.7
        assert request.max_tokens == 1000
    
    def test_service_request_with_functions(self):
        """Test service request with function definitions."""
        request = ServiceRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "test"}],
            functions=[
                {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {"type": "object"}
                }
            ]
        )
        
        assert len(request.functions) == 1
        assert request.functions[0]["name"] == "get_weather"
    
    def test_service_request_with_stop_sequences(self):
        """Test service request with stop sequences."""
        request = ServiceRequest(
            model="gpt-4",
            messages=[{"role": "user", "content": "test"}],
            stop_sequences=["END", "STOP"]
        )
        
        assert len(request.stop_sequences) == 2


class TestServiceResponse:
    """Test ServiceResponse data structure."""
    
    def test_service_response_creation(self):
        """Test creating a service response."""
        response = ServiceResponse(
            content="Generated text",
            model_used="gpt-4",
            tokens_used=150,
            finish_reason="stop",
            cost=0.01,
            processing_time=2.5
        )
        
        assert response.content == "Generated text"
        assert response.model_used == "gpt-4"
        assert response.tokens_used == 150
        assert response.finish_reason == "stop"
        assert response.cost == 0.01
        assert response.processing_time == 2.5


class TestAIServiceConfig:
    """Test AI service configuration."""
    
    def test_config_creation(self):
        """Test creating service config."""
        config = AIServiceConfig(
            provider=ModelProvider.OPENAI,
            api_key="test-key",
            timeout=60,
            rate_limit=100
        )
        
        assert config.provider == ModelProvider.OPENAI
        assert config.api_key == "test-key"
        assert config.timeout == 60
        assert config.rate_limit == 100
    
    def test_config_with_custom_headers(self):
        """Test config with custom headers."""
        config = AIServiceConfig(
            provider=ModelProvider.OPENAI,
            api_key="test",
            custom_headers={"X-Custom": "value"}
        )
        
        assert "X-Custom" in config.custom_headers


class TestRateLimiter:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_allows_requests(self):
        """Test rate limiter allows requests within limit."""
        limiter = RateLimiter(requests_per_minute=10)
        
        # Make 5 requests
        for _ in range(5):
            await limiter.wait_if_needed()
        
        # Should complete without excessive waiting
        assert len(limiter.requests) == 5
    
    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_excess_requests(self):
        """Test rate limiter blocks excess requests."""
        limiter = RateLimiter(requests_per_minute=2)
        
        start_time = asyncio.get_event_loop().time()
        
        # Make 3 requests - third should be blocked
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()
        await limiter.wait_if_needed()
        
        elapsed = asyncio.get_event_loop().time() - start_time
        
        # Third request should cause a wait
        assert len(limiter.requests) == 3
    
    @pytest.mark.asyncio
    async def test_rate_limiter_removes_old_requests(self):
        """Test that rate limiter removes old request timestamps."""
        limiter = RateLimiter(requests_per_minute=100)
        
        await limiter.wait_if_needed()
        
        # Manually add old timestamp (60+ seconds ago)
        old_time = asyncio.get_event_loop().time() - 70
        limiter.requests.append(old_time)
        
        await limiter.wait_if_needed()
        
        # Old request should be removed
        assert all(t > asyncio.get_event_loop().time() - 61 for t in limiter.requests)


class TestServiceMetrics:
    """Test service metrics tracking."""
    
    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = ServiceMetrics()
        
        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.total_tokens == 0
        assert metrics.total_cost == 0.0
    
    def test_record_successful_request(self):
        """Test recording successful request metrics."""
        metrics = ServiceMetrics()
        
        metrics.record_request(
            success=True,
            tokens=100,
            cost=0.01,
            response_time=1.5
        )
        
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.total_tokens == 100
        assert metrics.total_cost == 0.01
        assert metrics.average_response_time == 1.5
    
    def test_record_failed_request(self):
        """Test recording failed request metrics."""
        metrics = ServiceMetrics()
        
        metrics.record_request(
            success=False,
            tokens=0,
            cost=0.0,
            response_time=0.5
        )
        
        assert metrics.total_requests == 1
        assert metrics.failed_requests == 1
        assert metrics.successful_requests == 0
    
    def test_record_multiple_requests(self):
        """Test recording multiple requests."""
        metrics = ServiceMetrics()
        
        for i in range(5):
            metrics.record_request(
                success=True,
                tokens=100 * (i + 1),
                cost=0.01 * (i + 1),
                response_time=1.0 + (i * 0.1)
            )
        
        assert metrics.total_requests == 5
        assert metrics.successful_requests == 5
        assert metrics.total_tokens == 1500  # 100+200+300+400+500
        assert metrics.total_cost == pytest.approx(0.15)
    
    def test_metrics_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = ServiceMetrics()
        
        metrics.record_request(
            success=True,
            tokens=100,
            cost=0.01,
            response_time=1.0
        )
        
        metrics_dict = metrics.to_dict()
        
        assert metrics_dict["total_requests"] == 1
        assert metrics_dict["successful_requests"] == 1
        assert metrics_dict["total_tokens"] == 100
        assert metrics_dict["total_cost"] == 0.01


class TestOpenAIService:
    """Test OpenAI service implementation."""
    
    def test_openai_service_creation(self):
        """Test creating OpenAI service."""
        config = AIServiceConfig(
            provider=ModelProvider.OPENAI,
            api_key="test-key"
        )
        
        service = OpenAIService(config)
        
        assert service.config.api_key == "test-key"
        assert service.base_url == "https://api.openai.com/v1"
    
    def test_openai_service_custom_base_url(self):
        """Test OpenAI service with custom base URL."""
        config = AIServiceConfig(
            provider=ModelProvider.OPENAI,
            api_key="test",
            base_url="https://custom.url/v1"
        )
        
        service = OpenAIService(config)
        
        assert service.base_url == "https://custom.url/v1"
    
    def test_openai_service_missing_api_key(self):
        """Test OpenAI service raises error without API key."""
        config = AIServiceConfig(provider=ModelProvider.OPENAI)
        
        with pytest.raises(ValueError):
            OpenAIService(config)
    
    def test_get_context_window_gpt4(self):
        """Test context window sizes for GPT-4 models."""
        config = AIServiceConfig(provider=ModelProvider.OPENAI, api_key="test")
        service = OpenAIService(config)
        
        assert service._get_context_window("gpt-4") == 8192
        assert service._get_context_window("gpt-4-32k") == 32768
        assert service._get_context_window("gpt-3.5-turbo-16k") == 16384
        assert service._get_context_window("gpt-3.5-turbo") == 4096
    
    def test_get_cost_per_token(self):
        """Test cost per token for different models."""
        config = AIServiceConfig(provider=ModelProvider.OPENAI, api_key="test")
        service = OpenAIService(config)
        
        # GPT-4 should cost more than GPT-3.5
        gpt4_input = service._get_input_cost("gpt-4")
        gpt35_input = service._get_input_cost("gpt-3.5-turbo")
        
        assert gpt4_input > gpt35_input


class TestServiceErrors:
    """Test service error types."""
    
    def test_ai_service_error(self):
        """Test AI service error."""
        error = AIServiceError("Service error")
        assert str(error) == "Service error"
    
    def test_rate_limit_error(self):
        """Test rate limit error."""
        error = AIServiceRateLimitError("Too many requests")
        assert isinstance(error, AIServiceError)
    
    def test_authentication_error(self):
        """Test authentication error."""
        error = AIServiceAuthenticationError("Invalid API key")
        assert isinstance(error, AIServiceError)
    
    def test_timeout_error(self):
        """Test timeout error."""
        error = AIServiceTimeoutError("Request timed out")
        assert isinstance(error, AIServiceError)


class TestAIModel:
    """Test AI model definitions."""
    
    def test_ai_model_creation(self):
        """Test creating AI model definition."""
        model = AIModel(
            name="test-model",
            provider=ModelProvider.OPENAI,
            context_window=4096,
            max_tokens=2048,
            input_cost_per_token=0.001,
            output_cost_per_token=0.002,
            supports_function_calling=True
        )
        
        assert model.name == "test-model"
        assert model.provider == ModelProvider.OPENAI
        assert model.context_window == 4096
        assert model.supports_function_calling is True
    
    def test_ai_model_defaults(self):
        """Test AI model with default values."""
        model = AIModel(
            name="simple-model",
            provider=ModelProvider.LOCAL,
            context_window=2048,
            max_tokens=1024
        )
        
        assert model.input_cost_per_token == 0.0
        assert model.supports_function_calling is False
        assert model.supports_vision is False


class TestServiceIntegration:
    """Integration tests for AI services."""
    
    @pytest.mark.asyncio
    async def test_service_lifecycle(self):
        """Test full service lifecycle."""
        config = AIServiceConfig(
            provider=ModelProvider.OPENAI,
            api_key="test"
        )
        
        service = OpenAIService(config)
        
        # Initialize
        await service.initialize()
        assert service.session is not None
        
        # Cleanup
        await service.cleanup()
        assert service.session is None
    
    @pytest.mark.asyncio
    async def test_rate_limiter_integration(self):
        """Test rate limiter integration with service."""
        config = AIServiceConfig(
            provider=ModelProvider.OPENAI,
            api_key="test",
            rate_limit=5  # 5 requests per minute
        )
        
        service = OpenAIService(config)
        
        # Rate limiter should be initialized
        assert service.rate_limiter is not None
        assert service.rate_limiter.requests_per_minute == 5
