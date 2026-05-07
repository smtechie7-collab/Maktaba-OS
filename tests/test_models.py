"""
Tests for AI model registry, selection, and fallback logic.
"""

import pytest
from modules.ai.models import (
    ModelRegistry, ModelSelector, model_registry,
    OPENAI_MODELS, ANTHROPIC_MODELS, LOCAL_MODELS
)
from modules.ai.service import ModelProvider, AIModel


class TestModelRegistry:
    """Test the model registry functionality."""
    
    def test_registry_loads_default_models(self):
        """Test that default models are loaded on initialization."""
        registry = ModelRegistry()
        
        assert len(registry.models) > 0
        assert "gpt-4" in registry.models
        assert "gpt-3.5-turbo" in registry.models
    
    def test_register_and_retrieve_custom_model(self):
        """Test registering and retrieving custom models."""
        registry = ModelRegistry()
        
        custom_model = AIModel(
            name="custom-model-v1",
            provider=ModelProvider.CUSTOM,
            context_window=2048,
            max_tokens=1024,
            input_cost_per_token=0.0001,
            output_cost_per_token=0.0002
        )
        
        registry.register_model(custom_model)
        retrieved = registry.get_model("custom-model-v1")
        
        assert retrieved is not None
        assert retrieved.name == "custom-model-v1"
        assert retrieved.provider == ModelProvider.CUSTOM
    
    def test_list_models_by_provider(self):
        """Test listing models filtered by provider."""
        registry = ModelRegistry()
        
        openai_models = registry.list_models(ModelProvider.OPENAI)
        assert all(m.provider == ModelProvider.OPENAI for m in openai_models)
        assert len(openai_models) > 0
        
        anthropic_models = registry.list_models(ModelProvider.ANTHROPIC)
        assert all(m.provider == ModelProvider.ANTHROPIC for m in anthropic_models)
        assert len(anthropic_models) > 0
    
    def test_list_all_models(self):
        """Test listing all models without filter."""
        registry = ModelRegistry()
        
        all_models = registry.list_models()
        assert len(all_models) > 0
        
        # Should have models from multiple providers
        providers = {m.provider for m in all_models}
        assert len(providers) > 1
    
    def test_get_nonexistent_model(self):
        """Test retrieving a model that doesn't exist."""
        registry = ModelRegistry()
        
        result = registry.get_model("nonexistent-model-xyz")
        assert result is None
    
    def test_find_best_model_without_constraints(self):
        """Test finding best model with no constraints."""
        registry = ModelRegistry()
        
        best = registry.find_best_model()
        assert best is not None
        assert best.name in registry.models
    
    def test_find_best_model_by_cost(self):
        """Test finding most cost-effective model."""
        registry = ModelRegistry()
        
        # Find cheapest model
        cheapest = registry.find_best_model(max_cost=0.00001)
        assert cheapest is not None
        assert cheapest.input_cost_per_token <= 0.00001
        assert cheapest.output_cost_per_token <= 0.00001
    
    def test_find_best_model_by_context_window(self):
        """Test finding model with minimum context window."""
        registry = ModelRegistry()
        
        # Find model with large context
        large_context = registry.find_best_model(min_context=16000)
        assert large_context is not None
        assert large_context.context_window >= 16000
    
    def test_find_best_model_by_provider(self):
        """Test finding best model for specific provider."""
        registry = ModelRegistry()
        
        anthropic_model = registry.find_best_model(
            preferred_provider=ModelProvider.ANTHROPIC
        )
        if anthropic_model:
            assert anthropic_model.provider == ModelProvider.ANTHROPIC
    
    def test_find_best_model_with_multiple_constraints(self):
        """Test finding model with multiple constraints."""
        registry = ModelRegistry()
        
        model = registry.find_best_model(
            min_context=4096,
            max_cost=0.0001,
            preferred_provider=ModelProvider.OPENAI
        )
        
        if model:
            assert model.context_window >= 4096
            assert model.input_cost_per_token <= 0.0001
            assert model.output_cost_per_token <= 0.0001
    
    def test_find_best_model_no_matches(self):
        """Test finding model with impossible constraints."""
        registry = ModelRegistry()
        
        # Very restrictive cost constraint
        model = registry.find_best_model(max_cost=0.00000001)
        # Result may be None or a very cheap model
        if model:
            assert model.input_cost_per_token <= 0.00000001
    
    def test_get_fallback_models(self):
        """Test getting fallback models for a primary model."""
        registry = ModelRegistry()
        
        fallbacks = registry.get_fallback_models("gpt-4")
        assert isinstance(fallbacks, list)
        assert "gpt-4" not in fallbacks
        assert len(fallbacks) <= 3
    
    def test_get_fallback_models_for_cheap_model(self):
        """Test getting fallbacks for a low-cost model."""
        registry = ModelRegistry()
        
        fallbacks = registry.get_fallback_models("gpt-3.5-turbo")
        assert isinstance(fallbacks, list)
        assert "gpt-3.5-turbo" not in fallbacks
    
    def test_get_fallback_models_nonexistent(self):
        """Test getting fallbacks for nonexistent model."""
        registry = ModelRegistry()
        
        fallbacks = registry.get_fallback_models("nonexistent-model")
        assert fallbacks == []
    
    def test_model_metadata(self):
        """Test that model metadata is preserved."""
        registry = ModelRegistry()
        
        gpt4 = registry.get_model("gpt-4")
        assert gpt4 is not None
        assert "description" in gpt4.metadata
        assert gpt4.supports_function_calling


