# ==================== LLM.PY ====================
# LLM provider abstraction. Ollama's local HTTP API is the primary provider;
# an optional OpenAI-compatible online adapter covers research-heavy requests.
#
# Design rules:
# - No business logic here: providers return raw text/JSON, never mutate data.
# - Every failure mode (unreachable, model missing, timeout, malformed output,
#   empty output, context errors) becomes a typed exception the controller can
#   explain - the app stays fully usable with the provider offline.
# - API keys ONLY via environment variables; never logged, never persisted.

import os
import json
import re
import uuid
from abc import ABC, abstractmethod

import requests

DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434"
DEFAULT_TIMEOUT = 120


class LLMError(Exception):
    """Base class: user-presentable message in str(e)."""


class ProviderUnavailable(LLMError):
    pass


class ModelNotInstalled(LLMError):
    pass


class BadResponse(LLMError):
    pass


def _post_json(url, payload, timeout, headers=None):
    try:
        resp = requests.post(url, json=payload, timeout=timeout, headers=headers)
    except requests.exceptions.ConnectionError:
        raise ProviderUnavailable(f"Could not connect to {url} - is the service running?")
    except requests.exceptions.Timeout:
        raise ProviderUnavailable(f"Request to {url} timed out after {timeout}s")
    except requests.exceptions.RequestException as e:
        raise ProviderUnavailable(f"Request failed: {e.__class__.__name__}")
    if resp.status_code == 404:
        raise ModelNotInstalled("Model not found on the provider (404). "
                                "Install it with: ollama pull <model>")
    if resp.status_code in (429, 503):
        raise ProviderUnavailable(f"Provider busy or rate limited ({resp.status_code})")
    if resp.status_code != 200:
        raise ProviderUnavailable(f"Provider returned HTTP {resp.status_code}")
    try:
        return resp.json()
    except json.JSONDecodeError:
        raise BadResponse("Provider returned non-JSON HTTP body")


class LLMProvider(ABC):
    name = "base"

    @abstractmethod
    def chat(self, system, user, history=None, temperature=0.2, max_tokens=2048):
        """Return the assistant message text. Raise LLMError subclasses on failure."""

    def chat_json(self, system, user, history=None, temperature=0.0, max_tokens=2048):
        """chat() + tolerant JSON extraction. Raises BadResponse on garbage."""
        text = self.chat(system, user, history=history,
                         temperature=temperature, max_tokens=max_tokens)
        return extract_json(text)

    def status(self):
        """(ok: bool, detail: str) for the settings page."""
        return False, "not implemented"

    def capabilities(self):
        return {"local": True, "research": False}


def extract_json(text):
    """Pull the first JSON object out of model output.

    Handles fenced ```json blocks, leading prose, and thinking-model chatter.
    Raises BadResponse when no object is found.
    """
    if not text or not str(text).strip():
        raise BadResponse("Model returned empty output")
    text = str(text).strip()

    # prefer fenced blocks
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = []
    if m:
        candidates.append(m.group(1))
    # first balanced object scan
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            c = text[i]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(text[start:i + 1])
                    break
        nxt = text.find("{", start + 1)
        start = nxt
        if len(candidates) >= 3:
            break

    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    raise BadResponse("Model output did not contain valid JSON")


class OllamaProvider(LLMProvider):
    """Local Ollama inference via the /api/chat HTTP endpoint."""

    name = "ollama"

    def __init__(self, endpoint=None, model=None, timeout=None):
        env_host = os.environ.get("OLLAMA_HOST", "")
        if env_host and not env_host.startswith("http"):
            env_host = f"http://{env_host}"
        self.endpoint = (endpoint or env_host or DEFAULT_OLLAMA_ENDPOINT).rstrip("/")
        self.model = model or os.environ.get("OLLAMA_MODEL") or "qwen3:4b"
        self.timeout = int(timeout or os.environ.get("OLLAMA_TIMEOUT") or DEFAULT_TIMEOUT)

    def _chat_url(self):
        return f"{self.endpoint}/api/chat"

    def chat(self, system, user, history=None, temperature=0.2, max_tokens=2048):
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        for h in (history or [])[-8:]:
            role = "user" if h.get("role") == "user" else "assistant"
            content = h.get("content")
            if content:
                messages.append({"role": role, "content": content[:2000]})
        messages.append({"role": "user", "content": user})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,  # supported by thinking models; ignored otherwise
            "format": "json" if temperature == 0.0 else None,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        payload = {k: v for k, v in payload.items() if v is not None}
        data = _post_json(self._chat_url(), payload, self.timeout)

        msg = data.get("message") or {}
        content = msg.get("content")
        # thinking models may put everything under 'thinking' when content empty
        if not content and msg.get("thinking"):
            content = msg["thinking"]
        if not content and data.get("response"):
            content = data["response"]
        if not content:
            raise BadResponse("Ollama returned an empty message "
                              "(model may have run out of output tokens)")
        return content

    def status(self):
        try:
            resp = requests.get(f"{self.endpoint}/api/tags", timeout=5)
        except requests.exceptions.RequestException:
            return False, f"Ollama not reachable at {self.endpoint}"
        if resp.status_code != 200:
            return False, f"Ollama responded HTTP {resp.status_code}"
        try:
            models = [m.get("name", "") for m in resp.json().get("models", [])]
        except (json.JSONDecodeError, AttributeError):
            return False, "Ollama responded with unexpected data"
        if not models:
            return False, "Ollama is running but no models are installed. Run: ollama pull <model>"
        if self.model in models or any(m.split(":")[0] == self.model.split(":")[0] for m in models):
            return True, f"Auto-Hybrid AI Ready ({self.model} + Online Knowledge)"
        return False, (f"Ollama is running but '{self.model}' is not installed. "
                       f"Available: {', '.join(models[:6])}. Run: ollama pull {self.model}")

    def capabilities(self):
        return {"local": True, "research": True}


