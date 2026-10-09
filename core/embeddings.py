"""
Embeddings utility for RAG.
Uses sentence-transformers (free, local, no API key needed).
"""
import os
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
from sentence_transformers import SentenceTransformer

class FreeEmbeddings:
    def __init__(self):
        print("Loading embedding model... (First time takes 1-2 minutes)")
        # Free, small, fast model - perfect for this project
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Embedding model loaded!")
    
    def embed_documents(self, texts):
        """
        Convert a list of texts to embedding vectors.
        Returns list of vectors.
        """
        if isinstance(texts, str):
            texts = [texts]
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
    
    def embed_query(self, text):
        """
        Convert a single query text to embedding vector.
        Returns single vector.
        """
        embedding = self.model.encode([text], show_progress_bar=False)
        return embedding[0].tolist()


# Test
if __name__ == "__main__":
    print("Testing embeddings...")
    emb = FreeEmbeddings()
    
    # Test single text
    vector = emb.embed_query("fever and headache")
    print(f"Single vector length: {len(vector)}")
    
    # Test multiple texts
    vectors = emb.embed_documents(["fever", "headache", "diabetes"])
    print(f"Multiple vectors: {len(vectors)} documents, each {len(vectors[0])} dimensions")