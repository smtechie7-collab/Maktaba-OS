"""
AI Model Definitions and Provider Management.

This module defines available AI models and provides utilities for
model selection, fallback management, and provider configuration.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from .service import ModelProvider, AIModel


# Pre-defined AI models for different providers
OPENAI_MODELS = [
    AIModel(
        name="gpt-4",
        provider=ModelProvider.OPENAI,
        context_window=8192,
        max_tokens=4096,
        input_cost_per_token=0.00003,
        output_cost_per_token=0.00006,
        supports_function_calling=True,
        metadata={"description": "Most capable GPT-4 model"}
    ),
    AIModel(
        name="gpt-4-32k",
        provider=ModelProvider.OPENAI,
        context_window=32768,
        max_tokens=16384,
        input_cost_per_token=0.00006,
        output_cost_per_token=0.00012,
        supports_function_calling=True,
        metadata={"description": "GPT-4 with larger context window"}
    ),
    AIModel(
        name="gpt-3.5-turbo",
        provider=ModelProvider.OPENAI,
        context_window=4096,
        max_tokens=2048,
        input_cost_per_token=0.0000015,
        output_cost_per_token=0.000002,
        supports_function_calling=True,
        metadata={"description": "Fast and cost-effective GPT-3.5 model"}
    ),
    AIModel(
        name="gpt-3.5-turbo-16k",
        provider=ModelProvider.OPENAI,
        context_window=16384,
        max_tokens=8192,
        input_cost_per_token=0.000003,
        output_cost_per_token=0.000004,
        supports_function_calling=True,
        metadata={"description": "GPT-3.5 with larger context window"}
    )
]

ANTHROPIC_MODELS = [
    AIModel(
        name="claude-3-opus-20240229",
        provider=ModelProvider.ANTHROPIC,
        context_window=200000,
        max_tokens=4096,
        input_cost_per_token=0.000015,
        output_cost_per_token=0.000075,
        supports_function_calling=False,
        metadata={"description": "Most capable Claude model"}
    ),
    AIModel(
        name="claude-3-sonnet-20240229",
        provider=ModelProvider.ANTHROPIC,
        context_window=200000,
        max_tokens=4096,
        input_cost_per_token=0.000003,
        output_cost_per_token=0.000015,
        supports_function_calling=False,
        metadata={"description": "Balanced performance and cost"}
    ),
    AIModel(
        name="claude-3-haiku-20240307",
        provider=ModelProvider.ANTHROPIC,
        context_window=200000,
        max_tokens=4096,
        input_cost_per_token=0.00000025,
        output_cost_per_token=0.00000125,
        supports_function_calling=False,
        metadata={"description": "Fast and cost-effective"}
    )
]

LOCAL_MODELS = [
    AIModel(
        name="llama2:7b",
        provider=ModelProvider.LOCAL,
        context_window=4096,
        max_tokens=2048,
        input_cost_per_token=0.0,
        output_cost_per_token=0.0,
        supports_function_calling=False,
        metadata={"description": "Llama 2 7B parameter model"}
    ),
    AIModel(
        name="llama2:13b",
        provider=ModelProvider.LOCAL,
        context_window=4096,
        max_tokens=2048,
        input_cost_per_token=0.0,
        output_cost_per_token=0.0,
        supports_function_calling=False,
        metadata={"description": "Llama 2 13B parameter model"}
    ),
    AIModel(
        name="codellama:7b",
        provider=ModelProvider.LOCAL,
        context_window=16384,
        max_tokens=8192,
        input_cost_per_token=0.0,
        output_cost_per_token=0.0,
        supports_function_calling=False,
        metadata={"description": "Code Llama for programming tasks"}
    )
]


class ModelRegistry:
    """
    Registry for managing AI models and their configurations.

    Provides utilities for model discovery, selection, and fallback management.
    """

    def __init__(self):
        self.models: Dict[str, AIModel] = {}
        self._load_default_models()

    def _load_default_models(self) -> None:
        """Load default model configurations."""
        for model in OPENAI_MODELS + ANTHROPIC_MODELS + LOCAL_MODELS:
            self.models[model.name] = model

    def register_model(self, model: AIModel) -> None:
        """Register a new AI model."""
        self.models[model.name] = model

    def get_model(self, name: str) -> Optional[AIModel]:
        """Get a model by name."""
        return self.models.get(name)

    def list_models(self, provider: Optional[ModelProvider] = None) -> List[AIModel]:
        """List all models, optionally filtered by provider."""
        if provider:
            return [m for m in self.models.values() if m.provider == provider]
        return list(self.models.values())

    def find_best_model(
        self,
        capabilities: List[str] = None,
        max_cost: float = None,
        min_context: int = None,
        preferred_provider: ModelProvider = None
    ) -> Optional[AIModel]:
        """
        Find the best model based on requirements.

        Args:
            capabilities: Required capabilities (function_calling, vision)
            max_cost: Maximum cost per token
            min_context: Minimum context window size
            preferred_provider: Preferred provider

        Returns:
            Best matching model or None
        """
        candidates = list(self.models.values())

        # Filter by provider preference
        if preferred_provider:
            candidates = [m for m in candidates if m.provider == preferred_provider]

        # Filter by capabilities
        if capabilities:
            filtered = []
            for model in candidates:
                has_all_caps = True
                for cap in capabilities:
                    if cap == "function_calling" and not model.supports_function_calling:
                        has_all_caps = False
                        break
                    elif cap == "vision" and not model.supports_vision:
                        has_all_caps = False
                        break
                if has_all_caps:
                    filtered.append(model)
            candidates = filtered

        # Filter by cost
        if max_cost is not None:
            candidates = [
                m for m in candidates
                if m.input_cost_per_token <= max_cost and m.output_cost_per_token <= max_cost
            ]

        # Filter by context window
        if min_context:
            candidates = [m for m in candidates if m.context_window >= min_context]

        if not candidates:
            return None

        # Sort by preference: cost, context window, capabilities
        candidates.sort(key=lambda m: (
            m.input_cost_per_token + m.output_cost_per_token,  # Lower cost first
            -m.context_window,  # Larger context first
            -(1 if m.supports_function_calling else 0),  # Function calling support
            -(1 if m.supports_vision else 0)  # Vision support
        ))

        return candidates[0]

    def get_fallback_models(self, primary_model: str) -> List[str]:
        """Get fallback models for a primary model."""
        primary = self.get_model(primary_model)
        if not primary:
            return []

        # Find models with same or better capabilities at similar or lower cost
        fallbacks = []
        for model in self.models.values():
            if model.name == primary_model:
                continue

            # Same provider fallbacks first
            if model.provider == primary.provider:
                if (model.context_window >= primary.context_window and
                    model.input_cost_per_token <= primary.input_cost_per_token):
                    fallbacks.append(model.name)
            # Cross-provider fallbacks
            elif (model.context_window >= primary.context_window and
                  model.input_cost_per_token <= primary.input_cost_per_token * 2):  # Allow 2x cost
                fallbacks.append(model.name)

        return fallbacks[:3]  # Limit to 3 fallback models


class ModelSelector:
    """
    Intelligent model selection based on task requirements and user preferences.
    """

    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def select_for_task(
        self,
        task_type: str,
        content_length: int = 0,
        languages: List[str] = None,
        budget_constraint: float = None,
        speed_requirement: str = "balanced"
    ) -> List[str]:
        """
        Select best models for a specific task.

        Args:
            task_type: Type of task (writing, translation, analysis, etc.)
            content_length: Length of content to process
            languages: Languages involved
            budget_constraint: Maximum cost per request
            speed_requirement: "fast", "balanced", or "quality"

        Returns:
            List of model names in preference order
        """
        task_requirements = self._get_task_requirements(task_type, content_length, languages)

        candidates = []

        for req in task_requirements:
            model = self.registry.find_best_model(
                capabilities=req.get("capabilities", []),
                max_cost=budget_constraint or req.get("max_cost"),
                min_context=req.get("min_context", content_length),
                preferred_provider=req.get("preferred_provider")
            )
            if model:
                candidates.append(model.name)

        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                unique_candidates.append(candidate)

        return unique_candidates

    def _get_task_requirements(self, task_type: str, content_length: int, languages: List[str]) -> List[Dict]:
        """Get requirements for different task types."""
        base_requirements = {
            "writing": {
                "capabilities": [],
                "min_context": max(4096, content_length * 2),
                "preferred_provider": None
            },
            "translation": {
                "capabilities": [],
                "min_context": max(8192, content_length * 3),  # Need more context for translation
                "preferred_provider": None
            },
            "analysis": {
                "capabilities": [],
                "min_context": max(4096, content_length),
                "preferred_provider": None
            },
            "code_generation": {
                "capabilities": [],
                "min_context": max(8192, content_length * 2),
                "preferred_provider": None
            },
            "creative": {
                "capabilities": [],
                "min_context": max(4096, content_length),
                "preferred_provider": None
            }
        }

        # Adjust for multilingual content
        if languages and len(languages) > 1:
            for req in base_requirements.values():
                req["min_context"] = int(req["min_context"] * 1.5)  # Increase context for multilingual

        return [base_requirements.get(task_type, base_requirements["writing"])]


# Global model registry instance
model_registry = ModelRegistry()
model_selector = ModelSelector(model_registry)