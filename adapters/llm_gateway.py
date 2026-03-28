from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import json

import httpx

try:
    import litellm
    from litellm import acompletion as default_completion
    litellm.suppress_debug_info = True
    litellm.set_verbose = False
except ModuleNotFoundError:  # pragma: no cover
    litellm = None
    default_completion = None


CompletionFunc = Callable[..., Awaitable[Any]]
ResponsesCreateFunc = Callable[..., Awaitable[Any]]

SUPPORTED_INTERFACE_TYPES = {
    "openai_responses",
    "openai_compatible",
    "openai_compatible_chat",
    "anthropic",
    "amazon_bedrock",
    "google_gemini",
}


class UnifiedGateway:
    def __init__(
        self,
        provider: str,
        model: str,
        api_key: str,
        base_url: str | None = None,
        interface_type: str = "openai_compatible",
        completion_func: CompletionFunc | None = None,
        responses_create_func: ResponsesCreateFunc | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.interface_type = interface_type
        self.model_id = f"{provider}/{model}" if provider != "openai-compatible" else model
        self.completion_func = completion_func or default_completion
        self.responses_create_func = responses_create_func

    async def async_generate(self, prompt: str) -> str:
        if self.interface_type not in SUPPORTED_INTERFACE_TYPES:
            return f"[ERROR] unsupported interface type: {self.interface_type}"
        try:
            if self.interface_type == "openai_responses":
                return await self._generate_via_responses(prompt)
            return await self._generate_via_completion(prompt)
        except Exception as exc:  # pragma: no cover
            if litellm is not None and isinstance(exc, getattr(litellm, "RateLimitError", tuple())):
                raise
            if self.interface_type in {"openai_compatible", "openai_compatible_chat"} and self.base_url:
                try:
                    return await self._fallback_openai_chat(prompt)
                except Exception:
                    pass
            return f"[ERROR] {exc}"

    async def _generate_via_completion(self, prompt: str) -> str:
        if self.completion_func is None:
            return "[ERROR] litellm is not installed"
        request_kwargs = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": prompt}],
            "api_key": self.api_key,
            "api_base": self.base_url,
            "temperature": 0.3,
            "max_tokens": 512,
            "seed": 4242,
            "stream": False,
        }
        if self.interface_type not in {"openai_compatible", "openai_compatible_chat"}:
            request_kwargs["top_p"] = 0.9
        response = await self.completion_func(**request_kwargs)
        content = self._extract_completion_content(response)
        if content:
            return content
        if self.interface_type in {"openai_compatible", "openai_compatible_chat"} and self.base_url:
            return await self._fallback_openai_chat(prompt)
        return "[ERROR] empty completion response"

    async def _generate_via_responses(self, prompt: str) -> str:
        if self.responses_create_func is not None:
            response = await self.responses_create_func(
                model=self.model_id,
                input=prompt,
            )
            return getattr(response, "output_text", "") or "[ERROR] empty responses output"
        if not self.base_url:
            return "[ERROR] responses interface requires base_url"
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                self.base_url.rstrip("/") + "/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_id,
                    "input": prompt,
                },
            )
        response.raise_for_status()
        return self._extract_responses_output(response.json())

    def _extract_completion_content(self, response: Any) -> str:
        choices = getattr(response, "choices", None) or []
        if not choices:
            return ""
        first = choices[0]
        message = getattr(first, "message", None)
        if message is not None:
            content = getattr(message, "content", None)
            if isinstance(content, str):
                return content
        delta = getattr(first, "delta", None)
        if delta is not None:
            content = getattr(delta, "content", None)
            if isinstance(content, str):
                return content
        return ""

    def _extract_responses_output(self, payload: dict[str, Any]) -> str:
        if isinstance(payload.get("output_text"), str) and payload["output_text"]:
            return payload["output_text"]
        for item in payload.get("output") or []:
            for content in item.get("content") or []:
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        return "[ERROR] empty responses output"

    async def _fallback_openai_chat(self, prompt: str) -> str:
        assert self.base_url is not None
        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 512,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            return self._parse_sse_payload(response.text)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            if message.get("content"):
                return message["content"]
        return "[ERROR] empty chat completion payload"

    def _parse_sse_payload(self, payload: str) -> str:
        chunks = []
        for line in payload.splitlines():
            if not line.startswith("data: "):
                continue
            raw = line[6:].strip()
            if raw == "[DONE]":
                break
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            for choice in data.get("choices") or []:
                message = choice.get("message") or {}
                delta = choice.get("delta") or {}
                content = message.get("content") or delta.get("content")
                if isinstance(content, str) and content:
                    chunks.append(content)
        if chunks:
            return "".join(chunks)
        return "[ERROR] SSE response did not contain content"
