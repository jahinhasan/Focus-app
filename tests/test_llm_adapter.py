"""LLM provider abstraction: failure modes, payload shape, env-key handling (spec N.4, C)."""
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from focus_agent import llm as fllm
from focus_agent.llm import (BadResponse, ModelNotInstalled, NullProvider,
                             OllamaProvider, OnlineProvider, ProviderUnavailable,
                             extract_json, get_providers)


# ---------------- payload construction (mocked HTTP) ----------------

def test_ollama_payload_shape(monkeypatch):
    captured = {}

    def fake_post(url, payload, timeout, headers=None):
        captured["url"] = url
        captured["payload"] = payload
        return {"message": {"content": '{"ok": true}'}}

    monkeypatch.setattr(fllm, "_post_json", fake_post)
    p = OllamaProvider(endpoint="http://x:11434", model="qwen3:4b", timeout=30)
    out = p.chat("sys", "hello", history=[{"role": "user", "content": "earlier"}],
                 temperature=0.2, max_tokens=777)
    assert out == '{"ok": true}'
    assert captured["url"].endswith("/api/chat")
    payload = captured["payload"]
    assert payload["model"] == "qwen3:4b"
    assert payload["stream"] is False
    assert payload["think"] is False  # thinking models must not stall on <think>
    assert payload["options"]["num_predict"] == 777
    assert payload["messages"][0] == {"role": "system", "content": "sys"}
    assert payload["messages"][-1] == {"role": "user", "content": "hello"}
    assert "format" not in payload  # json format only when temperature == 0


def test_ollama_json_mode_sets_format(monkeypatch):
    captured = {}

    def fake_post(url, payload, timeout, headers=None):
        captured["payload"] = payload
        return {"message": {"content": "{}"}}

    monkeypatch.setattr(fllm, "_post_json", fake_post)
    OllamaProvider().chat_json("s", "u", temperature=0.0)
    assert captured["payload"]["format"] == "json"


def test_ollama_empty_content_is_typed_error(monkeypatch):
    monkeypatch.setattr(fllm, "_post_json",
                        lambda *a, **k: {"message": {"content": ""}})
    with pytest.raises(BadResponse):
        OllamaProvider().chat("s", "u")


# ---------------- failure mapping ----------------

def _resp(status, body=None):
    r = requests.Response()
    r.status_code = status
    if body is not None:
        import json as _json
        r._content = _json.dumps(body).encode()
    return r


def test_connection_error_maps_to_unavailable(monkeypatch):
    def boom(url, json=None, timeout=None, headers=None):
        raise requests.exceptions.ConnectionError("refused")
    monkeypatch.setattr(fllm.requests, "post", boom)
    with pytest.raises(ProviderUnavailable):
        fllm._post_json("http://x/api/chat", {}, 5)


def test_timeout_maps_to_unavailable(monkeypatch):
    def boom(url, json=None, timeout=None, headers=None):
        raise requests.exceptions.Timeout()
    monkeypatch.setattr(fllm.requests, "post", boom)
    with pytest.raises(ProviderUnavailable):
        fllm._post_json("http://x", {}, 5)


def test_404_maps_to_model_not_installed(monkeypatch):
    monkeypatch.setattr(fllm.requests, "post",
                        lambda url, json=None, timeout=None, headers=None: _resp(404))
    with pytest.raises(ModelNotInstalled):
        fllm._post_json("http://x", {}, 5)


def test_503_maps_to_busy(monkeypatch):
    monkeypatch.setattr(fllm.requests, "post",
                        lambda url, json=None, timeout=None, headers=None: _resp(503))
    with pytest.raises(ProviderUnavailable):
        fllm._post_json("http://x", {}, 5)


# ---------------- OnlineProvider: env-only keys, auth header ----------------

def test_online_provider_requires_env_key(monkeypatch):
    monkeypatch.delenv("ONLINE_LLM_API_KEY", raising=False)
    op = OnlineProvider()
    assert not op.available()
    with pytest.raises(ProviderUnavailable):
        op.chat("s", "u")  # no key -> refuses, does not crash
    ok, detail = op.status()
    assert not ok


def test_online_provider_sends_auth_header_not_in_payload(monkeypatch):
    captured = {}

    def fake_post(url, payload, timeout, headers=None):
        captured["url"], captured["payload"], captured["headers"] = url, payload, headers
        return {"choices": [{"message": {"content": "answer"}}]}

    monkeypatch.setattr(fllm, "_post_json", fake_post)
    op = OnlineProvider(api_key="sk-secret-123", base_url="https://api.example.com/v1",
                        model="m1")
    assert op.chat("s", "u") == "answer"
    assert captured["url"] == "https://api.example.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer sk-secret-123"
    assert "sk-secret-123" not in str(captured["payload"]), "key must never ride in the body"


def test_settings_never_hold_api_keys():
    from storage import DEFAULT_AGENT_SETTINGS
    flat = str(DEFAULT_AGENT_SETTINGS)
    assert "key" not in flat.lower() or "online_research_enabled" in flat
    assert "ONLINE_LLM_API_KEY" not in flat


# ---------------- factory precedence ----------------

def test_factory_provider_none(monkeypatch):
    for var in ("FOCUS_LLM_PROVIDER", "ONLINE_LLM_API_KEY", "OLLAMA_HOST", "OLLAMA_MODEL"):
        monkeypatch.delenv(var, raising=False)
    primary, online = get_providers({"agent": {"provider": "none"}})
    assert isinstance(primary, NullProvider)
    assert online is None  # no key -> no online adapter


def test_factory_env_overrides_settings(monkeypatch):
    monkeypatch.setenv("FOCUS_LLM_PROVIDER", "none")
    primary, _ = get_providers({"agent": {"provider": "ollama"}})
    assert isinstance(primary, NullProvider)


def test_factory_online_only_with_key(monkeypatch):
    for var in ("FOCUS_LLM_PROVIDER", "ONLINE_LLM_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    _, online = get_providers({})
    assert online is None
    monkeypatch.setenv("ONLINE_LLM_API_KEY", "sk-test")
    _, online2 = get_providers({})
    assert online2 is not None and online2.available()


def test_null_provider_refuses_chat():
    with pytest.raises(ProviderUnavailable):
        NullProvider().chat("s", "u")


# ---------------- live Ollama (opt-in; auto-skips when unreachable) ----------------

def test_ollama_live_roundtrip():
    """Real call against local Ollama. Skips automatically when unavailable."""
    p = OllamaProvider(timeout=90)
    ok, detail = p.status()
    if not ok:
        pytest.skip(f"Ollama not usable here: {detail}")
    reply = p.chat("Answer with one word.", "Say: ready", temperature=0.0, max_tokens=64)
    assert isinstance(reply, str) and reply.strip()
