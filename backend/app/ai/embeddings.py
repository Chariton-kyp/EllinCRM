"""
Embedding service for document vectorization.

Uses sentence-transformers with a multilingual model for Greek/English support.
Embeddings are stored in PostgreSQL with pgvector for efficient similarity search.

Model Selection Strategy:
1. Primary: google/embeddinggemma-300m (768 dims) - requires HuggingFace token
2. Fallback: paraphrase-multilingual-mpnet-base-v2 (768 dims) - no auth required

Both models support Greek/English and produce 768-dimensional vectors.

ASYNC LOADING:
The model is loaded in the background on startup to avoid blocking the API.
Embedding features become available when the model is ready.
Other API features work immediately.
"""

import asyncio
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ModelStatus(str, Enum):
    """Status of the embedding model loading."""
    NOT_STARTED = "not_started"
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"

# Primary model: Google EmbeddingGemma 300M (September 2025)
# - 768 dimensions, 300M parameters
# - Multilingual: 100+ languages including Greek
# - Requires HuggingFace authentication (gated model)
PRIMARY_MODEL = "google/embeddinggemma-300m"

# Fallback model: Multilingual MPNet (no auth required)
# - 768 dimensions, based on XLM-RoBERTa
# - Multilingual: 50+ languages including Greek
# - Free to use without authentication
FALLBACK_MODEL = "paraphrase-multilingual-mpnet-base-v2"

# Embedding dimension (both models produce 768-dim vectors)
EMBEDDING_DIMENSION = 768


