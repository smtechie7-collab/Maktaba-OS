#!/usr/bin/env python3
"""
Semantic Search Demonstration Script.

This script demonstrates the vector embeddings and semantic search capabilities.
Note: Requires sentence-transformers and faiss-cpu to be installed for full functionality.
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ai.embeddings import (
    SemanticSearchEngine, SENTENCE_TRANSFORMERS_AVAILABLE,
    initialize_semantic_search, get_semantic_search_engine
)


def demo_semantic_search():
    """Demonstrate semantic search functionality."""
    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("❌ sentence-transformers and/or faiss not available.")
        print("Install with: pip install sentence-transformers faiss-cpu")
        print("\nDemonstrating fallback behavior...")

        # Show what would happen with mock data
        print("\n📄 Sample semantic search workflow:")
        print("1. Initialize search engine with embedding model")
        print("2. Add documents with vector embeddings")
        print("3. Search using natural language queries")
        print("4. Get semantically similar results ranked by relevance")

        return

    print("🔍 Initializing Semantic Search Engine...")

    try:
        # Initialize the search engine
        engine = initialize_semantic_search("all-MiniLM-L6-v2")
        print("✅ Search engine initialized successfully")

        # Sample religious/Islamic texts for demonstration
        sample_texts = [
            "The Quran is the holy book of Islam revealed to Prophet Muhammad",
            "Prayer is one of the five pillars of Islam performed five times daily",
            "Zakat is obligatory giving of a portion of wealth to the poor",
            "Hajj is the pilgrimage to Mecca that every Muslim must undertake",
            "The Five Pillars of Islam are fundamental practices for Muslims",
            "Ramadan is the month of fasting and spiritual reflection",
            "The Prophet Muhammad received revelations from Angel Gabriel",
            "Islamic teachings emphasize compassion, charity, and justice",
            "The Kaaba in Mecca is the holiest site in Islam",
            "Salah involves specific physical postures and recitations"
        ]

        print(f"\n📚 Adding {len(sample_texts)} sample texts to search index...")
        doc_ids = engine.add_texts(sample_texts)
        print(f"✅ Added {len(doc_ids)} documents to index")

        # Demonstrate semantic search
        queries = [
            "What are the main practices of Islam?",
            "Tell me about Islamic pilgrimage",
            "What is the holy book called?",
            "How do Muslims pray?",
            "What is fasting in Islam?"
        ]

        print("\n🔎 Performing semantic searches...")
        for query in queries:
            print(f"\nQuery: '{query}'")
            results = engine.search(query, k=3)

            for i, result in enumerate(results, 1):
                content = result['content'][:100] + "..." if len(result['content']) > 100 else result['content']
                print(".3f")

        # Demonstrate semantic similarity
        print("\n🧠 Demonstrating semantic similarity:")
        print("Notice how different queries find relevant content even with different wording")

        similar_queries = [
            "Islamic holy sites",
            "sacred places in Islam",
            "Mecca and Medina"
        ]

        for query in similar_queries:
            results = engine.search(query, k=2)
            if results:
                print(f"'{query}' → '{results[0]['content'][:60]}...'")

    except Exception as e:
        print(f"❌ Error during demonstration: {e}")
        import traceback
        traceback.print_exc()


def demo_vector_operations():
    """Demonstrate basic vector operations."""
    print("\n🧮 Demonstrating Vector Operations...")

    if not SENTENCE_TRANSFORMERS_AVAILABLE:
        print("Vector operations require sentence-transformers library")
        return

    try:
        from modules.ai.embeddings import EmbeddingModel
        import numpy as np

        # Initialize embedding model
        model = EmbeddingModel("all-MiniLM-L6-v2")

        # Sample texts
        texts = [
            "The mosque is a place of worship",
            "A temple is a house of prayer",
            "The church serves religious gatherings"
        ]

        print("Encoding texts into vectors...")
        embeddings = model.encode(texts)

        print(f"Embeddings shape: {embeddings.shape}")
        print(f"Vector dimension: {model.get_dimension()}")

        # Calculate similarities
        from sklearn.metrics.pairwise import cosine_similarity
        similarities = cosine_similarity(embeddings)

        print("\nCosine similarities:")
        for i, text1 in enumerate(texts):
            for j, text2 in enumerate(texts):
                if i < j:  # Upper triangle only
                    sim = similarities[i, j]
                    print(".3f")

    except Exception as e:
        print(f"Error in vector operations: {e}")


def main():
    """Run all demonstrations."""
    print("🚀 Maktaba-OS Semantic Search Demonstration")
    print("=" * 50)

    demo_semantic_search()
    demo_vector_operations()

    print("\n✅ Demonstration completed!")
    print("\n💡 Key Benefits of Semantic Search:")
    print("• Finds content based on meaning, not just keywords")
    print("• Handles synonyms and related concepts")
    print("• Supports multiple languages")
    print("• Enables intelligent content discovery")
    print("• Powers AI-assisted writing and research")


if __name__ == "__main__":
    main()