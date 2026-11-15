"""
/matrix: ask the same questions of many documents at once (documents × questions).

Each cell retrieves only from its own document (with the caller's ACL filters),
then the model answers in a few words and must quote the passage it used. A cell
whose quote cannot be found in the retrieved text is downgraded to "unverified",
so a cell never shows an answer the evidence does not contain.
"""

from __future__ import annotations

import asyncio
import re
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from src.contracts import RetrievalRequest
from src.core.access import access_filters_for
from src.core.dependency_injection import ChatUser
from src.core.logger import get_logger
from src.knowledge import get_knowledge_adapter
from src.services.llm.llm_service import get_llm_service

logger = get_logger(__name__)
router = APIRouter()

CELL_PROMPT = """You extract one fact from document excerpts.

Question: {question}

Excerpts (from one document):
{context}

Reply with JSON only:
{{"answer": "<at most 12 words, or NOT_FOUND>", "quote": "<the exact sentence from the excerpts that supports the answer, copied verbatim>", "excerpt": <number of the excerpt you used>}}
If the excerpts do not answer the question, reply {{"answer": "NOT_FOUND", "quote": "", "excerpt": 0}}."""


class MatrixIn(BaseModel):
    document_ids: List[str] = Field(..., min_length=1, max_length=50)
    questions: List[str] = Field(..., min_length=1, max_length=12)
    top_k: int = Field(default=4, ge=1, le=10)


class Cell(BaseModel):
    document_id: str
    question: str
    status: str                 # found | not_found | unverified | error
    answer: Optional[str] = None
    quote: Optional[str] = None
    page: Optional[int] = None
    source_name: Optional[str] = None


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().lower()


async def _cell(adapter, user, doc_id: str, question: str, top_k: int, sem: asyncio.Semaphore) -> Cell:
    async with sem:
        try:
            filters = access_filters_for(user)
            filters.document_ids = [doc_id]
            result = await adapter.retrieve(RetrievalRequest(query=question, top_k=top_k, filters=filters))
            ev = list(result.chunks)
            if not ev:
                return Cell(document_id=doc_id, question=question, status="not_found")
            context = "\n\n".join(f"[{i + 1}] (page {e.page or '?'}) {e.content}" for i, e in enumerate(ev))
            data = await get_llm_service().generate_json(CELL_PROMPT.format(question=question, context=context),
                                                         max_tokens=300, fast=True)
            answer = str(data.get("answer") or "").strip()
            if not answer or answer.upper().startswith("NOT_FOUND"):
                return Cell(document_id=doc_id, question=question, status="not_found", source_name=ev[0].source)
            idx = int(data.get("excerpt") or 0)
            src = ev[idx - 1] if 0 < idx <= len(ev) else ev[0]
            quote = str(data.get("quote") or "").strip()
            supported = bool(quote) and any(_norm(quote)[:120] in _norm(e.content) for e in ev)
            return Cell(document_id=doc_id, question=question, status="found" if supported else "unverified",
                        answer=answer[:160], quote=quote[:500] or None, page=src.page, source_name=src.source)
        except Exception as exc:  # one bad cell must not sink the grid
            logger.warning("Matrix cell failed", document_id=doc_id, error=str(exc))
            return Cell(document_id=doc_id, question=question, status="error", answer=str(exc)[:160])


@router.post("")
async def run_matrix(body: MatrixIn, user: ChatUser):
    try:
        adapter = get_knowledge_adapter(None)
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    sem = asyncio.Semaphore(3)
    cells = await asyncio.gather(*[
        _cell(adapter, user, d, q, body.top_k, sem) for d in body.document_ids for q in body.questions
    ])
    return {"cells": [c.model_dump() for c in cells]}
