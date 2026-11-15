"""Evaluation endpoints: per-message scores (UI) and the offline eval harness."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.core.dependency_injection import AdminUser, ChatUser, CurrentUser, DbSession
from src.infrastructure.database import Evaluation

router = APIRouter()


import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

DATASET_DIR = Path(os.getenv("ASSAY_EVAL_DATASETS", Path(__file__).resolve().parents[4] / "evals" / "datasets"))
RUNS_DIR = Path(os.getenv("ASSAY_EVAL_RUNS", Path.cwd() / "data" / "evals"))


def _dataset_file(name: str) -> Path:
    """Only named JSON files inside the datasets folder; no paths."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", name) or ".." in name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid dataset name")
    path = DATASET_DIR / (name if name.endswith(".json") else f"{name}.json")
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Dataset not found: {name}")
    return path


class EvalRunRequest(BaseModel):
    dataset: str = Field(default="sample", description="File name in evals/datasets (no path)")
    top_k: int = Field(default=8, ge=1, le=50)
    judge: bool = Field(default=False, description="Also run LLM-judged faithfulness/relevance")
    backend: Optional[str] = None
    max_questions: Optional[int] = Field(default=None, ge=1)


@router.get("/datasets")
async def datasets(user: CurrentUser):
    out = []
    for f in sorted(DATASET_DIR.glob("*.json")):
        try:
            n = len(json.loads(f.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
        out.append({"name": f.stem, "questions": n})
    return {"datasets": out}


@router.get("/runs")
async def runs(user: CurrentUser, limit: int = 20):
    """Saved eval runs, newest first (summary only)."""
    out = []
    for f in sorted(RUNS_DIR.glob("*.json"), reverse=True)[:limit]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        d.pop("results", None)
        out.append(d)
    return {"runs": out}


@router.post("/run")
async def run_evaluation(body: EvalRunRequest, admin: AdminUser) -> Dict[str, Any]:
    """Admin only: runs every question through the current models (costs tokens)."""
    from src.evaluation import EvalHarness, load_dataset
    from src.providers import router as prov
    dataset = load_dataset(str(_dataset_file(body.dataset)))
    if body.max_questions:
        dataset = dataset[: body.max_questions]
    harness = EvalHarness(backend=body.backend)
    report = await harness.run(dataset, top_k=body.top_k, judge=body.judge)
    data = report.model_dump()
    try:
        model, _ = await prov.resolve("synthesis")
    except RuntimeError:
        model = None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    data.update({"run_id": stamp, "dataset": body.dataset, "model": model, "created_at": stamp,
                 "local_compute": os.getenv("ASSAY_LOCAL_COMPUTE", "1")})
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    (RUNS_DIR / f"{stamp}.json").write_text(json.dumps(data, indent=1, default=str), encoding="utf-8")
    return data


# Declared last so /datasets and /runs are not captured by the path parameter.
@router.get("/{message_id}")
async def message_evaluation(message_id: str, db: DbSession, user: ChatUser):
    try:
        mid = uuid.UUID(message_id)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No evaluation")
    row = await db.scalar(select(Evaluation).where(Evaluation.message_id == mid))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No evaluation for this message")
    return {"message_id": message_id, "faithfulness": row.faithfulness, "relevance": row.relevance,
            "precision": row.precision, "recall": row.recall, "overall_score": row.overall_score, "details": row.details}
