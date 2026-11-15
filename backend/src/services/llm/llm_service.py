"""
Chat-completion service for every provider.

Same interface the orchestrator always used (chat, generate, generate_json,
stream, generate_stream, generate_with_context), now routed through
src.providers: Anthropic, OpenAI, Azure, Bedrock, Vertex, Gemini, Mistral,
Ollama, vLLM, LM Studio, NIM and the rest. The model comes from the role:
"synthesis" for normal calls, "planner" for fast=True (routing, planning,
JSON). Usage records tokens, cost (from LiteLLM's price map) and model.
"""

from __future__ import annotations

import json
import re
from typing import Any, AsyncGenerator, Dict, List, Optional

from src.core.logger import get_logger, log_timing
from src.providers import cli_backends
from src.providers.router import _kwargs, resolve

logger = get_logger(__name__)

Message = Dict[str, str]


class LLMError(RuntimeError):
    pass


class LLMUsage:
    """Accumulates token usage, cost and models for one request / trace."""

    def __init__(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.cost_usd = 0.0
        self.models: Dict[str, int] = {}

    def add(self, usage: Optional[Dict[str, Any]], model: Optional[str] = None, cost: float = 0.0) -> None:
        self.cost_usd += float(cost or 0.0)
        if model:
            self.models[model] = self.models.get(model, 0) + 1
        if not usage:
            return
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.calls += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "llm_calls": self.calls,
            "cost_usd": round(self.cost_usd, 6),
            "models": dict(self.models),
        }


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Pull the first JSON object/array out of an LLM response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK.search(text)
    if m:
        return json.loads(m.group(1))
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return json.loads(text[start:end + 1])
    raise ValueError("No JSON found in LLM response")


def _usage_dict(u: Any) -> Optional[Dict[str, Any]]:
    if u is None:
        return None
    if isinstance(u, dict):
        return u
    return {"prompt_tokens": getattr(u, "prompt_tokens", 0), "completion_tokens": getattr(u, "completion_tokens", 0)}


def _cost(resp: Any) -> float:
    try:
        import litellm
        return float(litellm.completion_cost(completion_response=resp) or 0.0)
    except Exception:
        return 0.0          # local and unknown models have no price