class TestModelSelector:
    """Test the model selector functionality."""
    
    def test_selector_initialization(self):
        """Test selector initialization with registry."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        assert selector.registry is registry
    
    def test_select_for_writing_task(self):
        """Test selecting model for writing task."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        models = selector.select_for_task(
            task_type="writing",
            content_length=5000,
            speed_requirement="balanced"
        )
        
        assert isinstance(models, list)
        assert len(models) > 0
    
    def test_select_for_translation_task(self):
        """Test selecting model for translation task."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        models = selector.select_for_task(
            task_type="translation",
            languages=["en", "ar", "ur"],
            content_length=3000
        )
        
        assert isinstance(models, list)
        # Translation needs more context
        if models:
            selected_model = registry.get_model(models[0])
            assert selected_model.context_window >= 3000
    
    def test_select_for_analysis_task(self):
        """Test selecting model for analysis task."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        models = selector.select_for_task(
            task_type="analysis",
            content_length=2000
        )
        
        assert isinstance(models, list)
        assert len(models) > 0
    
    def test_select_for_code_generation(self):
        """Test selecting model for code generation task."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        models = selector.select_for_task(
            task_type="code_generation",
            content_length=1000
        )
        
        assert isinstance(models, list)
        assert len(models) > 0
    
    def test_select_for_creative_task(self):
        """Test selecting model for creative writing."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        models = selector.select_for_task(
            task_type="creative",
            content_length=2000
        )
        
        assert isinstance(models, list)
        assert len(models) > 0
    
    def test_select_with_budget_constraint(self):
        """Test selecting model with cost constraint."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        models = selector.select_for_task(
            task_type="writing",
            budget_constraint=0.001
        )
        
        assert isinstance(models, list)
        # All selected models should be within budget
        for model_name in models:
            model = registry.get_model(model_name)
            if model:
                assert model.input_cost_per_token <= 0.001
    
    def test_select_with_speed_requirement(self):
        """Test selecting model based on speed requirement."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        fast_models = selector.select_for_task(
            task_type="writing",
            speed_requirement="fast"
        )
        
        balanced_models = selector.select_for_task(
            task_type="writing",
            speed_requirement="balanced"
        )
        
        quality_models = selector.select_for_task(
            task_type="writing",
            speed_requirement="quality"
        )
        
        assert isinstance(fast_models, list)
        assert isinstance(balanced_models, list)
        assert isinstance(quality_models, list)
    
    def test_select_multilingual_content(self):
        """Test selecting model for multilingual content."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        models = selector.select_for_task(
            task_type="translation",
            languages=["ar", "en", "fr", "ur"],
            content_length=5000
        )
        
        assert isinstance(models, list)
        if models:
            selected = registry.get_model(models[0])
            # Should select model with larger context for multiple languages
            assert selected.context_window >= 5000
    
    def test_select_removes_duplicates(self):
        """Test that selector removes duplicate model selections."""
        registry = ModelRegistry()
        selector = ModelSelector(registry)
        
        models = selector.select_for_task(
            task_type="writing",
            content_length=1000
        )
        
        # Should not have duplicates
        assert len(models) == len(set(models))


class TestOpenAIModels:
    """Test OpenAI model definitions."""
    
    def test_openai_models_exist(self):
        """Test that OpenAI models are defined."""
        assert len(OPENAI_MODELS) > 0
    
    def test_gpt4_specifications(self):
        """Test GPT-4 model specifications."""
        gpt4 = next((m for m in OPENAI_MODELS if m.name == "gpt-4"), None)
        assert gpt4 is not None
        assert gpt4.provider == ModelProvider.OPENAI
        assert gpt4.context_window == 8192
        assert gpt4.supports_function_calling
    
    def test_gpt4_32k_specifications(self):
        """Test GPT-4 32K model specifications."""
        gpt4_32k = next((m for m in OPENAI_MODELS if m.name == "gpt-4-32k"), None)
        assert gpt4_32k is not None
        assert gpt4_32k.context_window == 32768
        assert gpt4_32k.max_tokens == 16384
    
    def test_gpt35_turbo_specifications(self):
        """Test GPT-3.5 Turbo specifications."""
        gpt35 = next((m for m in OPENAI_MODELS if m.name == "gpt-3.5-turbo"), None)
        assert gpt35 is not None
        assert gpt35.context_window == 4096
        assert gpt35.supports_function_calling
    
    def test_openai_cost_structure(self):
        """Test that OpenAI models have cost information."""
        for model in OPENAI_MODELS:
            assert model.input_cost_per_token > 0
            assert model.output_cost_per_token > 0
            # Output usually costs more than input
            assert model.output_cost_per_token >= model.input_cost_per_token


class TestAnthropicModels:
    """Test Anthropic Claude model definitions."""
    
    def test_anthropic_models_exist(self):
        """Test that Anthropic models are defined."""
        assert len(ANTHROPIC_MODELS) > 0
    
    def test_claude_models_have_large_context(self):
        """Test Claude models have large context windows."""
        for model in ANTHROPIC_MODELS:
            assert model.context_window >= 200000
    
    def test_anthropic_cost_structure(self):
        """Test Anthropic model cost structure."""
        for model in ANTHROPIC_MODELS:
            assert model.input_cost_per_token > 0
            assert model.output_cost_per_token > 0


class TestLocalModels:
    """Test local model definitions."""
    
    def test_local_models_exist(self):
        """Test that local models are defined."""
        assert len(LOCAL_MODELS) > 0
    
    def test_local_models_zero_cost(self):
        """Test that local models have zero cost."""
        for model in LOCAL_MODELS:
            assert model.input_cost_per_token == 0.0
            assert model.output_cost_per_token == 0.0
    
    def test_llama_models(self):
        """Test Llama model definitions."""
        llama_models = [m for m in LOCAL_MODELS if "llama" in m.name.lower()]
        assert len(llama_models) > 0
    
    def test_codellama_model(self):
        """Test Code Llama model definition."""
        code_llama = next((m for m in LOCAL_MODELS if "codellama" in m.name.lower()), None)
        assert code_llama is not None
        assert code_llama.context_window >= 16384


class TestGlobalRegistry:
    """Test the global model registry instance."""
    
    def test_global_registry_initialized(self):
        """Test that global registry is initialized."""
        assert model_registry is not None
        assert isinstance(model_registry, ModelRegistry)
    
    def test_global_registry_has_models(self):
        """Test that global registry has models."""
        assert len(model_registry.models) > 0
    
    def test_global_registry_can_find_models(self):
        """Test finding models in global registry."""
        gpt4 = model_registry.get_model("gpt-4")
        assert gpt4 is not None
        assert gpt4.name == "gpt-4"
