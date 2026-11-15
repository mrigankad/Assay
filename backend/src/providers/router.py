"""
Model router: one interface for every provider, a model per agent role.

Resolution for a role (planner, search, expert, verifier, browser, vision,
synthesis, embed, rerank):
  1. ASSAY_MODEL_<ROLE>        e.g. ASSAY_MODEL_VERIFIER=gemini/gemini-2.5-pro
  2. ASSAY_MODEL / ASSAY_EMBED_MODEL / ASSAY_RERANK_MODEL
  3. auto: the first detected provider in PREFERENCE that can do the job

Model strings are LiteLLM style ("provider/model"). Three extra prefixes are
handled here instead of LiteLLM: "claude_code/", "codex_cli/", "gemini_cli/"
(the vendor CLIs, opt-in) and "builtin/" (bundled ONNX via fastembed).

The public methods keep the old LLMService signatures (generate,
generate_stream, generate_with_context) so agents work unchanged.
"""

from __future__ import annotations

import asyncio
import os
from typing import AsyncGenerator, Optional

from src.core.logger import get_logger

from .catalog import BY_ID
from .detection import Detected, detect
from . import cli_backends, builtin

logger = get_logger(__name__)

ROLES = ("planner", "search", "expert", "verifier", "browser", "vision", "synthesis", "embed", "rerank")

# Hosted APIs first, then vendor CLIs the user enabled (opt-in = consent),
# then local runtimes. A disabled CLI is never picked.
PREFERENCE = [
    "anthropic", "openai", "gemini", "azure", "bedrock", "vertex_ai", "mistral", "cohere", "xai",
    "deepseek", "openrouter", "vercel_ai_gateway", "github", "nvidia_nim", "together_ai",
    "fireworks_ai", "groq", "dashscope", "watsonx", "oci", "databricks", "cloudflare",
    "huggingface", "ollama_cloud", "litellm_proxy",
    "claude_code", "codex_cli", "gemini_cli",
    "ollama", "lm_studio", "vllm", "sglang", "llamacpp", "localai", "xinference", "tgi",
    "docker_model_runner", "jan", "gpt4all", "koboldcpp", "textgen_webui", "mlx",
    "jina_ai", "voyage", "infinity", "builtin",
]

_CACHE: dict = {"detected": None}
_LOCK = asyncio.Lock()


async def detected(refresh: bool = False) -> list[Detected]:
    async with _LOCK:
        if refresh or _CACHE["detected"] is None:
            _CACHE["detected"] = await detect()
            logger.info("providers detected", providers=[d.id for d in _CACHE["detected"]])
        return _CACHE["detected"]


def _cap_for(role: str) -> str:
    return {"embed": "embed", "rerank": "rerank", "vision": "vision", "browser": "vision"}.get(role, "chat")


def _pick_model(d: Detected, cap: str) -> Optional[str]:
    spec = BY_ID[d.id]
    key = {"vision": "chat"}.get(cap, cap)
    if spec.default_models.get(key):
        return spec.default_models[key]
    if not d.models:
        return None
    pool = d.models
    if cap == "embed":
        pool = [m for m in d.models if "embed" in m.lower()] or []
    elif cap == "rerank":
        pool = [m for m in d.models if "rerank" in m.lower()] or []
    else:
        pool = [m for m in d.models if "embed" not in m.lower() and "rerank" not in m.lower()]
    if not pool:
        return None
    m = pool[0]
    if m.startswith(("builtin/",)):
        return m
    return f"{spec.prefix}/{m}" if spec.prefix and not m.startswith(spec.prefix + "/") else m


PREFS_PATH = os.getenv("ASSAY_PREFS_PATH", os.path.join(os.getcwd(), "data", "model_prefs.json"))


