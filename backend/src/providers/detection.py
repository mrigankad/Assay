"""
Auto-detection: find every provider this machine can reach, without setup.

Order (cheap to expensive):
  1. env vars from the catalogue
  2. credential files (~/.aws, gcloud ADC, ~/.oci, HF token ...)
  3. local ports, fingerprinted (several runtimes share 8000 / 8080)
  4. CLI binaries on PATH (reported, never enabled automatically)

Nothing here sends a prompt or reads a token's contents.
"""

from __future__ import annotations

import asyncio
import os
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import httpx

from .catalog import PROVIDERS, BY_ID, CLI_BINARIES, ProviderSpec

PROBE_TIMEOUT = float(os.getenv("ASSAY_PROBE_TIMEOUT", "0.6"))
LOCAL_HOST = os.getenv("ASSAY_LOCAL_HOST", "127.0.0.1")


@dataclass
class Detected:
    id: str
    name: str
    kind: str
    caps: list[str]
    via: str                       # "env:OPENAI_API_KEY", "file:~/.aws/credentials", "port:11434", "cli:claude"
    api_base: Optional[str] = None
    models: list[str] = field(default_factory=list)
    enabled: bool = True           # CLI backends are found but off until the user opts in
    icon: Optional[str] = None
    needs: Optional[str] = None
    risk: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


_PLACEHOLDERS = ("your-", "your_", "<", "changeme", "xxx", "sk-...")


def _real(value: Optional[str]) -> bool:
    """A set, non-placeholder value (templates ship things like 'your-api-key-here')."""
    return bool(value) and not value.strip().lower().startswith(_PLACEHOLDERS)


def _env_hit(spec: ProviderSpec, environ: dict[str, str]) -> Optional[str]:
    for group in spec.env:
        if all(_real(environ.get(v)) for v in group):
            return "env:" + "+".join(group)
    return None


def _file_hit(spec: ProviderSpec) -> Optional[str]:
    for f in spec.files:
        p = _expand(f)
        if "%" not in str(p) and p.is_file():
            return "file:" + f
    return None


def _base_from_env(spec: ProviderSpec, environ: dict[str, str]) -> Optional[str]:
    for g in spec.env:
        for v in g:
            if v.endswith(("_API_BASE", "_HOST")) and environ.get(v):
                base = environ[v]
                return base if base.startswith("http") else f"http://{base}"
    return spec.base_url


# ------------------------------------------------------------------ ports

def _fingerprint(spec_id: str, status: int, body) -> bool:
    """Decide if a 200 on a shared port really is this runtime."""
    if status != 200:
        return False
    if spec_id == "ollama":
        return isinstance(body, dict) and "models" in body
    if spec_id == "tgi":
        return isinstance(body, dict) and "model_id" in body
    if spec_id == "llamacpp":
        data = body.get("data", []) if isinstance(body, dict) else []
        return any(m.get("owned_by") == "llamacpp" for m in data if isinstance(m, dict))
    if spec_id == "vllm":
        data = body.get("data", []) if isinstance(body, dict) else []
        return any(m.get("owned_by") == "vllm" for m in data if isinstance(m, dict))
    if spec_id == "triton":
        return True
    return True


def _models_from(spec_id: str, body) -> list[str]:
    if not isinstance(body, dict):
        return []
    if spec_id == "ollama":
        return [m.get("name") for m in body.get("models", []) if m.get("name")]
    if "data" in body:
        return [m.get("id") for m in body["data"] if isinstance(m, dict) and m.get("id")]
    if "model_id" in body:
        return [body["model_id"]]
    return []


# Specific fingerprints first so a generic match can't steal a shared port.
_PORT_ORDER = ["ollama", "lm_studio", "tgi", "vllm", "llamacpp", "triton", "localai", "sglang",
               "jan", "gpt4all", "koboldcpp", "textgen_webui", "xinference", "infinity",
               "docker_model_runner", "litellm_proxy", "mlx"]


async def _probe(client: httpx.AsyncClient, spec: ProviderSpec, base: str):
    try:
        r = await client.get(base + spec.probe)
        try:
            body = r.json()
        except ValueError:
            body = None
        return r.status_code, body
    except (httpx.HTTPError, OSError):
        return None, None


