#!/usr/bin/env python3
"""
AI Infrastructure Demonstration Script.

This script demonstrates the basic functionality of the AI infrastructure
without requiring actual API keys or external services.
"""

import asyncio
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ai.agent import AgentConfig, AgentCapability, AgentContext
from modules.ai.service import ModelProvider, AIServiceConfig, OpenAIService
from modules.ai.models import model_registry
from modules.ai.context import AIContextManager, ChunkingStrategy
from modules.ai.metrics import metrics_aggregator
from modules.ai.content_agent import ContentGenerationAgent


async def demo_model_registry():
    """Demonstrate model registry functionality."""
    print("🔍 Testing Model Registry...")

    # List available OpenAI models
    openai_models = model_registry.list_models(ModelProvider.OPENAI)
    print(f"Available OpenAI models: {len(openai_models)}")
    for model in openai_models[:3]:  # Show first 3
        print(f"  - {model.name} (context: {model.context_window} tokens)")

    # Get a specific model
    gpt4 = model_registry.get_model("gpt-4")
    if gpt4:
        print(f"GPT-4 details: {gpt4.max_tokens} max tokens, ${gpt4.input_cost_per_token}/input token")
    else:
        print("GPT-4 model not found in registry")


async def demo_context_management():
    """Demonstrate context window management."""
    print("\n📄 Testing Context Management...")

    manager = AIContextManager()

    # Sample Arabic text (religious content)
    sample_text = """
    بسم الله الرحمن الرحيم

    الحمد لله رب العالمين، الرحمن الرحيم، مالك يوم الدين.
    إياك نعبد وإياك نستعين، اهدنا الصراط المستقيم، صراط الذين أنعمت عليهم غير المغضوب عليهم ولا الضالين.

    هذه سورة الفاتحة من القرآن الكريم، وهي أول سورة في المصحف الشريف.
    """

    # Test different chunking strategies
    paragraph_chunks = manager.add_document("demo_doc", sample_text, ChunkingStrategy.PARAGRAPH)
    print(f"Paragraph chunks: {len(paragraph_chunks)}")
    for i, chunk in enumerate(paragraph_chunks[:2]):  # Show first 2
        print(f"  Chunk {i+1}: {len(chunk.content)} chars, type: {chunk.chunk_type}")

    # Test context window
    window = manager.create_context_window("demo_conversation")
    print(f"Created context window with {window.available_tokens} available tokens")

    # Add a chunk to the window
    if paragraph_chunks:
        added = window.add_chunk(paragraph_chunks[0])
        print(f"Added chunk to window: {added}, remaining tokens: {window.available_tokens}")


async def demo_metrics():
    """Demonstrate metrics tracking."""
    print("\n📊 Testing Metrics Tracking...")

    # Get the global metrics aggregator
    aggregator = metrics_aggregator

    # Register a demo agent
    agent_metrics = aggregator.register_agent("demo_agent")

    # Simulate some requests using the agent metrics
    agent_metrics.record_request(
        success=True,
        input_tokens=150,
        output_tokens=75,
        cost=0.0025,
        response_time=1.2,
        provider="openai",
        model="gpt-4"
    )

    agent_metrics.record_request(
        success=False,
        response_time=0.8,
        provider="openai",
        model="gpt-4"
    )

    # Get summary from the agent metrics
    summary = agent_metrics.get_summary(hours=24)
    print(f"Total requests: {summary['requests']['total']}")
    print(f"Success rate: {summary['requests']['successful']}/{summary['requests']['total']}")
    print(f"Total cost: ${summary['cost']['total']:.4f}")
    print(f"Total tokens: {summary['tokens']['total']}")

    # Get global summary
    global_summary = aggregator.get_global_summary(hours=24)
    print(f"Global requests: {global_summary['requests']['total']}")


async def demo_agent_creation():
    """Demonstrate agent creation (without actual API calls)."""
    print("\n🤖 Testing Agent Creation...")

    # Create a mock AI service (without real API key)
    service_config = AIServiceConfig(
        provider=ModelProvider.OPENAI,
        api_key="demo_key"  # This won't work for real calls
    )

    # Note: We won't actually instantiate the service since we don't have a real API key
    print("AI Service configuration created (API key required for actual usage)")

    # Create agent config
    agent_config = AgentConfig(
        name="demo_content_agent",
        description="Demo content generation agent",
        capabilities=[AgentCapability.TEXT_GENERATION],
        model_provider="openai",
        model_name="gpt-4",
        temperature=0.7,
        max_tokens=1000
    )

    print(f"Agent config created: {agent_config.name}")
    print(f"Capabilities: {[cap.value for cap in agent_config.capabilities]}")
    print(f"Model: {agent_config.model_provider}/{agent_config.model_name}")


async def main():
    """Run all demonstrations."""
    print("🚀 Maktaba-OS AI Infrastructure Demonstration")
    print("=" * 50)

    try:
        await demo_model_registry()
        await demo_context_management()
        await demo_metrics()
        await demo_agent_creation()

        print("\n✅ All demonstrations completed successfully!")
        print("\n📝 Note: To use actual AI features, you'll need to:")
        print("   1. Set up API keys for your preferred AI providers")
        print("   2. Configure the AI service with valid credentials")
        print("   3. Initialize agents with the configured service")

    except Exception as e:
        print(f"\n❌ Demonstration failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())