def load_prefs() -> dict:
    """Saved choices from the UI: {"default": "claude_code/", "roles": {"verifier": "..."}}."""
    import json
    try:
        with open(PREFS_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_prefs(prefs: dict) -> dict:
    import json
    os.makedirs(os.path.dirname(PREFS_PATH), exist_ok=True)
    clean = {"default": prefs.get("default") or None,
             "roles": {k: v for k, v in (prefs.get("roles") or {}).items() if k in ROLES and v}}
    with open(PREFS_PATH, "w", encoding="utf-8") as fh:
        json.dump(clean, fh, indent=2)
    return clean


def _env_model(role: str) -> Optional[str]:
    """UI choice for this role, then env for this role, then UI default, then env default."""
    prefs = load_prefs()
    if prefs.get("roles", {}).get(role):
        return prefs["roles"][role]
    v = os.getenv(f"ASSAY_MODEL_{role.upper()}")
    if v:
        return v
    if role == "embed":
        return os.getenv("ASSAY_EMBED_MODEL")
    if role == "rerank":
        return os.getenv("ASSAY_RERANK_MODEL")
    if prefs.get("default"):
        return prefs["default"]
    return os.getenv("ASSAY_MODEL")


async def resolve(role: str) -> tuple[str, Optional[str]]:
    """Return (model, api_base) for a role."""
    explicit = _env_model(role)
    found = await detected()
    by_id = {d.id: d for d in found}
    if explicit:
        pid = next((d.id for d in found if BY_ID[d.id].prefix and explicit.startswith(BY_ID[d.id].prefix + "/")), None)
        return explicit, by_id[pid].api_base if pid else None
    cap = _cap_for(role)
    for pid in PREFERENCE:
        d = by_id.get(pid)
        if not d or not d.enabled or cap not in d.caps:
            continue
        model = _pick_model(d, cap)
        if model:
            base = d.api_base if BY_ID[pid].kind == "local" or pid in {"ollama_cloud", "litellm_proxy"} else None
            return model, base
    raise RuntimeError(
        f"No model available for role '{role}'. Set an API key (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY, "
        f"AWS credentials, AZURE_OPENAI_*), start Ollama / LM Studio / vLLM, or set ASSAY_MODEL_{role.upper()}."
    )


def _kwargs(model: str, api_base: Optional[str]) -> dict:
    kw: dict = {}
    if api_base:
        kw["api_base"] = api_base
    if model.startswith("openai/") and api_base:
        kw["api_key"] = os.getenv("OPENAI_API_KEY") or "local"
    if model.startswith("ollama_chat/") and api_base and "ollama.com" in api_base:
        kw["api_key"] = os.getenv("OLLAMA_API_KEY")
    return kw


def _messages(prompt, system_prompt=None, chat_history=None):
    msgs = []
    if system_prompt:
        msgs.append({"role": "system", "content": system_prompt})
    if chat_history:
        msgs.extend(chat_history)
    msgs.append({"role": "user", "content": prompt})
    return msgs


class LLMRouter:
    """Drop-in replacement for LLMService, bound to an agent role."""

    def __init__(self, role: str = "synthesis", model: Optional[str] = None):
        self.role = role if role in ROLES else "synthesis"
        self._model = model
        self._base: Optional[str] = None

    async def _target(self) -> tuple[str, Optional[str]]:
        if self._model is None:
            self._model, self._base = await resolve(self.role)
        return self._model, self._base

    @property
    def model(self) -> Optional[str]:
        return self._model

    async def generate(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024,
                       temperature: float = 0.7, top_p: float = 0.9, **_) -> str:
        model, base = await self._target()
        msgs = _messages(prompt, system_prompt)
        if cli_backends.handles(model):
            return await cli_backends.complete(model, msgs)
        import litellm
        resp = await litellm.acompletion(model=model, messages=msgs, max_tokens=max_tokens,
                                         temperature=temperature, top_p=top_p, num_retries=2,
                                         **_kwargs(model, base))
        return resp.choices[0].message.content or ""

    async def generate_stream(self, prompt: str, system_prompt: Optional[str] = None,
                              chat_history=None, max_tokens: int = 1024, temperature: float = 0.7,
                              top_p: float = 0.9, **_) -> AsyncGenerator[str, None]:
        model, base = await self._target()
        msgs = _messages(prompt, system_prompt, chat_history)
        if cli_backends.handles(model):
            yield await cli_backends.complete(model, msgs)
            return
        import litellm
        stream = await litellm.acompletion(model=model, messages=msgs, max_tokens=max_tokens,
                                           temperature=temperature, top_p=top_p, stream=True,
                                           num_retries=2, **_kwargs(model, base))
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    async def generate_with_context(self, query: str, context: str, system_prompt: Optional[str] = None,
                                    max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        system = system_prompt or (
            "Answer the question using only the provided context. If the context does not "
            "contain the answer, say so. Cite the context where you use it."
        )
        prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
        async for t in self.generate_stream(prompt, system_prompt=system, max_tokens=max_tokens):
            yield t


async def embed(texts: list[str], model: Optional[str] = None) -> list[list[float]]:
    model, base = (model, None) if model else await resolve("embed")
    if builtin.handles(model):
        return await builtin.embed(model, texts)
    import litellm
    resp = await litellm.aembedding(model=model, input=texts, **_kwargs(model, base))
    return [d["embedding"] for d in resp.data]


async def rerank(query: str, docs: list[str], top_n: int = 5, model: Optional[str] = None) -> list[tuple[int, float]]:
    """Return [(doc_index, score)] best first."""
    model, base = (model, None) if model else await resolve("rerank")
    if builtin.handles(model):
        return await builtin.rerank(model, query, docs, top_n)
    import litellm
    resp = await litellm.arerank(model=model, query=query, documents=docs, top_n=top_n, **_kwargs(model, base))
    return [(r["index"], r["relevance_score"]) for r in resp.results]


def get_llm(role: str = "synthesis") -> LLMRouter:
    return LLMRouter(role)