async def _scan_ports(skip: set[str]) -> list[Detected]:
    specs = [BY_ID[i] for i in _PORT_ORDER if i in BY_ID and BY_ID[i].port and i not in skip]
    claimed: set[int] = set()
    found: list[Detected] = []
    async with httpx.AsyncClient(timeout=PROBE_TIMEOUT) as client:
        results = await asyncio.gather(
            *[_probe(client, s, f"http://{LOCAL_HOST}:{s.port}") for s in specs]
        )
        for spec, (status, body) in zip(specs, results):
            if spec.port in claimed or status is None or not _fingerprint(spec.id, status, body):
                continue
            claimed.add(spec.port)
            base = f"http://{LOCAL_HOST}:{spec.port}"
            if spec.prefix == "openai" or spec.id in {"lm_studio", "vllm", "docker_model_runner"}:
                base += "/engines/v1" if spec.id == "docker_model_runner" else "/v1"
            models = _models_from(spec.id, body)
            if not models and spec.id != "ollama":
                s2, b2 = await _probe(client, ProviderSpec(**{**spec.__dict__, "probe": "/v1/models"}),
                                      f"http://{LOCAL_HOST}:{spec.port}")
                models = _models_from(spec.id, b2) if s2 == 200 else []
            found.append(Detected(spec.id, spec.name, spec.kind, sorted(spec.caps), f"port:{spec.port}",
                                  api_base=base, models=models, icon=spec.icon, needs=spec.needs))
    return found


# ----------------------------------------------------- local compute policy

def local_compute_allowed(environ: Optional[dict[str, str]] = None) -> bool:
    """ASSAY_LOCAL_COMPUTE=0 means: never run model weights on this machine.

    Local servers that only *forward* to a cloud (Ollama "-cloud" models,
    a LiteLLM proxy) stay usable; everything that runs weights here is off.
    """
    env = os.environ if environ is None else environ
    return env.get("ASSAY_LOCAL_COMPUTE", "1").strip().lower() not in {"0", "false", "no", "off"}


def is_cloud_model(name: str) -> bool:
    n = name.lower()
    return n.endswith("-cloud") or n.endswith(":cloud")


def _apply_policy(found: list["Detected"], environ: dict[str, str]) -> list["Detected"]:
    if local_compute_allowed(environ):
        return found
    for d in found:
        if d.id == "ollama":
            d.models = [m for m in d.models if is_cloud_model(m)]
            d.caps = [c for c in d.caps if c != "embed"]
            if not d.models:
                d.enabled = False
                d.needs = "no -cloud models yet: run `ollama signin`, then `ollama run gpt-oss:120b-cloud` once"
        elif d.kind == "local" and d.id != "litellm_proxy":
            d.enabled = False
            d.needs = "local compute is off (ASSAY_LOCAL_COMPUTE=0)"
    return found


# --------------------------------------------------------------- public

async def detect(environ: Optional[dict[str, str]] = None, scan_ports: bool = True) -> list[Detected]:
    environ = dict(os.environ if environ is None else environ)
    found: list[Detected] = []
    seen: set[str] = set()

    for spec in PROVIDERS:
        if spec.kind == "cli" or spec.id == "builtin":
            continue
        via = _env_hit(spec, environ) or _file_hit(spec)
        if via:
            found.append(Detected(spec.id, spec.name, spec.kind, sorted(spec.caps), via,
                                  api_base=_base_from_env(spec, environ),
                                  models=sorted(set(spec.default_models.values())),
                                  icon=spec.icon, needs=spec.needs))
            seen.add(spec.id)

    if scan_ports and environ.get("ASSAY_SCAN_LOCAL", "1") != "0":
        for d in await _scan_ports(skip=set()):
            if d.id in seen:   # env said where it is; enrich with live models
                for f in found:
                    if f.id == d.id:
                        f.models = d.models or f.models
                        f.api_base = f.api_base or d.api_base
                continue
            found.append(d)
            seen.add(d.id)

    for pid, binary in CLI_BINARIES.items():
        path = shutil.which(binary)
        if path:
            spec = BY_ID[pid]
            opted_in = environ.get(f"ASSAY_ENABLE_{pid.upper()}", "0") == "1"
            found.append(Detected(pid, spec.name, "cli", sorted(spec.caps), f"cli:{binary}",
                                  enabled=opted_in, icon=spec.icon, risk=spec.risk))

    from . import builtin
    if builtin.available() and local_compute_allowed(environ):
        found.append(Detected("builtin", BY_ID["builtin"].name, "local", ["embed", "rerank"], "bundled",
                              models=["builtin/bge-small-en-v1.5", "builtin/ms-marco-MiniLM-L-6-v2"]))
    return _apply_policy(found, environ)
