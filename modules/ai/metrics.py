"""
AI Metrics and Analytics for Maktaba-OS.

This module provides:
- Usage tracking and cost monitoring
- Performance metrics and analytics
- Quality assessment and improvement tracking
- Reporting and dashboard data
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import time
import logging
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of metrics tracked."""
    REQUEST_COUNT = "request_count"
    TOKEN_USAGE = "token_usage"
    COST = "cost"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    QUALITY_SCORE = "quality_score"


@dataclass
class MetricPoint:
    """A single metric measurement."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricSeries:
    """Time series data for a metric."""
    name: str
    metric_type: MetricType
    points: List[MetricPoint] = field(default_factory=list)
    aggregation: str = "sum"  # sum, avg, min, max

    def add_point(self, value: float, metadata: Dict[str, Any] = None) -> None:
        """Add a new data point."""
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            metadata=metadata or {}
        )
        self.points.append(point)

        # Keep only last 1000 points to prevent memory issues
        if len(self.points) > 1000:
            self.points = self.points[-1000:]

    def get_aggregated_value(self, hours: int = 24) -> float:
        """Get aggregated value for the last N hours."""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_points = [p for p in self.points if p.timestamp >= cutoff]

        if not recent_points:
            return 0.0

        values = [p.value for p in recent_points]

        if self.aggregation == "sum":
            return sum(values)
        elif self.aggregation == "avg":
            return sum(values) / len(values)
        elif self.aggregation == "min":
            return min(values)
        elif self.aggregation == "max":
            return max(values)
        else:
            return sum(values)


@dataclass
class AIMetrics:
    """Comprehensive AI usage metrics."""
    # Request metrics
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0

    # Token metrics
    total_tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    # Cost metrics
    total_cost: float = 0.0
    cost_by_provider: Dict[str, float] = field(default_factory=dict)
    cost_by_model: Dict[str, float] = field(default_factory=dict)

    # Performance metrics
    total_response_time: float = 0.0
    average_response_time: float = 0.0
    min_response_time: float = float('inf')
    max_response_time: float = 0.0

    # Quality metrics
    quality_scores: List[float] = field(default_factory=list)
    average_quality_score: float = 0.0

    # Time series data
    request_series: MetricSeries = field(default_factory=lambda: MetricSeries("requests", MetricType.REQUEST_COUNT))
    token_series: MetricSeries = field(default_factory=lambda: MetricSeries("tokens", MetricType.TOKEN_USAGE))
    cost_series: MetricSeries = field(default_factory=lambda: MetricSeries("cost", MetricType.COST))
    response_time_series: MetricSeries = field(default_factory=lambda: MetricSeries("response_time", MetricType.RESPONSE_TIME))

    def record_request(
        self,
        success: bool,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0.0,
        response_time: float = 0.0,
        provider: str = "",
        model: str = "",
        quality_score: Optional[float] = None
    ) -> None:
        """Record a completed AI request."""
        self.total_requests += 1

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        # Token tracking
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.total_tokens_used += input_tokens + output_tokens

        # Cost tracking
        self.total_cost += cost
        if provider:
            self.cost_by_provider[provider] = self.cost_by_provider.get(provider, 0.0) + cost
        if model:
            self.cost_by_model[model] = self.cost_by_model.get(model, 0.0) + cost

        # Performance tracking
        if response_time > 0:
            self.total_response_time += response_time
            self.average_response_time = self.total_response_time / self.total_requests
            self.min_response_time = min(self.min_response_time, response_time)
            self.max_response_time = max(self.max_response_time, response_time)

        # Quality tracking
        if quality_score is not None:
            self.quality_scores.append(quality_score)
            self.average_quality_score = sum(self.quality_scores) / len(self.quality_scores)

        # Update time series
        self.request_series.add_point(1.0, {"success": success, "provider": provider, "model": model})
        if input_tokens + output_tokens > 0:
            self.token_series.add_point(input_tokens + output_tokens, {"provider": provider, "model": model})
        if cost > 0:
            self.cost_series.add_point(cost, {"provider": provider, "model": model})
        if response_time > 0:
            self.response_time_series.add_point(response_time, {"provider": provider, "model": model})

    @property
    def error_rate(self) -> float:
        """Calculate current error rate."""
        return self.failed_requests / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def tokens_per_request(self) -> float:
        """Calculate average tokens per request."""
        return self.total_tokens_used / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def cost_per_request(self) -> float:
        """Calculate average cost per request."""
        return self.total_cost / self.total_requests if self.total_requests > 0 else 0.0

    def get_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get a summary of metrics for the last N hours."""
        return {
            "period_hours": hours,
            "requests": {
                "total": self.request_series.get_aggregated_value(hours),
                "successful": self.successful_requests,
                "failed": self.failed_requests,
                "error_rate": self.error_rate
            },
            "tokens": {
                "total": self.token_series.get_aggregated_value(hours),
                "input": self.input_tokens,
                "output": self.output_tokens,
                "per_request": self.tokens_per_request
            },
            "cost": {
                "total": self.cost_series.get_aggregated_value(hours),
                "per_request": self.cost_per_request,
                "by_provider": dict(self.cost_by_provider),
                "by_model": dict(self.cost_by_model)
            },
            "performance": {
                "avg_response_time": self.average_response_time,
                "min_response_time": self.min_response_time if self.min_response_time != float('inf') else 0.0,
                "max_response_time": self.max_response_time
            },
            "quality": {
                "average_score": self.average_quality_score,
                "total_scores": len(self.quality_scores)
            }
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.total_tokens_used = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_cost = 0.0
        self.cost_by_provider.clear()
        self.cost_by_model.clear()
        self.total_response_time = 0.0
        self.average_response_time = 0.0
        self.min_response_time = float('inf')
        self.max_response_time = 0.0
        self.quality_scores.clear()
        self.average_quality_score = 0.0

        # Reset time series
        self.request_series.points.clear()
        self.token_series.points.clear()
        self.cost_series.points.clear()
        self.response_time_series.points.clear()


class MetricsAggregator:
    """
    Aggregates metrics across multiple AI agents and services.

    Provides global insights and analytics across the entire AI infrastructure.
    """

    def __init__(self):
        self.agent_metrics: Dict[str, AIMetrics] = {}
        self.service_metrics: Dict[str, AIMetrics] = {}
        self.global_metrics = AIMetrics()

    def register_agent(self, agent_id: str) -> AIMetrics:
        """Register a new agent for metrics tracking."""
        if agent_id not in self.agent_metrics:
            self.agent_metrics[agent_id] = AIMetrics()
        return self.agent_metrics[agent_id]

    def register_service(self, service_id: str) -> AIMetrics:
        """Register a new service for metrics tracking."""
        if service_id not in self.service_metrics:
            self.service_metrics[service_id] = AIMetrics()
        return self.service_metrics[service_id]

    def record_global_request(self, **kwargs) -> None:
        """Record a request in global metrics."""
        self.global_metrics.record_request(**kwargs)

    def get_global_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get global metrics summary."""
        summary = self.global_metrics.get_summary(hours)
        summary["agents"] = {aid: metrics.get_summary(hours) for aid, metrics in self.agent_metrics.items()}
        summary["services"] = {sid: metrics.get_summary(hours) for sid, metrics in self.service_metrics.items()}
        return summary

    def get_cost_analysis(self) -> Dict[str, Any]:
        """Get detailed cost analysis across all components."""
        total_cost = self.global_metrics.total_cost
        agent_costs = {aid: metrics.total_cost for aid, metrics in self.agent_metrics.items()}
        service_costs = {sid: metrics.total_cost for sid, metrics in self.service_metrics.items()}

        return {
            "total_cost": total_cost,
            "agent_costs": agent_costs,
            "service_costs": service_costs,
            "cost_distribution": {
                "agents_percent": sum(agent_costs.values()) / total_cost * 100 if total_cost > 0 else 0,
                "services_percent": sum(service_costs.values()) / total_cost * 100 if total_cost > 0 else 0
            }
        }

    def get_performance_analysis(self) -> Dict[str, Any]:
        """Get performance analysis across all components."""
        return {
            "global_performance": {
                "avg_response_time": self.global_metrics.average_response_time,
                "error_rate": self.global_metrics.error_rate,
                "requests_per_second": self.global_metrics.total_requests / max(1, self.global_metrics.total_response_time)
            },
            "agent_performance": {
                aid: {
                    "avg_response_time": metrics.average_response_time,
                    "error_rate": metrics.error_rate,
                    "total_requests": metrics.total_requests
                }
                for aid, metrics in self.agent_metrics.items()
            },
            "service_performance": {
                sid: {
                    "avg_response_time": metrics.average_response_time,
                    "error_rate": metrics.error_rate,
                    "total_requests": metrics.total_requests
                }
                for sid, metrics in self.service_metrics.items()
            }
        }


# Global metrics aggregator instance
metrics_aggregator = MetricsAggregator()