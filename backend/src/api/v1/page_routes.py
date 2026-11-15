"""
Page images and highlighted regions for cited passages (PDFs).

GET  /documents/{id}/pages/{n}.png      render page n (1-based) as PNG
POST /documents/{id}/pages/{n}/locate   {"text": "..."} -> rectangles (0..1, top-left origin)

Located on demand from the stored original, so documents indexed before this
feature get highlights too. Same access rules as downloading the file.
"""

from __future__ import annotations

import io
import os
import re
from typing import List

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.v1.ingestion_routes import _get_owned
from src.core.config import settings
from src.core.dependency_injection import CurrentUser, DbSession

router = APIRouter()


def _pdf_path(doc, document_id: str) -> str:
    if (doc.file_type or "").lower() != "pdf":
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Page images are available for PDFs only")
    path = os.path.join(settings.upload_dir, f"{document_id}.pdf")
    if not os.path.exists(path):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Original file not found")
    return path


def _open_page(path: str, n: int):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    if n < 1 or n > len(pdf):
        pdf.close()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such page")
    return pdf, pdf[n - 1]


@router.get("/documents/{document_id}/pages/{n}.png")
async def page_image(document_id: str, n: int, db: DbSession, user: CurrentUser, scale: float = 1.6):
    doc = await _get_owned(db, user, document_id)
    pdf, page = _open_page(_pdf_path(doc, document_id), n)
    try:
        img = page.render(scale=max(0.5, min(scale, 3.0))).to_pil()
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
    finally:
        pdf.close()
    return Response(buf.getvalue(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


class LocateIn(BaseModel):
    text: str = Field(..., min_length=3, max_length=8000)


def _phrases(text: str) -> List[str]:
    """Searchable pieces of a passage: sentences/lines of a useful length, de-duplicated."""
    text = re.sub(r"[ \t]+", " ", text)
    parts = re.split(r"(?<=[.!?;:])\s+|\n+", text)
    out, seen = [], set()
    for p in parts:
        p = p.strip(" -•*#|")
        if len(p) < 18:
            continue
        p = p[:90]                      # long sentences: the start is enough to find the line
        if p.lower() not in seen:
            seen.add(p.lower())
            out.append(p)
    return out[:12]


@router.post("/documents/{document_id}/pages/{n}/locate")
async def locate(document_id: str, n: int, body: LocateIn, db: DbSession, user: CurrentUser):
    doc = await _get_owned(db, user, document_id)
    pdf, page = _open_page(_pdf_path(doc, document_id), n)
    try:
        width, height = page.get_size()
        tp = page.get_textpage()
        boxes: List[List[float]] = []          # PDF coords: left, bottom, right, top
        for phrase in _phrases(body.text):
            searcher = tp.search(phrase, match_case=False, match_whole_word=False)
            hit = searcher.get_next()
            if not hit:
                continue
            start, count = hit
            boxes.extend(list(tp.get_rect(i)) for i in range(tp.count_rects(start, count)))
        tp.close()
    finally:
        pdf.close()
    rects = [[round(l / width, 4), round(1 - t / height, 4), round(r / width, 4), round(1 - b / height, 4)]
             for l, b, r, t in _merge_lines(boxes)]
    return {"page": n, "width": width, "height": height, "rects": rects, "found": bool(rects)}


def _merge_lines(boxes: List[List[float]]) -> List[List[float]]:
    """Glyph boxes -> one padded box per text line (like a marker stroke)."""
    lines: List[List[float]] = []
    for l, b, r, t in sorted(boxes, key=lambda x: (-x[3], x[0])):
        mid = (b + t) / 2
        for line in lines:
            if line[1] - 2 <= mid <= line[3] + 2:
                line[0], line[1], line[2], line[3] = min(line[0], l), min(line[1], b), max(line[2], r), max(line[3], t)
                break
        else:
            lines.append([l, b, r, t])
    padded = []
    for l, b, r, t in lines:
        h = max(t - b, 6.0)
        padded.append([l - 2, b - h * 0.3, r + 2, t + h * 0.3])
    return padded[:40]
