"""
Embedding Service
Generates text embeddings using sentence-transformers
Uses all-MiniLM-L6-v2 model for local inference
"""

from typing import List, Optional
import numpy as np


class EmbeddingService:
    def __init__(self):
        self.model = None
        self.model_name = "all-MiniLM-L6-v2"
        self.is_loading = False

    def load_model(self):
        """Load the embedding model (lazy loading)"""
        if self.model:
            return self.model

        if self.is_loading:
            return self.model

        self.is_loading = True
        print(f"🔄 Loading embedding model: {self.model_name}...")

        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            print(f"✅ Embedding model loaded: {self.model_name}")
            return self.model
        except Exception as e:
            print(f"❌ Error loading embedding model: {str(e)}")
            self.is_loading = False
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text
        
        Args:
            text: Text to generate embedding for
            
        Returns:
            384-dimensional embedding vector
        """
        try:
            model = self.load_model()
            
            # Generate embedding
            embedding = model.encode(text, normalize_embeddings=True)
            
            # Convert to list
            embedding_list = embedding.tolist()
            
            print(f"✅ Generated {len(embedding_list)}-dimensional embedding")
            return embedding_list
        except Exception as e:
            print(f"❌ Error generating embedding: {str(e)}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (batch processing)
        
        Args:
            texts: Array of texts
            
        Returns:
            Array of embeddings
        """
        try:
            model = self.load_model()
            
            # Generate embeddings
            embeddings = model.encode(texts, normalize_embeddings=True)
            
            # Convert to list of lists
            embeddings_list = [emb.tolist() for emb in embeddings]
            
            print(f"✅ Generated embeddings for {len(texts)} texts")
            return embeddings_list
        except Exception as e:
            print(f"❌ Error generating batch embeddings: {str(e)}")
            raise

    def get_embedding_dimension(self) -> int:
        """Get the embedding dimension (384 for all-MiniLM-L6-v2)"""
        return 384

    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Calculate cosine similarity between two embeddings
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Similarity score between -1 and 1
        """
        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have the same dimension")

        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        magnitude = norm1 * norm2
        return float(dot_product / magnitude) if magnitude != 0 else 0.0

    def is_model_loaded(self) -> bool:
        """Check if the model is loaded"""
        return self.model is not None


# Singleton instance
_embedding_service_instance: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get the singleton embedding service instance"""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
