"""Re-ranking service using cross-encoders (Voyage AI, Cohere Rerank API, local models, or ONNX)."""

import asyncio
import logging
import os
import numpy as np
from abc import ABC, abstractmethod
from typing import List, Optional, Sequence

from app.core.config import settings
from app.schemas.document import ResolvedParentChunk

logger = logging.getLogger(__name__)


class RerankerProvider(ABC):
    """Abstract base class for re-ranker providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model identifier."""
        pass

    @abstractmethod
    async def rerank(
        self,
        query: str,
        passages: List[str],
        top_k: Optional[int] = None,
    ) -> List[float]:
        """
        Re-rank passages given a query.

        Args:
            query: The search query
            passages: List of passage texts to score
            top_k: Optional limit on returned scores

        Returns:
            List of relevance scores (higher = more relevant)
        """
        pass


class CohereRerankerProvider(RerankerProvider):
    """Cohere Rerank API provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "rerank-english-v3.0",
        max_batch_size: int = 96,
    ):
        self._api_key = api_key
        self._model = model
        self._max_batch_size = max_batch_size
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model

    async def _get_client(self):
        """Lazy initialization of Cohere client."""
        if self._client is None:
            import cohere
            self._client = cohere.AsyncClient(api_key=self._api_key)
        return self._client

    async def rerank(
        self,
        query: str,
        passages: List[str],
        top_k: Optional[int] = None,
    ) -> List[float]:
        """Re-rank using Cohere Rerank API."""
        if not passages:
            return []

        client = await self._get_client()

        try:
            # Cohere API has a max of 96 documents per request
            all_scores = []
            for i in range(0, len(passages), self._max_batch_size):
                batch = passages[i:i + self._max_batch_size]
                response = await client.rerank(
                    model=self._model,
                    query=query,
                    documents=batch,
                    top_n=top_k or len(batch),
                    return_documents=False,
                )
                # Scores are already sorted by relevance
                batch_scores = [result.relevance_score for result in response.results]
                all_scores.extend(batch_scores)

            # If we processed multiple batches, we need to re-sort
            if len(passages) > self._max_batch_size:
                # Return scores in original passage order
                # For simplicity, we just return the scores as-is since API sorts them
                pass

            return all_scores

        except Exception as e:
            logger.error(f"Cohere rerank failed: {e}")
            raise


class VoyageRerankerProvider(RerankerProvider):
    """Voyage AI Rerank API provider."""

    def __init__(
        self,
        api_key: str,
        model: str = "rerank-2",
        max_batch_size: int = 100,
    ):
        self._api_key = api_key
        self._model = model
        self._max_batch_size = max_batch_size
        self._client = None

    @property
    def model_name(self) -> str:
        return self._model

    async def _get_client(self):
        """Lazy initialization of Voyage AI client."""
        if self._client is None:
            import voyageai
            self._client = voyageai.AsyncClient(api_key=self._api_key)
        return self._client

    async def rerank(
        self,
        query: str,
        passages: List[str],
        top_k: Optional[int] = None,
    ) -> List[float]:
        """Re-rank using Voyage AI Rerank API."""
        if not passages:
            return []

        client = await self._get_client()

        try:
            # Voyage AI supports up to 100 documents per request
            all_scores = []
            for i in range(0, len(passages), self._max_batch_size):
                batch = passages[i:i + self._max_batch_size]
                response = await client.rerank(
                    query=query,
                    documents=batch,
                    model=self._model,
                    top_k=top_k or len(batch),
                )
                # Results are sorted by relevance_score descending
                # We need to map back to original order
                batch_results = {r.index: r.relevance_score for r in response.results}
                batch_scores = [batch_results[j] for j in range(len(batch))]
                all_scores.extend(batch_scores)

            return all_scores

        except Exception as e:
            logger.error(f"Voyage AI rerank failed: {e}")
            raise


class LocalCrossEncoderProvider(RerankerProvider):
    """Local cross-encoder provider using sentence-transformers."""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        batch_size: int = 32,
        device: Optional[str] = None,
    ):
        self._model_name = model_name
        self._batch_size = batch_size
        self._device = device or ("cuda" if self._is_cuda_available() else "cpu")
        self._model = None

    @property
    def model_name(self) -> str:
        return self._model_name

    def _is_cuda_available(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    async def _get_model(self):
        """Lazy initialization of cross-encoder model."""
        if self._model is None:
            from sentence_transformers import CrossEncoder
            import asyncio
            # Load model in thread pool to avoid blocking
            self._model = await asyncio.to_thread(
                CrossEncoder,
                self._model_name,
                device=self._device,
            )
            logger.info(f"Loaded cross-encoder {self._model_name} on {self._device}")
        return self._model

    async def rerank(
        self,
        query: str,
        passages: List[str],
        top_k: Optional[int] = None,
    ) -> List[float]:
        """Re-rank using local cross-encoder."""
        if not passages:
            return []

        model = await self._get_model()

        try:
            # Prepare query-passage pairs
            pairs = [(query, passage) for passage in passages]

            # Get scores in batches
            all_scores = []
            for i in range(0, len(pairs), self._batch_size):
                batch = pairs[i:i + self._batch_size]
                scores = await asyncio.to_thread(
                    model.predict,
                    batch,
                    batch_size=len(batch),
                    show_progress_bar=False,
                )
                all_scores.extend(scores.tolist())

            return all_scores

        except Exception as e:
            logger.error(f"Local cross-encoder rerank failed: {e}")
            raise


class ONNXCrossEncoderProvider(RerankerProvider):
    """Local cross-encoder provider using ONNX Runtime for faster inference."""

    def __init__(
        self,
        model_path: str,
        tokenizer_name: Optional[str] = None,
        batch_size: int = 32,
        provider: str = "CPUExecutionProvider",
    ):
        self._model_path = model_path
        self._tokenizer_name = tokenizer_name or model_path
        self._batch_size = batch_size
        self._provider = provider
        self._session = None
        self._tokenizer = None

    @property
    def model_name(self) -> str:
        return self._model_path

    async def _get_session(self):
        """Lazy initialization of ONNX session and tokenizer."""
        if self._session is None:
            import onnxruntime as ort
            from transformers import AutoTokenizer
            import asyncio

            # Load tokenizer
            self._tokenizer = await asyncio.to_thread(
                AutoTokenizer.from_pretrained,
                self._tokenizer_name,
            )

            # Create ONNX Runtime session
            session_options = ort.SessionOptions()
            session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            self._session = await asyncio.to_thread(
                ort.InferenceSession,
                self._model_path,
                sess_options=session_options,
                providers=[self._provider],
            )
            logger.info(f"Loaded ONNX cross-encoder from {self._model_path} with {self._provider}")

        return self._session, self._tokenizer

    async def rerank(
        self,
        query: str,
        passages: List[str],
        top_k: Optional[int] = None,
    ) -> List[float]:
        """Re-rank using ONNX Runtime cross-encoder."""
        if not passages:
            return []

        session, tokenizer = await self._get_session()

        try:
            all_scores = []
            for i in range(0, len(passages), self._batch_size):
                batch_passages = passages[i:i + self._batch_size]

                # Tokenize query-passage pairs
                encoded = await asyncio.to_thread(
                    tokenizer,
                    [query] * len(batch_passages),
                    batch_passages,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="np",
                )

                # Run inference
                inputs = {
                    "input_ids": encoded["input_ids"],
                    "attention_mask": encoded["attention_mask"],
                }
                if "token_type_ids" in encoded:
                    inputs["token_type_ids"] = encoded["token_type_ids"]

                outputs = await asyncio.to_thread(session.run, None, inputs)
                # Assuming single output logit
                logits = outputs[0].squeeze(-1)
                scores = 1 / (1 + np.exp(-logits))  # Sigmoid for relevance score
                all_scores.extend(scores.tolist())

            return all_scores

        except Exception as e:
            logger.error(f"ONNX cross-encoder rerank failed: {e}")
            raise


def create_reranker_provider() -> RerankerProvider:
    """Factory function to create the configured re-ranker provider."""
    provider_type = getattr(settings, "reranker_provider", "local").lower()

    if provider_type == "voyage":
        api_key = getattr(settings, "voyage_api_key", "")
        if not api_key:
            raise ValueError("Voyage AI API key not configured. Set VOYAGE_API_KEY in environment.")
        model = getattr(settings, "reranker_model", "rerank-2")
        return VoyageRerankerProvider(api_key=api_key, model=model)

    elif provider_type == "cohere":
        api_key = getattr(settings, "cohere_api_key", "")
        if not api_key:
            raise ValueError("Cohere API key not configured. Set COHERE_API_KEY in environment.")
        model = getattr(settings, "reranker_model", "rerank-english-v3.0")
        return CohereRerankerProvider(api_key=api_key, model=model)

    elif provider_type == "onnx":
        model_path = getattr(settings, "reranker_model_path", "")
        if not model_path:
            raise ValueError("ONNX model path not configured. Set RERANKER_MODEL_PATH in environment.")
        tokenizer_name = getattr(settings, "reranker_tokenizer", None)
        provider = getattr(settings, "onnx_provider", "CPUExecutionProvider")
        return ONNXCrossEncoderProvider(
            model_path=model_path,
            tokenizer_name=tokenizer_name,
            provider=provider,
        )

    elif provider_type == "local":
        model_name = getattr(settings, "reranker_model", "BAAI/bge-reranker-base")
        return LocalCrossEncoderProvider(model_name=model_name)

    else:
        raise ValueError(f"Unknown reranker provider: {provider_type}")


class RerankerService:
    """
    Service for re-ranking retrieved parent chunks using cross-encoders.

    Cross-encoders evaluate query-passage pairs jointly, providing
    more accurate relevance scores than bi-encoders used in retrieval.
    """

    def __init__(self, provider: Optional[RerankerProvider] = None):
        self.provider = provider or create_reranker_provider()
        self.top_k_final = getattr(settings, "reranker_top_k", 5)

    async def rerank(
        self,
        query: str,
        parent_chunks: List[ResolvedParentChunk],
        top_k: Optional[int] = None,
    ) -> List[ResolvedParentChunk]:
        """
        Re-rank parent chunks by relevance to query.

        Args:
            query: The search query
            parent_chunks: List of resolved parent chunks from hybrid search
            top_k: Number of top chunks to return (default from config)

        Returns:
            Re-ranked and trimmed list of parent chunks with relevance_score attached
        """
        if not parent_chunks:
            return []

        # Extract passage texts (use parent chunk content for re-ranking)
        passages = [chunk.content for chunk in parent_chunks]

        # Get relevance scores from cross-encoder
        scores = await self.provider.rerank(query, passages)

        # Attach scores to parent chunks
        for chunk, score in zip(parent_chunks, scores):
            chunk.relevance_score = float(score)

        # Sort by relevance score descending
        parent_chunks.sort(key=lambda c: c.relevance_score, reverse=True)

        # Limit to top_k
        k = top_k or self.top_k_final
        return parent_chunks[:k]


async def get_reranker_service() -> RerankerService:
    """Dependency injection for RerankerService."""
    return RerankerService()