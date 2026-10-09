# add_medical_tests_to_rag.py — CORRECTED for your JSON structure
import json
import os
import chromadb
from core.embeddings import FreeEmbeddings

# ========== LOAD MEDICAL TESTS ==========
test_file = "data/raw/medlineplus_medical_tests.json"
if not os.path.exists(test_file):
    print(f"❌ File not found: {test_file}")
    exit()

with open(test_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

# EXACT structure: {"metadata": {...}, "tests": [...]}
tests = data.get("tests", [])
print(f"📦 Total medical tests loaded: {len(tests)}")

# ========== CONNECT TO CHROMADB ==========
embeddings = FreeEmbeddings()
client = chromadb.PersistentClient(path="data/chroma_db")

try:
    collection = client.get_collection("medassist_rag")
    print("✅ Connected to existing collection")
except:
    collection = client.create_collection("medassist_rag")
    print("✅ Created new collection")

# ========== DELETE OLD MEDICAL TESTS (to avoid duplicates) ==========
existing = collection.get(where={"type": "medical_test"})
if existing['ids']:
    print(f"🗑️  Deleting {len(existing['ids'])} old medical tests...")
    collection.delete(ids=existing['ids'])

# ========== ADD ALL 350 TESTS ==========
batch_size = 50
added = 0

for i in range(0, len(tests), batch_size):
    batch = tests[i:i+batch_size]
    
    ids = []
    documents = []
    metadatas = []
    
    for j, test in enumerate(batch):
        idx = i + j
        test_id = f"medtest_{idx}"
        
        # Your JSON uses "name" not "title"
        title = test.get('name') or test.get('title') or f"Test_{idx}"
        url = test.get('url', '')
        
        # Build rich content from all available fields
        parts = [f"Medical Test: {title}"]
        
        if test.get('description'):
            parts.append(f"Description: {test['description']}")
        if test.get('why_done'):
            parts.append(f"Why done: {test['why_done']}")
        if test.get('what_happens'):
            parts.append(f"What happens: {test['what_happens']}")
        if test.get('risks_complications'):
            parts.append(f"Risks: {test['risks_complications']}")
        if test.get('normal_values'):
            parts.append(f"Normal values: {test['normal_values']}")
        if test.get('what_results_mean'):
            parts.append(f"Results meaning: {test['what_results_mean']}")
        if test.get('special_considerations'):
            parts.append(f"Special considerations: {test['special_considerations']}")
        
        content = "\n\n".join(parts)
        
        ids.append(test_id)
        documents.append(content)
        metadatas.append({
            'type': 'medical_test',
            'title': title,
            'url': url,
            'source': 'MedlinePlus Lab Tests'
        })
    
    collection.add(ids=ids, documents=documents, metadatas=metadatas)
    added += len(ids)
    print(f"✅ Added: {added}/{len(tests)}")

print(f"\n🎉 Done! Total medical tests in RAG: {added}")

# Verify
final = collection.get(where={"type": "medical_test"})
print(f"🧪 Verified in RAG: {len(final['ids'])} medical tests")