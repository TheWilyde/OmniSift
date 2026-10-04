"""Embedding provider abstraction and implementations."""

import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Embedding vector dimension."""
        pass

    @property
    @abstractmethod
    def max_batch_size(self) -> int:
        """Maximum batch size for embedding requests."""
        pass

    @abstractmethod
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (list of floats)
        """
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        pass


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embedding provider using gemini-embedding-2 model."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-embedding-2",
        output_dimensionality: int = 1536,
        batch_size: int = 32,
    ):
        self._api_key = api_key
        self._model = model
        self._output_dimensionality = output_dimensionality
        self._batch_size = batch_size
        self._client = None

    @property
    def dimension(self) -> int:
        return self._output_dimensionality

    @property
    def max_batch_size(self) -> int:
        return self._batch_size

    async def _get_client(self):
        """Lazy initialization of Gemini client."""
        if self._client is None:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._client = genai
        return self._client

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts using Gemini."""
        if not texts:
            return []

        client = await self._get_client()

        # Process in batches
        all_embeddings = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]
            try:
                result = await asyncio.to_thread(
                    client.embed_content,
                    model=self._model,
                    content=batch,
                    task_type="retrieval_document",
                    output_dimensionality=self._output_dimensionality,
                )
                # The legacy Gemini SDK returns a dict (`embedding`) for
                # batch input, while some versions expose Embedding objects.
                if isinstance(result, dict):
                    batch_embeddings = result["embedding"]
                else:
                    batch_embeddings = [e.values for e in result.embeddings]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"Gemini embedding batch failed: {e}")
                raise

        return all_embeddings

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """OpenAI embedding provider (text-embedding-3-small = 1536 dims)."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        batch_size: int = 32,
    ):
        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._batch_size = batch_size
        self._client = None

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def max_batch_size(self) -> int:
        return self._batch_size

    async def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts using OpenAI."""
        if not texts:
            return []

        client = await self._get_client()

        all_embeddings = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i:i + self._batch_size]
            try:
                response = await client.embeddings.create(
                    model=self._model,
                    input=batch,
                    dimensions=self._dimension,
                )
                batch_embeddings = [e.embedding for e in response.data]
                all_embeddings.extend(batch_embeddings)
            except Exception as e:
                logger.error(f"OpenAI embedding batch failed: {e}")
                raise

        return all_embeddings

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []


class LocalEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers embedding provider."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
    ):
        self._model_name = model_name
        self._batch_size = batch_size
        self._model = None

    @property
    def dimension(self) -> int:
        # Default dimensions for common models
        dims = {
            "sentence-transformers/all-MiniLM-L6-v2": 384,
            "sentence-transformers/all-mpnet-base-v2": 768,
            "BAAI/bge-large-en-v1.5": 1024,
            "BAAI/bge-base-en-v1.5": 768,
        }
        return dims.get(self._model_name, 384)

    @property
    def max_batch_size(self) -> int:
        return self._batch_size

    async def _get_model(self):
        """Lazy initialization of sentence-transformers model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self._model = SentenceTransformer(self._model_name, device=device)
        return self._model

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts locally."""
        if not texts:
            return []

        model = await self._get_model()

        try:
            embeddings = model.encode(
                texts,
                batch_size=self._batch_size,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Local embedding batch failed: {e}")
            raise

    async def embed_text(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        embeddings = await self.embed_texts([text])
        return embeddings[0] if embeddings else []


def create_embedding_provider() -> EmbeddingProvider:
    """Factory function to create the configured embedding provider."""
    provider_type = settings.embedding_provider.lower()

    if provider_type == "gemini":
        if not settings.gemini_api_key:
            raise ValueError("Gemini API key not configured. Set GEMINI_API_KEY in environment.")
        return GeminiEmbeddingProvider(
            api_key=settings.gemini_api_key,
            model=settings.embedding_model,
            output_dimensionality=settings.gemini_output_dimensionality,
            batch_size=settings.embedding_batch_size,
        )
    elif provider_type == "openai":
        from app.core.config import settings as s
        api_key = getattr(s, "openai_api_key", "")
        if not api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in environment.")
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimension,
            batch_size=settings.embedding_batch_size,
        )
    elif provider_type == "local":
        return LocalEmbeddingProvider(
            model_name=settings.embedding_model,
            batch_size=settings.embedding_batch_size,
        )
    else:
        raise ValueError(f"Unknown embedding provider: {provider_type}")
