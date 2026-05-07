"""
AI Agent Architecture for Maktaba-OS.

This module implements a modular AI agent system with:
- Plugin-based architecture for extensibility
- Configurable agent behaviors and capabilities
- Context-aware processing and memory management
- Error handling and fallback mechanisms
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentCapability(Enum):
    """Capabilities that AI agents can have."""
    TEXT_GENERATION = "text_generation"
    TEXT_ANALYSIS = "text_analysis"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    EDITING = "editing"
    REVIEW = "review"
    RESEARCH = "research"
    CREATIVE_WRITING = "creative_writing"


class AgentStatus(Enum):
    """Agent operational status."""
    INITIALIZING = "initializing"
    READY = "ready"
    BUSY = "busy"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class AgentConfig:
    """Configuration for AI agents."""
    name: str
    description: str
    capabilities: List[AgentCapability]
    model_provider: str
    model_name: str
    temperature: float = 0.7
    max_tokens: int = 2048
    context_window: int = 4096
    rate_limit: int = 60  # requests per minute
    timeout: int = 30  # seconds
    retry_attempts: int = 3
    fallback_models: List[str] = field(default_factory=list)
    custom_parameters: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.capabilities:
            raise ValueError("Agent must have at least one capability")


@dataclass
class AgentContext:
    """Context information for agent operations."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    document_id: Optional[str] = None
    language: str = "en"
    domain: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentResponse:
    """Response from an AI agent operation."""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    tokens_used: int = 0
    processing_time: float = 0.0
    model_used: str = ""
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


class AIAgent(ABC):
    """
    Base class for AI agents in Maktaba-OS.

    Agents are specialized AI-powered components that can perform specific
    tasks like content generation, translation, analysis, etc.
    """

    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.INITIALIZING
        self.last_activity = datetime.now()
        self.metrics = AgentMetrics()

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def capabilities(self) -> List[AgentCapability]:
        return self.config.capabilities

    async def initialize(self) -> bool:
        """Initialize the agent and its dependencies."""
        try:
            # Validate configuration
            await self._validate_config()

            # Initialize model connections
            await self._initialize_models()

            # Set up monitoring and metrics
            await self._setup_monitoring()

            self.status = AgentStatus.READY
            logger.info(f"Agent {self.name} initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize agent {self.name}: {e}")
            self.status = AgentStatus.ERROR
            return False

    @abstractmethod
    async def process(self, input_data: Dict[str, Any], context: AgentContext) -> AgentResponse:
        """
        Process input data and return an AI-generated response.

        Args:
            input_data: The input data to process
            context: Contextual information for the operation

        Returns:
            AgentResponse with the generated content and metadata
        """
        pass

    async def is_available(self) -> bool:
        """Check if the agent is available for processing."""
        return self.status == AgentStatus.READY

    async def get_status(self) -> Dict[str, Any]:
        """Get detailed status information about the agent."""
        return {
            "name": self.name,
            "status": self.status.value,
            "capabilities": [cap.value for cap in self.capabilities],
            "last_activity": self.last_activity.isoformat(),
            "metrics": self.metrics.to_dict()
        }

    async def shutdown(self) -> None:
        """Clean up agent resources."""
        self.status = AgentStatus.DISABLED
        logger.info(f"Agent {self.name} shut down")

    # Abstract methods for subclasses to implement
    @abstractmethod
    async def _validate_config(self) -> None:
        """Validate agent configuration."""
        pass

    @abstractmethod
    async def _initialize_models(self) -> None:
        """Initialize AI model connections."""
        pass

    @abstractmethod
    async def _setup_monitoring(self) -> None:
        """Set up monitoring and metrics collection."""
        pass


@dataclass
class AgentMetrics:
    """Metrics tracking for AI agents."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_tokens_used: int = 0
    average_response_time: float = 0.0
    error_rate: float = 0.0

    def record_request(self, success: bool, tokens_used: int, response_time: float) -> None:
        """Record a request and update metrics."""
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        self.total_tokens_used += tokens_used
        self.average_response_time = (
            (self.average_response_time * (self.total_requests - 1) + response_time) /
            self.total_requests
        )
        self.error_rate = self.failed_requests / self.total_requests if self.total_requests > 0 else 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "total_tokens_used": self.total_tokens_used,
            "average_response_time": round(self.average_response_time, 3),
            "error_rate": round(self.error_rate, 3)
        }