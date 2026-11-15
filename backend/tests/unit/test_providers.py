"""Provider layer: catalogue, auto-detection, role routing, LLMService over LiteLLM."""

from __future__ import annotations

import types

import pytest

from src.providers import catalog, router
import src.providers.detection as det
from src.providers.catalog import BY_ID, PROVIDERS


@pytest.fixture(autouse=True)
def _reset_cache():
    router._CACHE["detected"] = None
    yield
    router._CACHE["detected"] = None


def test_catalogue_ids_unique_and_prefixes_known_to_litellm():
    import litellm
    known = {str(getattr(p, "value", p)) for p in litellm.provider_list}
    ids = [p.id for p in PROVIDERS]
    assert len(ids) == len(set(ids))
    assert len(PROVIDERS) >= 60
    for p in PROVIDERS:
        if p.prefix:
            assert p.prefix in known, f"{p.id}: unknown LiteLLM prefix {p.prefix}"
        assert p.caps, p.id


def test_catalogue_covers_the_clouds():
    for pid in ["azure", "bedrock", "vertex_ai", "oci", "watsonx", "dashscope", "databricks", "snowflake",
                "cloudflare", "sagemaker"]:
        assert pid in BY_ID


async def _detect(env, monkeypatch, ports=None, which=None):
    async def fake_scan(skip):
        return ports or []
    monkeypatch.setattr(det, "_scan_ports", fake_scan)
    monkeypatch.setattr(det.shutil, "which", lambda b: (which or {}).get(b))
    monkeypatch.setattr(det, "_file_hit", lambda spec: None)
    return await det.detect(environ=env)


@pytest.mark.asyncio
async def test_env_detection_requires_whole_group(monkeypatch):
    found = await _detect({"AZURE_OPENAI_API_KEY": "k"}, monkeypatch)
    assert "azure" not in {d.id for d in found}
    found = await _detect({"AZURE_OPENAI_API_KEY": "k", "AZURE_OPENAI_ENDPOINT": "https://x"}, monkeypatch)
    assert "azure" in {d.id for d in found}


@pytest.mark.asyncio
async def test_aws_and_many_keys_detected(monkeypatch):
    env = {"AWS_PROFILE": "dev", "OPENAI_API_KEY": "sk", "GROQ_API_KEY": "g", "TOGETHER_API_KEY": "t"}
    ids = {d.id for d in await _detect(env, monkeypatch)}
    assert {"bedrock", "openai", "groq", "together_ai"} <= ids


@pytest.mark.asyncio
async def test_cli_found_but_off_until_opted_in(monkeypatch):
    found = await _detect({}, monkeypatch, which={"claude": "/usr/bin/claude"})
    cc = next(d for d in found if d.id == "claude_code")
    assert cc.enabled is False and cc.risk
    found = await _detect({"ASSAY_ENABLE_CLAUDE_CODE": "1"}, monkeypatch, which={"claude": "/usr/bin/claude"})
    assert next(d for d in found if d.id == "claude_code").enabled is True


def test_port_fingerprints_disambiguate_shared_ports():
    assert det._fingerprint("ollama", 200, {"models": []})
    assert not det._fingerprint("ollama", 200, {"data": []})
    assert det._fingerprint("tgi", 200, {"model_id": "x"})
    assert not det._fingerprint("tgi", 200, {"data": []})
    assert det._fingerprint("llamacpp", 200, {"data": [{"id": "m", "owned_by": "llamacpp"}]})
    assert not det._fingerprint("vllm", 200, {"data": [{"id": "m", "owned_by": "llamacpp"}]})
    assert det._models_from("ollama", {"models": [{"name": "qwen3:8b"}]}) == ["qwen3:8b"]


def _set_detected(items):
    router._CACHE["detected"] = items


def _d(pid, models=(), base=None, enabled=True):
    s = BY_ID[pid]
    return det.Detected(pid, s.name, s.kind, sorted(s.caps), "test", api_base=base, models=list(models),
                        enabled=enabled)


@pytest.mark.asyncio
async def test_resolve_prefers_hosted_then_local(monkeypatch):
    for v in ("ASSAY_MODEL", "ASSAY_MODEL_SYNTHESIS", "ASSAY_EMBED_MODEL"):
        monkeypatch.delenv(v, raising=False)
    _set_detected([_d("ollama", ["qwen3:8b", "nomic-embed-text"], "http://127.0.0.1:11434"), _d("anthropic")])
    model, base = await router.resolve("synthesis")
    assert model.startswith("anthropic/") and base is None
    _set_detected([_d("ollama", ["qwen3:8b", "nomic-embed-text"], "http://127.0.0.1:11434")])
    assert await router.resolve("synthesis") == ("ollama_chat/qwen3:8b", "http://127.0.0.1:11434")
    assert (await router.resolve("embed"))[0] == "ollama_chat/nomic-embed-text"


@pytest.mark.asyncio
async def test_resolve_env_override_and_disabled_cli(monkeypatch):
    _set_detected([_d("claude_code", enabled=False), _d("ollama", ["llama3.2"], "http://h:11434")])
    monkeypatch.setenv("ASSAY_MODEL_VERIFIER", "gemini/gemini-2.5-pro")
    assert (await router.resolve("verifier"))[0] == "gemini/gemini-2.5-pro"
    assert (await router.resolve("planner"))[0] == "ollama_chat/llama3.2"   # CLI never auto-picked


@pytest.mark.asyncio
async def test_resolve_explains_when_nothing_found(monkeypatch):
    monkeypatch.delenv("ASSAY_MODEL", raising=False)
    monkeypatch.delenv("ASSAY_MODEL_SYNTHESIS", raising=False)
    _set_detected([])
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        await router.resolve("synthesis")


@pytest.mark.asyncio
async def test_llm_service_uses_litellm_and_tracks_cost(monkeypatch):
    import litellm
    from src.services.llm.llm_service import LLMService, LLMUsage

    calls = {}

    async def fake(**kw):
        calls.update(kw)
        msg = types.SimpleNamespace(content='{"ok": true}')
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)],
                                     usage=types.SimpleNamespace(prompt_tokens=10, completion_tokens=3))

    monkeypatch.setattr(litellm, "acompletion", fake)
    monkeypatch.setattr(litellm, "completion_cost", lambda **_: 0.0021)
    svc = LLMService(model="bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0", fast_model="groq/llama-3.3-70b")
    usage = LLMUsage()
    assert await svc.generate_json("q", usage=usage) == {"ok": True}
    assert calls["model"] == "groq/llama-3.3-70b" and calls["response_format"] == {"type": "json_object"}
    await svc.generate("q", usage=usage)
    assert calls["model"].startswith("bedrock/")
    d = usage.to_dict()
    assert d["total_tokens"] == 26 and d["cost_usd"] == pytest.approx(0.0042) and len(d["models"]) == 2


@pytest.mark.asyncio
async def test_cli_backend_refuses_without_opt_in(monkeypatch):
    from src.providers import cli_backends
    monkeypatch.delenv("ASSAY_ENABLE_CLAUDE_CODE", raising=False)
    with pytest.raises(PermissionError):
        await cli_backends.complete("claude_code/", [{"role": "user", "content": "hi"}])
