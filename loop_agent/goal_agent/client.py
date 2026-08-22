"""Minimal OpenAI-compatible Chat Completions client."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .config import ApiConfig


class ApiError(RuntimeError):
    """Raised when the compatible API cannot return a usable response."""


@dataclass(frozen=True)
class ChatResponse:
    message: dict[str, Any]
    usage: dict[str, Any]


class OpenAICompatibleClient:
    def __init__(self, config: ApiConfig) -> None:
        self.config = config

    @property
    def endpoint(self) -> str:
        base = self.config.base_url.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        timeout_seconds: float | None = None,
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
        }
        if self.config.temperature is not None:
            payload["temperature"] = self.config.temperature

        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            **self.config.extra_headers,
        }
        timeout = timeout_seconds or self.config.timeout_seconds
        deadline = time.monotonic() + timeout
        last_error: Exception | None = None

        for attempt in range(self.config.max_retries + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            request = urllib.request.Request(self.endpoint, data=body, headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=max(0.1, remaining)) as response:
                    decoded = json.loads(response.read().decode("utf-8"))
                choices = decoded.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise ApiError(f"API response has no choices: {decoded}")
                message = choices[0].get("message")
                if not isinstance(message, dict):
                    raise ApiError(f"API response has no assistant message: {decoded}")
                return ChatResponse(message=message, usage=decoded.get("usage", {}))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = ApiError(f"HTTP {exc.code} from compatible API: {detail}")
                if exc.code < 500 and exc.code != 429:
                    break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ApiError) as exc:
                last_error = exc

            if attempt < self.config.max_retries:
                backoff = min(2**attempt, 8, max(0, deadline - time.monotonic()))
                if backoff:
                    time.sleep(backoff)

        raise ApiError(str(last_error or "Unknown API error"))