class EmbeddingService:
    """
    Service for generating document embeddings with async background loading.

    Uses sentence-transformers for efficient local embedding generation.
    Supports multilingual text including Greek and English.

    ASYNC LOADING:
        The model is loaded in the background to avoid blocking the API.
        Use `is_ready` property to check if model is available.
        Use `start_background_loading()` to initiate loading at startup.

    Model Selection:
        1. Tries PRIMARY_MODEL (google/embeddinggemma-300m) if HuggingFace token is available
        2. Falls back to FALLBACK_MODEL (paraphrase-multilingual-mpnet-base-v2) otherwise

    Example:
        >>> service = EmbeddingService()
        >>> service.start_background_loading()  # Non-blocking
        >>> # ... later ...
        >>> if service.is_ready:
        ...     embedding = service.generate_embedding("Αναζήτηση υπηρεσιών IT")
    """

    def __init__(
        self,
        primary_model: str = PRIMARY_MODEL,
        fallback_model: str = FALLBACK_MODEL,
    ):
        """
        Initialize the embedding service with fallback support.

        Args:
            primary_model: Primary model to try (may require HF token).
            fallback_model: Fallback model if primary fails.
        """
        self._primary_model = primary_model
        self._fallback_model = fallback_model
        self._model: SentenceTransformer | None = None
        self._active_model_name: str | None = None
        self._dimension = EMBEDDING_DIMENSION
        self._status = ModelStatus.NOT_STARTED
        self._error_message: str | None = None
        self._load_lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="embedding_loader")

    @property
    def status(self) -> ModelStatus:
        """Return the current model loading status."""
        return self._status

    @property
    def is_ready(self) -> bool:
        """Check if the model is loaded and ready to use."""
        return self._status == ModelStatus.READY and self._model is not None

    @property
    def is_loading(self) -> bool:
        """Check if the model is currently loading."""
        return self._status == ModelStatus.LOADING

    @property
    def error_message(self) -> str | None:
        """Return error message if loading failed."""
        return self._error_message

    def get_status_info(self) -> dict[str, Any]:
        """Get detailed status information about the model loading."""
        return {
            "status": self._status.value,
            "is_ready": self.is_ready,
            "is_loading": self.is_loading,
            "model_name": self._active_model_name,
            "dimension": self._dimension,
            "error": self._error_message,
        }

    @property
    def model_name(self) -> str:
        """Return the active model name."""
        return self._active_model_name or self._fallback_model

    @property
    def model(self) -> SentenceTransformer | None:
        """
        Get the embedding model if loaded.

        Returns None if model is not ready (use is_ready to check first).
        For blocking load, use load_model_sync() instead.
        """
        return self._model

    def start_background_loading(self) -> None:
        """
        Start loading the model in the background (non-blocking).

        This method returns immediately. Use `is_ready` to check when
        the model is available.
        """
        with self._load_lock:
            if self._status in (ModelStatus.LOADING, ModelStatus.READY):
                logger.info(
                    "background_loading_skipped",
                    reason="already_loading_or_ready",
                    status=self._status.value,
                )
                return

            self._status = ModelStatus.LOADING

        logger.info(
            "background_loading_started",
            primary_model=self._primary_model,
            fallback_model=self._fallback_model,
        )

        # Submit loading task to thread pool
        self._executor.submit(self._load_model_background)

    def _load_model_background(self) -> None:
        """Background thread function to load the model."""
        try:
            model = self._load_model_with_fallback()
            with self._load_lock:
                self._model = model
                self._status = ModelStatus.READY
            logger.info(
                "background_loading_completed",
                model=self._active_model_name,
                status="ready",
            )
        except Exception as e:
            with self._load_lock:
                self._status = ModelStatus.FAILED
                self._error_message = str(e)
            logger.error(
                "background_loading_failed",
                error=str(e),
            )

    def load_model_sync(self) -> SentenceTransformer:
        """
        Load the model synchronously (blocking).

        Use this only when you need the model immediately.
        Prefer start_background_loading() for non-blocking startup.
        """
        with self._load_lock:
            if self._model is not None:
                return self._model

            if self._status == ModelStatus.LOADING:
                # Wait for background loading to complete
                pass

            self._status = ModelStatus.LOADING

        try:
            model = self._load_model_with_fallback()
            with self._load_lock:
                self._model = model
                self._status = ModelStatus.READY
            return model
        except Exception as e:
            with self._load_lock:
                self._status = ModelStatus.FAILED
                self._error_message = str(e)
            raise

    def _load_model_with_fallback(self) -> SentenceTransformer:
        """
        Attempt to load the primary model, fall back if it fails.

        Returns:
            Loaded SentenceTransformer model.
        """
        # Set HuggingFace token if available
        hf_token = settings.huggingface_token
        if hf_token:
            os.environ["HF_TOKEN"] = hf_token
            os.environ["HUGGING_FACE_HUB_TOKEN"] = hf_token
            logger.info(
                "huggingface_token_configured",
                token_prefix=hf_token[:8] + "..." if len(hf_token) > 8 else "***",
            )

        # Try primary model first
        try:
            logger.info(
                "loading_embedding_model",
                model=self._primary_model,
                is_primary=True,
            )
            model = SentenceTransformer(
                self._primary_model,
                token=hf_token,
            )
            self._active_model_name = self._primary_model
            logger.info(
                "embedding_model_loaded",
                model=self._primary_model,
                dimension=self._dimension,
                is_primary=True,
            )
            return model
        except Exception as e:
            logger.warning(
                "primary_model_failed",
                model=self._primary_model,
                error=str(e),
                fallback=self._fallback_model,
            )

        # Fall back to secondary model
        try:
            logger.info(
                "loading_embedding_model",
                model=self._fallback_model,
                is_fallback=True,
            )
            model = SentenceTransformer(self._fallback_model)
            self._active_model_name = self._fallback_model
            logger.info(
                "embedding_model_loaded",
                model=self._fallback_model,
                dimension=self._dimension,
                is_fallback=True,
            )
            return model
        except Exception as e:
            logger.error(
                "fallback_model_failed",
                model=self._fallback_model,
                error=str(e),
            )
            raise RuntimeError(
                f"Failed to load both primary ({self._primary_model}) "
                f"and fallback ({self._fallback_model}) embedding models: {e}"
            )

    @property
    def dimension(self) -> int:
        """Return the embedding dimension."""
        return self._dimension

    def generate_embedding(self, text: str) -> list[float] | None:
        """
        Generate an embedding vector for the given text.

        Args:
            text: The text to embed (Greek or English).

        Returns:
            List of floats representing the embedding vector,
            or None if model is not ready.
        """
        if not self.is_ready:
            logger.warning(
                "embedding_skipped_model_not_ready",
                status=self._status.value,
            )
            return None

        if not text or not text.strip():
            # Return zero vector for empty text
            return [0.0] * self._dimension

        # Normalize and encode
        text = text.strip()
        embedding = self._model.encode(text, convert_to_numpy=True)

        return embedding.tolist()

    def generate_embeddings_batch(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[float]] | None:
        """
        Generate embeddings for multiple texts efficiently.

        Args:
            texts: List of texts to embed.
            batch_size: Number of texts to process at once.

        Returns:
            List of embedding vectors, or None if model is not ready.
        """
        if not self.is_ready:
            logger.warning(
                "batch_embedding_skipped_model_not_ready",
                status=self._status.value,
            )
            return None

        if not texts:
            return []

        # Filter empty texts and track indices
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text.strip())
                valid_indices.append(i)

        if not valid_texts:
            return [[0.0] * self._dimension for _ in texts]

        # Batch encode
        embeddings = self._model.encode(
            valid_texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        # Build result with zero vectors for empty texts
        result = [[0.0] * self._dimension for _ in texts]
        for idx, embedding in zip(valid_indices, embeddings):
            result[idx] = embedding.tolist()

        return result

    async def generate_embedding_async(self, text: str) -> list[float] | None:
        """
        Async wrapper for embedding generation.

        Runs the synchronous embedding in a thread pool.
        Returns None if model is not ready.
        """
        if not self.is_ready:
            return None
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.generate_embedding, text)

    async def generate_embeddings_batch_async(
        self, texts: list[str], batch_size: int = 32
    ) -> list[list[float]] | None:
        """
        Async wrapper for batch embedding generation.
        Returns None if model is not ready.
        """
        if not self.is_ready:
            return None
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.generate_embeddings_batch(texts, batch_size)
        )

    def compute_similarity(
        self, embedding1: list[float], embedding2: list[float]
    ) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector.
            embedding2: Second embedding vector.

        Returns:
            Cosine similarity score (0 to 1).
        """
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # Cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


# Singleton instance for efficiency
_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """
    Get the singleton embedding service instance.

    Returns:
        EmbeddingService: The shared embedding service.
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def start_embedding_model_loading() -> None:
    """
    Start loading the embedding model in the background.

    Call this during application startup to begin model loading
    without blocking the API from accepting requests.

    The model will be available when `get_embedding_service().is_ready` is True.
    """
    service = get_embedding_service()
    service.start_background_loading()
    logger.info(
        "embedding_model_background_loading_initiated",
        status=service.status.value,
    )


