from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import json

import httpx

try:
    from botocore.auth import SigV4Auth
    from botocore.awsrequest import AWSRequest
    from botocore.credentials import Credentials
except ModuleNotFoundError:  # pragma: no cover
    SigV4Auth = None
    AWSRequest = None
    Credentials = None

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
RawPostFunc = Callable[[str, dict[str, Any], dict[str, Any]], Awaitable[Any]]
BedrockSigner = Callable[[dict[str, Any]], dict[str, Any]]

SUPPORTED_INTERFACE_TYPES = {
    "openai_responses",
    "openai_compatible",
    "anthropic_messages",
    "amazon_bedrock",
    "gemini_native",
    "gemini_openai_compatible",
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
        provider_options: dict[str, Any] | None = None,
        raw_post_func: RawPostFunc | None = None,
        bedrock_signer: BedrockSigner | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.base_url = base_url
        self.interface_type = interface_type
        self.model_id = f"{provider}/{model}" if provider != "openai-compatible" else model
        self.completion_func = completion_func or default_completion
        self.responses_create_func = responses_create_func
        self.provider_options = provider_options or {}
        self.raw_post_func = raw_post_func
        self.bedrock_signer = bedrock_signer

    async def async_generate(self, prompt: str) -> str:
        if self.interface_type not in SUPPORTED_INTERFACE_TYPES:
            return f"[ERROR] unsupported interface type: {self.interface_type}"
        try:
            if self.interface_type == "openai_responses":
                return await self._generate_via_responses(prompt)
            if self.interface_type in {"anthropic_messages", "amazon_bedrock", "gemini_native"}:
                return await self._generate_via_raw_provider(prompt)
            return await self._generate_via_completion(prompt)
        except Exception as exc:  # pragma: no cover
            if litellm is not None and isinstance(exc, getattr(litellm, "RateLimitError", tuple())):
                raise
            if self.interface_type in {"openai_compatible", "gemini_openai_compatible"} and self.base_url:
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
        if self.interface_type not in {"openai_compatible", "gemini_openai_compatible"}:
            request_kwargs["top_p"] = 0.9
        response = await self.completion_func(**request_kwargs)
        content = self._extract_completion_content(response)
        if content:
            return content
        if self.interface_type in {"openai_compatible", "gemini_openai_compatible"} and self.base_url:
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
        url = self.base_url.rstrip("/") + "/responses"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model_id,
            "input": prompt,
        }
        last_error: Exception | None = None
        for _ in range(2):
            try:
                response = await self._post_json(url, headers, payload)
                response.raise_for_status()
                parsed = self._extract_responses_output(response.json())
                if parsed.startswith("[ERROR]"):
                    return f"[ERROR] /v1/responses {parsed[8:]}"
                return parsed
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise last_error

    async def _generate_via_raw_provider(self, prompt: str) -> str:
        request = self._build_raw_request(prompt)
        if request.get("provider") == "amazon_bedrock" and "Authorization" not in request["headers"]:
            return "[ERROR] Bedrock request signing failed"
        response = await self._post_json(request["url"], request["headers"], request["json"])
        response.raise_for_status()
        payload = response.json()
        if self.interface_type == "anthropic_messages":
            return self._extract_anthropic_output(payload)
        if self.interface_type == "gemini_native":
            return self._extract_gemini_output(payload)
        return "[ERROR] unsupported raw provider response"

    def _build_raw_request(self, prompt: str) -> dict[str, Any]:
        if self.interface_type == "anthropic_messages":
            version = self.provider_options.get("anthropic_version", "2023-06-01")
            max_tokens = int(self.provider_options.get("max_tokens", 512))
            return {
                "url": (self.base_url or "https://api.anthropic.com/v1").rstrip("/") + "/messages",
                "headers": {
                    "x-api-key": self.api_key,
                    "anthropic-version": version,
                    "Content-Type": "application/json",
                },
                "json": {
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": self.provider_options.get("temperature", 0.3),
                },
            }
        if self.interface_type == "gemini_native":
            api_version = self.provider_options.get("google_api_version", "v1beta")
            base = self.base_url or f"https://generativelanguage.googleapis.com/{api_version}/models"
            return {
                "url": base.rstrip("/") + f"/{self.model}:generateContent",
                "headers": {
                    "x-goog-api-key": self.provider_options.get("google_api_key", self.api_key),
                    "Content-Type": "application/json",
                },
                "json": {
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": self.provider_options.get("temperature", 0.3),
                        "topP": self.provider_options.get("top_p", 0.9),
                        "maxOutputTokens": int(self.provider_options.get("max_tokens", 512)),
                    },
                },
            }
        if self.interface_type == "amazon_bedrock":
            region = self.provider_options.get("aws_region", "us-east-1")
            request = {
                "provider": "amazon_bedrock",
                "url": f"https://bedrock-runtime.{region}.amazonaws.com/model/{self.model}/invoke",
                "headers": {"Content-Type": "application/json"},
                "json": {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": int(self.provider_options.get("max_tokens", 512)),
                    "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                    "temperature": self.provider_options.get("temperature", 0.3),
                },
            }
            return self._sign_bedrock_request(request)
        raise ValueError(f"unsupported raw request builder: {self.interface_type}")

    async def _post_json(self, url: str, headers: dict[str, Any], json_payload: dict[str, Any]):
        if self.raw_post_func is not None:
            return await self.raw_post_func(url, headers, json_payload)
        async with httpx.AsyncClient(timeout=45.0) as client:
            return await client.post(url, headers=headers, json=json_payload)

    def _sign_bedrock_request(self, request: dict[str, Any]) -> dict[str, Any]:
        if self.bedrock_signer is not None:
            return self.bedrock_signer(request)
        if SigV4Auth is None or AWSRequest is None or Credentials is None:
            return request
        access_key = self.provider_options.get("aws_access_key_id", "")
        secret_key = self.provider_options.get("aws_secret_access_key", "")
        session_token = self.provider_options.get("aws_session_token", "")
        if not access_key or not secret_key:
            return request
        credentials = Credentials(access_key, secret_key, session_token or None)
        aws_request = AWSRequest(method="POST", url=request["url"], data=json.dumps(request["json"]), headers=request["headers"])
        SigV4Auth(credentials, "bedrock", self.provider_options.get("aws_region", "us-east-1")).add_auth(aws_request)
        request["headers"] = dict(aws_request.headers.items())
        return request

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

    def _extract_anthropic_output(self, payload: dict[str, Any]) -> str:
        for item in payload.get("content") or []:
            if item.get("type") == "text" and item.get("text"):
                return item["text"]
        return "[ERROR] empty anthropic output"

    def _extract_gemini_output(self, payload: dict[str, Any]) -> str:
        for candidate in payload.get("candidates") or []:
            content = candidate.get("content") or {}
            for part in content.get("parts") or []:
                if part.get("text"):
                    return part["text"]
        return "[ERROR] empty gemini output"

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
        return "[ERROR] /v1/chat/completions empty chat completion payload"

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
        return "[ERROR] /v1/chat/completions SSE response did not contain content"