class LLMService:
    """Provider-agnostic chat client. `role` picks the model (see src.providers.router)."""

    def __init__(self, model: Optional[str] = None, fast_model: Optional[str] = None,
                 role: str = "synthesis", fast_role: str = "planner", **_legacy: Any):
        self._model, self._fast_model = model, fast_model
        self.role, self.fast_role = role, fast_role
        self._bases: Dict[str, Optional[str]] = {}

    async def _target(self, fast: bool, model: Optional[str] = None) -> tuple[str, Optional[str]]:
        if model:
            return model, self._bases.get(model)
        attr = "_fast_model" if fast else "_model"
        current = getattr(self, attr)
        if current is None:
            current, base = await resolve(self.fast_role if fast else self.role)
            setattr(self, attr, current)
            self._bases[current] = base
        return current, self._bases.get(current)

    @property
    def model(self) -> Optional[str]:
        return self._model

    @property
    def fast_model(self) -> Optional[str]:
        return self._fast_model or self._model

    @staticmethod
    def _build_messages(prompt: str, system_prompt: Optional[str], chat_history: Optional[List[Message]]) -> List[Message]:
        messages: List[Message] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if chat_history:
            messages.extend({"role": m["role"], "content": m["content"]} for m in chat_history if m.get("content"))
        messages.append({"role": "user", "content": prompt})
        return messages

    async def chat(self, messages: List[Message], model: Optional[str] = None, max_tokens: int = 1024,
                   temperature: float = 0.3, top_p: float = 0.9, usage: Optional[LLMUsage] = None,
                   json_mode: bool = False, fast: bool = False) -> str:
        target, base = await self._target(fast, model)
        if cli_backends.handles(target):
            text = await cli_backends.complete(target, messages)
            if usage is not None:
                usage.add(None, model=target)
            return text
        import litellm
        kw: Dict[str, Any] = dict(model=target, messages=messages, max_tokens=max_tokens,
                                  temperature=temperature, top_p=top_p, num_retries=2, **_kwargs(target, base))
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        try:
            resp = await litellm.acompletion(**kw)
        except Exception as exc:
            if not json_mode:
                raise LLMError(f"{target}: {exc}") from exc
            kw.pop("response_format", None)   # provider without JSON mode: ask plainly
            try:
                resp = await litellm.acompletion(**kw)
            except Exception as exc2:
                raise LLMError(f"{target}: {exc2}") from exc2
        if usage is not None:
            usage.add(_usage_dict(getattr(resp, "usage", None)), model=target, cost=_cost(resp))
        return resp.choices[0].message.content or ""

    @log_timing("llm_generate")
    async def generate(self, prompt: str, system_prompt: Optional[str] = None,
                       chat_history: Optional[List[Message]] = None, max_tokens: int = 1024,
                       temperature: float = 0.3, top_p: float = 0.9, fast: bool = False,
                       usage: Optional[LLMUsage] = None) -> str:
        target, _ = await self._target(fast)
        return await self.chat(self._build_messages(prompt, system_prompt, chat_history), model=target,
                               max_tokens=max_tokens, temperature=temperature, top_p=top_p, usage=usage)

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None, max_tokens: int = 1024,
                            temperature: float = 0.1, fast: bool = True, usage: Optional[LLMUsage] = None,
                            retries: int = 1) -> Any:
        messages = self._build_messages(prompt, system_prompt, None)
        last_error: Optional[Exception] = None
        target, _ = await self._target(fast)
        for _ in range(retries + 1):
            text = await self.chat(messages, model=target, max_tokens=max_tokens, temperature=temperature,
                                   usage=usage, json_mode=True)
            try:
                return extract_json(text)
            except (ValueError, json.JSONDecodeError) as exc:
                last_error = exc
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content": "That was not valid JSON. Reply with ONLY the JSON object."})
        raise LLMError(f"Could not parse JSON from model: {last_error}")

    async def stream(self, messages: List[Message], model: Optional[str] = None, max_tokens: int = 1024,
                     temperature: float = 0.3, top_p: float = 0.9, usage: Optional[LLMUsage] = None,
                     fast: bool = False) -> AsyncGenerator[str, None]:
        target, base = await self._target(fast, model)
        if cli_backends.handles(target):
            yield await cli_backends.complete(target, messages)
            if usage is not None:
                usage.add(None, model=target)
            return
        import litellm
        try:
            resp = await litellm.acompletion(model=target, messages=messages, max_tokens=max_tokens,
                                             temperature=temperature, top_p=top_p, stream=True,
                                             stream_options={"include_usage": True}, num_retries=2,
                                             **_kwargs(target, base))
        except Exception as exc:
            raise LLMError(f"{target}: {exc}") from exc
        chunks = []
        async for chunk in resp:
            chunks.append(chunk)
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        if usage is not None:
            u = next((getattr(c, "usage", None) for c in reversed(chunks) if getattr(c, "usage", None)), None)
            cost = 0.0
            try:
                cost = _cost(litellm.stream_chunk_builder(chunks, messages=messages))
            except Exception:
                pass
            usage.add(_usage_dict(u), model=target, cost=cost)

    async def generate_stream(self, prompt: str, system_prompt: Optional[str] = None,
                              chat_history: Optional[List[Message]] = None, max_tokens: int = 1024,
                              temperature: float = 0.3, top_p: float = 0.9,
                              usage: Optional[LLMUsage] = None) -> AsyncGenerator[str, None]:
        async for t in self.stream(self._build_messages(prompt, system_prompt, chat_history),
                                   max_tokens=max_tokens, temperature=temperature, top_p=top_p, usage=usage):
            yield t

    async def generate_with_context(self, query: str, context: str, system_prompt: Optional[str] = None,
                                    max_tokens: int = 1024) -> AsyncGenerator[str, None]:
        default_system = ("Answer the user's question from the provided context. If the context doesn't "
                          "contain the answer, say so. Cite the context when relevant.")
        prompt = f"Context:\n{context}\n\nQuestion: {query}\n\nAnswer:"
        async for t in self.generate_stream(prompt, system_prompt=system_prompt or default_system, max_tokens=max_tokens):
            yield t

    @classmethod
    async def aclose(cls) -> None:
        return None


_default_llm: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _default_llm
    if _default_llm is None:
        _default_llm = LLMService()
    return _default_llm


def set_llm_service(service: Optional[LLMService]) -> None:
    """Dependency override hook (tests, custom providers)."""
    global _default_llm
    _default_llm = service


def get_role_llm(role: str) -> LLMService:
    """A client bound to an agent role (verifier, browser, expert...)."""
    return LLMService(role=role)
