import threading
from typing import List, Optional
import numpy as np

from app.core.config import settings
from app.core.logger import logger


class TextEmbedder:
    """
    Singleton wrapper around sentence-transformers model ('all-MiniLM-L6-v2').
    Ensures model weights are loaded into memory once during application startup.
    """

    _instance: Optional["TextEmbedder"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self.model_name: str = settings.MODEL_NAME
        self.dimension: int = settings.EMBEDDING_DIMENSION
        self._model = None
        self._is_loaded: bool = False
        self._load_model()

    def _load_model(self) -> None:
        """Loads SentenceTransformer model into memory."""
        try:
            logger.info(f"Loading SentenceTransformer model '{self.model_name}'...")
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            self._is_loaded = True
            logger.info(
                f"SentenceTransformer model '{self.model_name}' loaded successfully "
                f"(embedding dim={self.dimension})."
            )
        except Exception as e:
            logger.warning(
                f"Could not load SentenceTransformer model '{self.model_name}': {str(e)}. "
                "Fallback synthetic embedding generator will be active."
            )
            self._is_loaded = False

    @classmethod
    def get_instance(cls) -> "TextEmbedder":
        """
        Thread-safe singleton getter for TextEmbedder.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def initialize_on_startup(cls) -> "TextEmbedder":
        """
        Lifespan initialization method called on FastAPI application startup.
        """
        return cls.get_instance()

    def encode_text(self, text: str) -> List[float]:
        """
        Encodes a single text string into a 384-dimensional float vector.
        """
        if not text or not text.strip():
            # Return zero vector if text is empty
            return [0.0] * self.dimension

        if self._is_loaded and self._model is not None:
            try:
                embedding = self._model.encode(
                    text, convert_to_numpy=True, normalize_embeddings=True
                )
                return embedding.tolist()
            except Exception as e:
                logger.error(f"Error encoding text with SentenceTransformer: {str(e)}")

        # Fallback deterministic pseudo-random embedding generator (useful for offline tests)
        return self._generate_fallback_embedding(text)

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Encodes a batch of text strings into a list of 384-dimensional float vectors.
        """
        if not texts:
            return []

        if self._is_loaded and self._model is not None:
            try:
                embeddings = self._model.encode(
                    texts, convert_to_numpy=True, normalize_embeddings=True
                )
                return embeddings.tolist()
            except Exception as e:
                logger.error(f"Error batch encoding texts: {str(e)}")

        return [self.encode_text(t) for t in texts]

    def _generate_fallback_embedding(self, text: str) -> List[float]:
        """
        Generates a deterministic 384-dimensional unit vector using string hashing.
        Used as fallback during model loading issues or test mock environments.
        """
        seed = abs(hash(text)) % (2**32)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dimension)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()


def get_embedder() -> TextEmbedder:
    """FastAPI dependency provider returning TextEmbedder singleton."""
    return TextEmbedder.get_instance()