def fetch_online_topic_summary(query: str, timeout: float = 2.5) -> str:
    """Fetch live online encyclopedic knowledge for a topic when internet is available.

    Used automatically by the agent for curriculum roadmaps and study explanations
    when no paid cloud API key is configured. Returns '' when offline.
    """
    q = re.sub(r"[^a-zA-Z0-9\s+#.-]", " ", (query or "")).strip()
    if not q or len(q) < 2:
        return ""
    headers = {"User-Agent": "FocusAgentV2/2.0 (Academic Student Productivity Agent)"}
    try:
        search_resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={"action": "opensearch", "search": q, "limit": 2, "namespace": 0, "format": "json"},
            headers=headers,
            timeout=timeout,
        )
        if search_resp.status_code != 200:
            return ""
        data = search_resp.json()
        titles = data[1] if isinstance(data, list) and len(data) > 1 else []
        if not titles:
            return ""
        page_title = titles[0].replace(" ", "_")
        sum_resp = requests.get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{page_title}",
            headers=headers,
            timeout=timeout,
        )
        if sum_resp.status_code == 200:
            extract = (sum_resp.json() or {}).get("extract") or ""
            return extract[:900].strip()
    except Exception:
        return ""
    return ""


class OnlineProvider(LLMProvider):
    """Optional OpenAI-compatible online adapter for research-heavy requests.

    Automatically detects ONLINE_LLM_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, or
    GEMINI_API_KEY from the environment so the user never has to configure
    provider routing manually.
    """

    name = "online"

    def __init__(self, model=None, base_url=None, api_key=None, timeout=60):
        env_online = os.environ.get("ONLINE_LLM_API_KEY")
        env_groq = os.environ.get("GROQ_API_KEY")
        env_openai = os.environ.get("OPENAI_API_KEY")
        env_gemini = os.environ.get("GEMINI_API_KEY")

        if api_key or env_online:
            self.api_key = api_key or env_online
            self.base_url = (base_url or os.environ.get("ONLINE_LLM_BASE_URL")
                             or "https://api.openai.com/v1").rstrip("/")
            self.model = model or os.environ.get("ONLINE_LLM_MODEL") or "gpt-4o-mini"
        elif env_groq:
            self.api_key = env_groq
            self.base_url = "https://api.groq.com/openai/v1"
            self.model = model or "llama-3.3-70b-versatile"
        elif env_gemini:
            self.api_key = env_gemini
            self.base_url = "https://generativelanguage.googleapis.com/v1beta/openai"
            self.model = model or "gemini-2.0-flash"
        elif env_openai:
            self.api_key = env_openai
            self.base_url = "https://api.openai.com/v1"
            self.model = model or "gpt-4o-mini"
        else:
            self.api_key = None
            self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
            self.model = model or "gpt-4o-mini"
        self.timeout = int(timeout)

    def available(self):
        return bool(self.api_key)

    def chat(self, system, user, history=None, temperature=0.2, max_tokens=2048):
        if not self.api_key:
            raise ProviderUnavailable(
                "Online research is not configured (set ONLINE_LLM_API_KEY). "
                "The answer below is generated locally, without web research.")
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        for h in (history or [])[-8:]:
            role = "user" if h.get("role") == "user" else "assistant"
            if h.get("content"):
                messages.append({"role": role, "content": h["content"][:2000]})
        messages.append({"role": "user", "content": user})
        data = _post_json(
            f"{self.base_url}/chat/completions",
            {"model": self.model, "messages": messages,
             "temperature": temperature, "max_tokens": max_tokens},
            self.timeout,
            headers={"Authorization": f"Bearer {self.api_key}"})
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise BadResponse("Online provider returned an unexpected response shape")
        if not content:
            raise BadResponse("Online provider returned empty output")
        return content

    def status(self):
        if not self.api_key:
            return False, "Not configured (ONLINE_LLM_API_KEY not set) - optional"
        return True, f"Configured ({self.model} via {self.base_url})"

    def capabilities(self):
        return {"local": False, "research": True}


class NullProvider(LLMProvider):
    """Used when the user sets provider='none'. Deterministic features only."""

    name = "none"

    def chat(self, system, user, history=None, temperature=0.2, max_tokens=2048):
        raise ProviderUnavailable("AI provider is disabled in Settings")

    def status(self):
        return False, "AI provider disabled - manual features still work"

    def capabilities(self):
        return {"local": False, "research": False}


# ==================== FACTORY ====================

def get_providers(settings=None):
    """Build (primary, online_or_None) providers from data settings + env.

    Env vars override stored settings (documented precedence).
    """
    settings = settings or {}
    agent_cfg = settings.get("agent") or {}
    provider_name = (os.environ.get("FOCUS_LLM_PROVIDER")
                     or agent_cfg.get("provider") or "ollama").lower()

    online = None
    op = OnlineProvider(model=agent_cfg.get("online_model") or None)
    if op.available():
        online = op

    if provider_name == "none":
        return NullProvider(), online
    if provider_name == "online" and online is not None:
        return online, None
    primary = OllamaProvider(
        endpoint=agent_cfg.get("endpoint"),
        model=agent_cfg.get("model"),
        timeout=agent_cfg.get("timeout_seconds"),
    )
    return primary, online


def new_call_id():
    return uuid.uuid4().hex[:16]
