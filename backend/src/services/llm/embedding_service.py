"""
NVIDIA NIM embedding client with batching, retries and an LRU cache.

Asymmetric models (nv-embedqa) need ``input_type`` = ``query`` for questions and
``passage`` for documents; this service always sets it correctly.
"""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from typing import List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.core.config import settings
from src.core.logger import get_logger, log_timing

logger = get_logger(__name__)


class EmbeddingError(RuntimeError):
    pass


class EmbeddingService:
    """Embeddings from any provider (router role "embed"), with an LRU cache.

    Model: ASSAY_EMBED_MODEL, else the best detected provider, else the
    bundled offline ONNX model. Vector size follows the model.
    """

    def __init__(self, model: Optional[str] = None, dimensions: Optional[int] = None, **_legacy):
        self.model = model
        self.dimensions = dimensions or settings.nvidia_embed_dimensions
        self.batch_size = settings.embedding_batch_size
        self._cache: "OrderedDict[str, List[float]]" = OrderedDict()
        self._cache_size = settings.embedding_cache_size
        self._base: Optional[str] = None

    @classmethod
    async def aclose(cls) -> None:
        return None

    async def available(self) -> bool:
        """False when no embedding model can be resolved (keyword-only mode)."""
        try:
            await self._target()
            return True
        except RuntimeError:
            return False

    async def _target(self) -> str:
        if self.model is None:
            from src.providers.router import resolve
            self.model, self._base = await resolve("embed")
            logger.info("Embedding model selected", model=self.model)
        return self.model

    @staticmethod
    def _key(text: str, input_type: str) -> str:
        return hashlib.sha1(f"{input_type}:{text}".encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[List[float]]:
        vec = self._cache.get(key)
        if vec is not None:
            self._cache.move_to_end(key)
        return vec

    def _cache_put(self, key: str, vec: List[float]) -> None:
        self._cache[key] = vec
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)

    async def _embed_batch(self, texts: List[str], input_type: str) -> List[List[float]]:
        model = await self._target()
        from src.providers import builtin
        if builtin.handles(model):
            return await builtin.embed(model, texts)
        import litellm
        from src.providers.router import _kwargs
        kw = _kwargs(model, self._base)
        if model.split("/", 1)[0] in {"nvidia_nim", "cohere", "voyage", "jina_ai", "bedrock"}:
            kw["input_type"] = {"cohere": "search_" + ("query" if input_type == "query" else "document")}.get(
                model.split("/", 1)[0], input_type)
        if self.dimensions:
            kw["dimensions"] = self.dimensions
        try:
            resp = await litellm.aembedding(model=model, input=texts, **kw)
        except Exception as exc:
            raise EmbeddingError(f"{model}: {exc}") from exc
        data = sorted(resp.data, key=lambda d: d.get("index", 0) if isinstance(d, dict) else 0)
        return [d["embedding"] if isinstance(d, dict) else d.embedding for d in data]

    @log_timing("embed_texts")
    async def embed_texts(self, texts: List[str], input_type: str = "passage", batch_size: Optional[int] = None) -> List[List[float]]:
        """Embed many texts (documents by default) with batching + cache."""
        if not texts:
            return []
        batch_size = batch_size or self.batch_size
        results: List[Optional[List[float]]] = [None] * len(texts)
        pending: List[int] = []
        for i, text in enumerate(texts):
            cached = self._cache_get(self._key(text, input_type))
            if cached is not None:
                results[i] = cached
            else:
                pending.append(i)
        for start in range(0, len(pending), batch_size):
            idxs = pending[start:start + batch_size]
            vectors = await self._embed_batch([texts[i] for i in idxs], input_type)
            for i, vec in zip(idxs, vectors):
                results[i] = vec
                self._cache_put(self._key(texts[i], input_type), vec)
        return [r for r in results if r is not None]

    async def embed_query(self, query: str) -> List[float]:
        return (await self.embed_texts([query], input_type="query"))[0]

    async def embed_queries(self, queries: List[str]) -> List[List[float]]:
        return await self.embed_texts(queries, input_type="query")

    async def embed_text(self, text: str, use_cache: bool = True) -> List[float]:
        """Backward-compatible single-passage embed."""
        return (await self.embed_texts([text], input_type="passage"))[0]

    def clear_cache(self) -> None:
        self._cache.clear()


_default: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _default
    if _default is None:
        _default = EmbeddingService()
    return _default


def set_embedding_service(service: Optional[EmbeddingService]) -> None:
    global _default
    _default = service
