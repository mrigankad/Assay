"""
Built-in offline embeddings and reranking (ONNX via fastembed).

Works with no API key and no network after the first model download, so
Assay always has a retrieval stack even on an air-gapped machine.
Model strings: "builtin/<fastembed model name>".
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

ALIASES = {
    "bge-small-en-v1.5": "BAAI/bge-small-en-v1.5",
    "bge-m3": "BAAI/bge-m3",
    "ms-marco-MiniLM-L-6-v2": "Xenova/ms-marco-MiniLM-L-6-v2",
    "bge-reranker-base": "BAAI/bge-reranker-base",
}


def handles(model: str) -> bool:
    return model.startswith("builtin/")


def available() -> bool:
    try:
        import fastembed  # noqa: F401
        return True
    except ImportError:
        return False


def _name(model: str) -> str:
    n = model.split("/", 1)[1]
    return ALIASES.get(n, n)


@lru_cache(maxsize=4)
def _embedder(name: str):
    from fastembed import TextEmbedding
    return TextEmbedding(model_name=name)


@lru_cache(maxsize=4)
def _reranker(name: str):
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    return TextCrossEncoder(model_name=name)


async def embed(model: str, texts: list[str]) -> list[list[float]]:
    def run():
        return [v.tolist() for v in _embedder(_name(model)).embed(texts)]
    return await asyncio.to_thread(run)


async def rerank(model: str, query: str, docs: list[str], top_n: int) -> list[tuple[int, float]]:
    def run():
        scores = list(_reranker(_name(model)).rerank(query, docs))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, float(s)) for i, s in ranked[:top_n]]
    return await asyncio.to_thread(run)
