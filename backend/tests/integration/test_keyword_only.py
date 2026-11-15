"""Keyword-only (BM25) retrieval when no embedding model exists, e.g. ASSAY_LOCAL_COMPUTE=0 and no embed key."""

import pytest

from src.infrastructure.vector_store.qdrant_store import QdrantStore
from src.infrastructure.vector_store.sparse_encoder import SparseEncoder


@pytest.mark.asyncio
async def test_sparse_only_index_and_search(services):
    store = QdrantStore(collection="kwtest")
    enc = SparseEncoder()
    texts = [
        "The cafeteria menu changed in September.",
        "Kestrel Metals raised steel coil prices by 18 percent under Annex C.",
        "Board minutes note a new audit committee chair.",
    ]
    payloads = [{"document_id": f"d{i}", "content": t, "source": "x.pdf", "page": i + 1,
                 "chunk_index": 0, "tenant_id": "default", "visibility": "public", "acl": ["public"]}
                for i, t in enumerate(texts)]
    await store.upsert(payloads, None, enc.encode_documents(texts))
    assert store.keyword_only and store.collection == "kwtest_kw"

    hits = await store.hybrid_search(None, enc.encode_query("steel coil price increase"), top_k=2)
    assert hits and "Kestrel" in hits[0].content

    # A dense index is a different collection; switching back never touches the keyword one.
    store.set_keyword_only(False)
    assert store.collection == "kwtest"


@pytest.mark.asyncio
async def test_embedding_service_reports_unavailable(monkeypatch):
    from src.providers import router
    from src.services.llm.embedding_service import EmbeddingService

    async def none(role):
        raise RuntimeError("No model available for role 'embed'")

    monkeypatch.setattr(router, "resolve", none)
    assert await EmbeddingService().available() is False


@pytest.mark.asyncio
async def test_documents_found_after_restart_in_keyword_mode(services):
    """A fresh store (as after a restart) starts in dense mode but must still see keyword-only chunks."""
    store = QdrantStore(collection="kwrestart")
    enc = SparseEncoder()
    await store.upsert([{"document_id": "d1", "content": "steel coil", "source": "a.pdf", "page": 1, "chunk_index": 0,
                         "tenant_id": "default", "visibility": "public", "acl": ["public"]}], None, enc.encode_documents(["steel coil"]))
    fresh = QdrantStore(collection="kwrestart")
    assert fresh.keyword_only is False
    assert await fresh.count_all_modes() == 1
