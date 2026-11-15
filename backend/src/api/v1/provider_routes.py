"""
/providers: what Assay found on this machine, which model each role uses,
and a one-click connection test. Backs the Models screen.
"""

from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.providers import PROVIDERS, ROLES
from src.providers import router as prov

router = APIRouter()


@router.get("")
async def list_providers(refresh: bool = False):
    """Detected providers (env vars, credential files, local ports, CLIs)."""
    found = await prov.detected(refresh=refresh)
    return {"providers": [d.to_dict() for d in found], "count": len(found)}


@router.get("/catalog")
async def catalog():
    """Every provider Assay supports, detected or not, with how to enable it."""
    return {"providers": [
        {"id": p.id, "name": p.name, "kind": p.kind, "prefix": p.prefix, "caps": sorted(p.caps),
         "env": [list(g) for g in p.env], "files": list(p.files), "port": p.port, "icon": p.icon,
         "needs": p.needs, "risk": p.risk}
        for p in PROVIDERS
    ], "count": len(PROVIDERS)}


@router.get("/roles")
async def roles():
    """The model each agent role resolves to right now."""
    out = {}
    for role in ROLES:
        try:
            model, base = await prov.resolve(role)
            out[role] = {"model": model, "api_base": base, "error": None}
        except RuntimeError as exc:
            out[role] = {"model": None, "api_base": None, "error": str(exc)}
    return out


class TestRequest(BaseModel):
    model: Optional[str] = None
    role: str = "synthesis"


@router.post("/test")
async def test(req: TestRequest):
    """Send a tiny prompt (or embed one word) and report latency."""
    t0 = time.perf_counter()
    try:
        if req.role == "embed":
            vec = await prov.embed(["assay"], model=req.model)
            return {"ok": True, "dimension": len(vec[0]), "latency_ms": round((time.perf_counter() - t0) * 1000)}
        llm = prov.LLMRouter(req.role, model=req.model)
        text = await llm.generate("Reply with the single word: ready", max_tokens=8, temperature=0)
        return {"ok": True, "model": llm.model, "reply": text.strip()[:40],
                "latency_ms": round((time.perf_counter() - t0) * 1000)}
    except Exception as exc:  # report, don't 500: this is a diagnostics endpoint
        raise HTTPException(status_code=502, detail=f"{type(exc).__name__}: {exc}")
