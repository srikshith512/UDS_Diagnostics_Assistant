"""Ollama client. The LLM drafts language (answers, suggestions); it never decides protocol correctness."""
from __future__ import annotations

import httpx


class LlmError(RuntimeError):
    pass


class DisabledLlm:
    model = "disabled"

    def available(self) -> bool:
        return False

    def generate(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        raise LlmError("The language model is disabled (LLM_ENABLED=false).")


class OllamaClient:
    def __init__(self, url: str, model: str, timeout: float = 120.0):
        self.url, self.model, self.timeout = url, model, timeout

    def available(self) -> bool:
        try:
            r = httpx.get(f"{self.url}/api/tags", timeout=2.0)
            return r.status_code == 200 and any(m.get("name", "").split(":")[0] == self.model.split(":")[0] for m in r.json().get("models", []))
        except (httpx.HTTPError, ValueError):
            return False

    def generate(self, prompt: str, system: str | None = None, json_mode: bool = False) -> str:
        payload = {"model": self.model, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}
        if system:
            payload["system"] = system
        if json_mode:
            payload["format"] = "json"
        try:
            r = httpx.post(f"{self.url}/api/generate", json=payload, timeout=self.timeout)
            r.raise_for_status()
            return r.json().get("response", "").strip()
        except (httpx.HTTPError, ValueError) as exc:
            raise LlmError(f"Could not get a response from Ollama at {self.url}: {exc}") from exc
