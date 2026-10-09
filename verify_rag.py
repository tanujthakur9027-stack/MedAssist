# verify_rag.py — FIXED
import chromadb
import os

CHROMA_DIR = "data/chroma_db"

if not os.path.exists(CHROMA_DIR):
    print("❌ ChromaDB folder not found!")
    exit()

client = chromadb.PersistentClient(path=CHROMA_DIR)
collection = client.get_collection("medassist_rag")

print(f"📊 Total documents in RAG: {collection.count()}")

# CORRECT where syntax for ChromaDB
try:
    all_medtests = collection.get(where={"type": {"$eq": "medical_test"}})
    print(f"🧪 Medical tests in RAG: {len(all_medtests['ids'])}")
except:
    # Fallback: manual count
    results = collection.get(limit=99999)
    med_count = sum(1 for m in results['metadatas'] if m.get('type') == 'medical_test')
    print(f"🧪 Medical tests in RAG (manual): {med_count}")

# Peek at a medical test specifically
try:
    sample = collection.get(where={"type": {"$eq": "medical_test"}}, limit=3)
    print("\n🔍 Sample medical tests:")
    for meta in sample['metadatas']:
        print(f"  - {meta.get('title', 'No title')}")
except Exception as e:
    print(f"⚠️ Could not peek: {e}")