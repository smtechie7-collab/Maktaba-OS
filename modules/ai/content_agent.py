"""
Content Generation AI Agent.

This agent specializes in:
- Content creation and expansion
- Writing assistance and suggestions
- Style consistency checking
- Multilingual content generation
"""

import os
from typing import Dict, List, Optional, Any
import logging
from .agent import AIAgent, AgentConfig, AgentContext, AgentResponse, AgentCapability, AgentStatus
from .service import AIService, AIServiceConfig, OpenAIService, ServiceRequest, ServiceResponse, ModelProvider
from .metrics import metrics_aggregator

logger = logging.getLogger(__name__)


class OpenAIDevelopmentService(AIService):
    """Fallback OpenAI-style service used when no API key is available."""

    def __init__(self, config: AIServiceConfig):
        super().__init__(config)

    async def generate_text(self, request: ServiceRequest) -> ServiceResponse:
        return ServiceResponse(
            content="",
            model_used=request.model,
            tokens_used=0,
            finish_reason="error",
            metadata={"error": "No OpenAI API key provided."},
            cost=0.0,
            processing_time=0.0,
        )

    async def list_models(self) -> List[Any]:
        return []

    async def check_health(self) -> bool:
        return False


class ContentGenerationAgent(AIAgent):
    """
    AI agent specialized in content generation and writing assistance.

    Capabilities:
    - Generate content based on topics or outlines
    - Expand existing content
    - Provide writing suggestions and improvements
    - Maintain style consistency
    - Support multilingual content creation
    """

    def __init__(self, config: AgentConfig, ai_service: AIService):
        super().__init__(config)
        self.ai_service = ai_service
        self.metrics = metrics_aggregator.register_agent(f"content_gen_{config.name}")

    async def _validate_config(self) -> None:
        """Validate agent configuration."""
        if AgentCapability.TEXT_GENERATION not in self.config.capabilities:
            raise ValueError("ContentGenerationAgent requires TEXT_GENERATION capability")

        # Validate model supports text generation
        if not self.ai_service:
            raise ValueError("AI service is required for ContentGenerationAgent")

    async def _initialize_models(self) -> None:
        """Initialize AI models."""
        # Test service availability
        is_healthy = await self.ai_service.check_health()
        if not is_healthy:
            raise RuntimeError(f"AI service is not healthy: {self.config.model_provider}")

    async def _setup_monitoring(self) -> None:
        """Set up monitoring and metrics."""
        logger.info(f"ContentGenerationAgent {self.name} monitoring enabled")

    async def process(self, input_data: Dict[str, Any], context: AgentContext) -> AgentResponse:
        """Process content generation requests."""
        start_time = __import__('time').time()

        if self.status != AgentStatus.READY:
            error_message = f"Agent {self.name} is not ready. Initialize before processing."
            logger.warning(error_message)
            processing_time = __import__('time').time() - start_time
            self.metrics.record_request(
                success=False,
                input_tokens=0,
                output_tokens=0,
                cost=0.0,
                response_time=processing_time,
                provider=self.config.model_provider,
                model=self.config.model_name,
                quality_score=0.0,
            )
            return AgentResponse(
                content="",
                error_message=error_message,
                processing_time=processing_time,
            )

        try:
            task_type = input_data.get("task_type", "generate")
            content = input_data.get("content", "")
            topic = input_data.get("topic", "")
            language = input_data.get("language", context.language)
            style = input_data.get("style", "academic")
            length = input_data.get("length", "medium")

            # Build prompt based on task type
            prompt = self._build_prompt(task_type, content, topic, language, style, length)

            # Create service request
            request = ServiceRequest(
                model=self.config.model_name,
                messages=[
                    {"role": "system", "content": self._get_system_prompt(language, style)},
                    {"role": "user", "content": prompt}
                ],
                temperature=self._get_temperature_for_task(task_type),
                max_tokens=self._get_max_tokens_for_length(length)
            )

            # Generate content
            response = await self.ai_service.generate_text(request)

            # Record metrics
            self.metrics.record_request(
                success=True,
                input_tokens=response.tokens_used // 2,  # Estimate
                output_tokens=response.tokens_used // 2,
                cost=response.cost,
                response_time=response.processing_time,
                provider=self.config.model_provider,
                model=self.config.model_name,
                quality_score=self._assess_quality(response.content)
            )

            processing_time = __import__('time').time() - start_time

            return AgentResponse(
                content=response.content,
                metadata={
                    "task_type": task_type,
                    "language": language,
                    "style": style,
                    "model_used": response.model_used,
                    "tokens_used": response.tokens_used,
                    "cost": response.cost
                },
                tokens_used=response.tokens_used,
                processing_time=processing_time,
                model_used=response.model_used
            )

        except Exception as e:
            logger.error(f"Content generation failed: {e}")

            # Record failed request
            processing_time = __import__('time').time() - start_time
            self.metrics.record_request(
                success=False,
                response_time=processing_time,
                provider=self.config.model_provider,
                model=self.config.model_name
            )

            return AgentResponse(
                content="",
                error_message=str(e),
                processing_time=processing_time
            )

    def _build_prompt(self, task_type: str, content: str, topic: str, language: str, style: str, length: str) -> str:
        """Build the appropriate prompt based on task type."""
        prompts = {
            "generate": f"Write a {length} {style} article about: {topic}",
            "expand": f"Expand the following content while maintaining its style and adding relevant details:\n\n{content}",
            "summarize": f"Summarize the following content in a {length} format:\n\n{content}",
            "rewrite": f"Rewrite the following content in a {style} style:\n\n{content}",
            "outline": f"Create a detailed outline for an article about: {topic}",
            "title": f"Generate compelling titles for content about: {topic}",
            "introduction": f"Write an engaging introduction for an article about: {topic}",
            "conclusion": f"Write a strong conclusion for the following content:\n\n{content}"
        }

        base_prompt = prompts.get(task_type, prompts["generate"])

        # Add language specification if not English
        if language != "en":
            lang_names = {
                "ar": "Arabic", "ur": "Urdu", "gu": "Gujarati", "hi": "Hindi",
                "fa": "Persian", "bn": "Bengali", "pa": "Punjabi"
            }
            lang_name = lang_names.get(language, language.upper())
            base_prompt += f"\n\nRespond in {lang_name} language."

        return base_prompt

    def _get_system_prompt(self, language: str, style: str) -> str:
        """Get the system prompt for content generation."""
        base_prompt = f"""You are an expert content creator specializing in {style} writing.
Focus on creating high-quality, engaging content that is well-structured and informative.
Ensure the content is original, accurate, and follows best practices for {style} writing."""

        if language != "en":
            lang_names = {
                "ar": "Arabic", "ur": "Urdu", "gu": "Gujarati", "hi": "Hindi",
                "fa": "Persian", "bn": "Bengali", "pa": "Punjabi"
            }
            lang_name = lang_names.get(language, language.upper())
            base_prompt += f"\n\nYou must respond in {lang_name} language only."

        return base_prompt

    def _get_temperature_for_task(self, task_type: str) -> float:
        """Get appropriate temperature for different task types."""
        temperatures = {
            "generate": 0.7,    # Creative but focused
            "expand": 0.6,      # Balanced creativity and consistency
            "summarize": 0.3,   # More deterministic
            "rewrite": 0.5,     # Moderate creativity
            "outline": 0.4,     # Structured output
            "title": 0.8,       # More creative
            "introduction": 0.7,
            "conclusion": 0.6
        }
        return temperatures.get(task_type, 0.7)

    def _get_max_tokens_for_length(self, length: str) -> int:
        """Get max tokens based on desired content length."""
        lengths = {
            "short": 500,
            "medium": 1500,
            "long": 3000,
            "xl": 5000
        }
        return lengths.get(length, 1500)

    def _assess_quality(self, content: str) -> float:
        """Simple quality assessment of generated content."""
        if not content or len(content.strip()) < 50:
            return 0.0

        score = 0.5  # Base score

        # Length appropriateness
        word_count = len(content.split())
        if 100 <= word_count <= 2000:
            score += 0.2

        # Structure indicators
        if any(indicator in content.lower() for indicator in ["introduction", "conclusion", "summary"]):
            score += 0.1

        # Readability (sentence length variation)
        sentences = content.split('.')
        if len(sentences) > 3:
            avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
            if 10 <= avg_sentence_length <= 25:
                score += 0.2

        return min(score, 1.0)


# Factory function to create content generation agents
def create_content_generation_agent(
    name: str = "content_writer",
    model_provider: ModelProvider = ModelProvider.OPENAI,
    model_name: str = "gpt-4",
    api_key: Optional[str] = None
) -> ContentGenerationAgent:
    """Create a content generation agent with default configuration."""

    # Allow environment override for OpenAI API key.
    resolved_api_key = api_key or os.environ.get("OPENAI_API_KEY")

    service_config = AIServiceConfig(
        provider=model_provider,
        api_key=resolved_api_key,
    )

    # Create AI service
    if model_provider == ModelProvider.OPENAI:
        if resolved_api_key:
            ai_service = OpenAIService(service_config)
        else:
            ai_service = OpenAIDevelopmentService(service_config)
    else:
        raise ValueError(f"Unsupported provider: {model_provider}")

    # Create agent config
    agent_config = AgentConfig(
        name=name,
        description="AI-powered content generation and writing assistance",
        capabilities=[AgentCapability.TEXT_GENERATION, AgentCapability.EDITING],
        model_provider=model_provider.value,
        model_name=model_name,
        temperature=0.7,
        max_tokens=2048
    )

    return ContentGenerationAgent(agent_config, ai_service)