def get_embedding_status() -> dict[str, Any]:
    """
    Get the current status of the embedding model.

    Returns:
        Dict with status information including:
        - status: "not_started", "loading", "ready", or "failed"
        - is_ready: True if model can generate embeddings
        - is_loading: True if model is currently loading
        - model_name: Name of the active model (if loaded)
        - error: Error message (if failed)
    """
    service = get_embedding_service()
    return service.get_status_info()


def extract_text_for_embedding(
    record_type: str, data: dict[str, Any]
) -> str:
    """
    Extract searchable text from a record for embedding.

    Combines relevant fields based on record type to create
    a comprehensive text representation for semantic search.

    Args:
        record_type: Type of record (FORM, EMAIL, INVOICE).
        data: The extracted data dictionary.

    Returns:
        Combined text suitable for embedding.
    """
    parts = []

    if record_type == "FORM":
        # Contact form: focus on inquiry details
        if data.get("full_name"):
            parts.append(f"Client: {data['full_name']}")
        if data.get("company"):
            parts.append(f"Company: {data['company']}")
        if data.get("service_interest"):
            parts.append(f"Service: {data['service_interest']}")
        if data.get("message"):
            parts.append(f"Message: {data['message']}")
        if data.get("priority"):
            parts.append(f"Priority: {data['priority']}")

    elif record_type == "EMAIL":
        # Email: focus on content and classification
        if data.get("sender_name"):
            parts.append(f"From: {data['sender_name']}")
        if data.get("company"):
            parts.append(f"Company: {data['company']}")
        if data.get("subject"):
            parts.append(f"Subject: {data['subject']}")
        if data.get("service_interest"):
            parts.append(f"Service: {data['service_interest']}")
        if data.get("body"):
            # Truncate body to avoid overly long embeddings
            body = data["body"][:1000] if len(data["body"]) > 1000 else data["body"]
            parts.append(f"Content: {body}")
        if data.get("email_type"):
            parts.append(f"Type: {data['email_type']}")

    elif record_type == "INVOICE":
        # Invoice: focus on client and financial data
        if data.get("client_name"):
            parts.append(f"Client: {data['client_name']}")
        if data.get("invoice_number"):
            parts.append(f"Invoice: {data['invoice_number']}")
        if data.get("total_amount"):
            parts.append(f"Amount: {data['total_amount']}")
        if data.get("items"):
            # Extract item descriptions
            items = data["items"]
            if isinstance(items, list):
                descriptions = [
                    item.get("description", "")
                    for item in items
                    if isinstance(item, dict)
                ]
                if descriptions:
                    parts.append(f"Items: {', '.join(descriptions)}")
        if data.get("notes"):
            parts.append(f"Notes: {data['notes']}")

    return " | ".join(parts) if parts else ""
