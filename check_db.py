import os
import chromadb
from chromadb.config import Settings

# Check all possible paths
paths = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "chroma_db"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "chroma_db"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "vector_db"),
    "./chroma_db",
    "./data/chroma_db",
    "./data/vector_db",
    "../chroma_db",
    "../data/chroma_db",
    "../data/vector_db",
]

print("=" * 60)
print("CHECKING CHROMADB LOCATIONS")
print("=" * 60)

for p in paths:
    exists = os.path.exists(p)
    abs_path = os.path.abspath(p)
    print(f"\n📁 Path: {abs_path}")
    print(f"   Exists: {'✅ YES' if exists else '❌ NO'}")
    
    if exists:
        try:
            client = chromadb.PersistentClient(path=abs_path, settings=Settings(anonymized_telemetry=False))
            collections = client.list_collections()
            print(f"   Collections found: {len(collections)}")
            
            for c in collections:
                coll = client.get_collection(name=c.name)
                count = coll.count()
                print(f"   📦 '{c.name}' → {count} documents")
                
                # Peek at first doc
                if count > 0:
                    sample = coll.get(limit=1, include=["documents", "metadatas"])
                    doc = sample["documents"][0] if sample["documents"] else "N/A"
                    meta = sample["metadatas"][0] if sample["metadatas"] else {}
                    print(f"   📝 Sample title: {meta.get('title', 'No title')}")
                    print(f"   📝 Sample text (first 100 chars): {str(doc)[:100]}...")
                else:
                    print(f"   ⚠️  Collection is EMPTY!")
                    
        except Exception as e:
            print(f"   ❌ Error: {e}")

print("\n" + "=" * 60)
print("CHECKING DATA FOLDER CONTENTS")
print("=" * 60)

data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
if os.path.exists(data_dir):
    for root, dirs, files in os.walk(data_dir):
        level = root.replace(data_dir, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for f in files[:10]:  # Limit to first 10 files per dir
            print(f"{subindent}{f}")
        if len(files) > 10:
            print(f"{subindent}... and {len(files)-10} more files")
else:
    print("❌ No 'data' folder found!")