#!/usr/bin/env python3
"""
Quick test for Disease Info Module
Run this to verify everything is working before full integration.
"""

import os
import sys

# Set dummy env vars for testing if not set
if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GROQ_API_KEY"):
    print("WARNING: No LLM API key found. Set GEMINI_API_KEY or GROQ_API_KEY in .env")
    print("   The module will work but structured extraction needs an LLM.\n")

try:
    from disease_info import DiseaseInfoRetriever, format_disease_info
    print("disease_info.py imported successfully")
except Exception as e:
    print(f"Failed to import disease_info.py: {e}")
    sys.exit(1)

try:
    retriever = DiseaseInfoRetriever()
    print("DiseaseInfoRetriever initialized")
    print(f"   -> LLM Type: {retriever.llm_type}")
    print(f"   -> ChromaDB Collections: {retriever.client.list_collections()}")
except Exception as e:
    print(f"Failed to initialize retriever: {e}")
    sys.exit(1)

# Test search
try:
    docs = retriever.get_disease_documents("diabetes", n_results=3)
    print(f"Search test passed — found {len(docs)} documents")
    if docs:
        print(f"   -> Top doc: {docs[0]['title']}")
except Exception as e:
    print(f"Search test failed: {e}")

print("\nAll basic tests passed! Ready for integration.")
