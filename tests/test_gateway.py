import asyncio

import adapters.llm_gateway as gateway_module
from adapters.llm_gateway import UnifiedGateway


class DummyChoice:
    def __init__(self, content: str) -> None:
        self.message = type("Message", (), {"content": content})()


class DummyResponse:
    def __init__(self, content: str) -> None:
        self.choices = [DummyChoice(content)]


class DummyResponsesOutput:
    def __init__(self, text: str) -> None:
        self.output_text = text


def test_gateway_preserves_openai_compatible_model_name() -> None:
    gateway = UnifiedGateway("openai-compatible", "gpt-x", "k")
    assert gateway.model_id == "gpt-x"


def test_gateway_prefixes_other_providers() -> None:
    gateway = UnifiedGateway("anthropic", "claude-x", "k")
    assert gateway.model_id == "anthropic/claude-x"


def test_gateway_sends_locked_sampling_arguments() -> None:
    captured = {}

    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return DummyResponse("ok")

    gateway = UnifiedGateway("openai-compatible", "gpt-x", "k", completion_func=fake_completion)
    result = asyncio.run(gateway.async_generate("hello"))

    assert result == "ok"
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == 512
    assert captured["seed"] == 4242
    assert captured["stream"] is False


def test_gateway_omits_top_p_for_openai_compatible() -> None:
    captured = {}

    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return DummyResponse("ok")

    gateway = UnifiedGateway("openai-compatible", "gpt-x", "k", completion_func=fake_completion)
    result = asyncio.run(gateway.async_generate("hello"))

    assert result == "ok"
    assert "top_p" not in captured


def test_gateway_keeps_top_p_for_other_interfaces() -> None:
    gateway = UnifiedGateway("gemini", "gemini-2.5-pro", "k", interface_type="gemini_native")

    request = gateway._build_raw_request("hello")

    assert request["json"]["generationConfig"]["topP"] == 0.9


def test_gateway_returns_error_marker_for_generic_exception() -> None:
    async def fake_completion(**kwargs):
        raise RuntimeError("boom")

    gateway = UnifiedGateway("openai-compatible", "gpt-x", "k", completion_func=fake_completion)
    result = asyncio.run(gateway.async_generate("hello"))

    assert result == "[ERROR] boom"


def test_gateway_enables_litellm_debug_suppression() -> None:
    if gateway_module.litellm is None:
        return

    assert gateway_module.litellm.suppress_debug_info is True


def test_gateway_builds_openai_responses_payload() -> None:
    captured = {}

    async def fake_responses_create(**kwargs):
        captured.update(kwargs)
        return DummyResponsesOutput("pong")

    gateway = UnifiedGateway(
        "openai",
        "gpt-5.4",
        "k",
        interface_type="openai_responses",
        responses_create_func=fake_responses_create,
    )

    result = asyncio.run(gateway.async_generate("hello"))

    assert result == "pong"
    assert captured["model"] == "openai/gpt-5.4"
    assert captured["input"] == "hello"


def test_gateway_extracts_text_from_raw_responses_payload() -> None:
    gateway = UnifiedGateway("openai-compatible", "gpt-5.2", "k", base_url="https://example.com/v1", interface_type="openai_responses")

    parsed = gateway._extract_responses_output(
        {
            "output": [
                {
                    "content": [
                        {"type": "output_text", "text": "pong"}
                    ]
                }
            ]
        }
    )

    assert parsed == "pong"


def test_gateway_supports_named_interface_types() -> None:
    gateway = UnifiedGateway("gemini", "gemini-2.5-pro", "k", interface_type="gemini_native")
    assert gateway.interface_type == "gemini_native"


def test_gateway_supports_gemini_openai_compatibility_name() -> None:
    gateway = UnifiedGateway("openai-compatible", "gemini-2.5-pro", "k", interface_type="gemini_openai_compatible")
    assert gateway.interface_type == "gemini_openai_compatible"


def test_gateway_falls_back_to_raw_openai_chat_on_completion_exception() -> None:
    async def failing_completion(**kwargs):
        raise RuntimeError("blocked")

    async def fake_fallback(prompt: str) -> str:
        return f"raw:{prompt}"

    gateway = UnifiedGateway(
        "openai-compatible",
        "gpt-x",
        "k",
        base_url="https://example.com/v1",
            interface_type="openai_compatible",
        completion_func=failing_completion,
    )
    gateway._fallback_openai_chat = fake_fallback  # type: ignore[method-assign]

    result = asyncio.run(gateway.async_generate("hello"))

    assert result == "raw:hello"


def test_gateway_builds_anthropic_request_with_provider_headers() -> None:
    gateway = UnifiedGateway(
        "anthropic",
        "claude-3-7-sonnet",
        "k",
        base_url="https://api.anthropic.com/v1",
        interface_type="anthropic_messages",
        provider_options={"anthropic_version": "2023-06-01", "max_tokens": 333},
    )

    request = gateway._build_raw_request("hello")

    assert request["url"].endswith("/messages")
    assert request["headers"]["x-api-key"] == "k"
    assert request["headers"]["anthropic-version"] == "2023-06-01"
    assert request["json"]["max_tokens"] == 333
    assert request["json"]["messages"][0]["content"] == "hello"


def test_gateway_builds_gemini_request_with_contents_shape() -> None:
    gateway = UnifiedGateway(
        "gemini",
        "gemini-2.5-pro",
        "k",
        base_url="https://generativelanguage.googleapis.com/v1beta/models",
        interface_type="gemini_native",
    )

    request = gateway._build_raw_request("hello")

    assert ":generateContent" in request["url"]
    assert request["headers"]["x-goog-api-key"] == "k"
    assert request["json"]["contents"][0]["parts"][0]["text"] == "hello"


def test_gateway_builds_bedrock_request_with_runtime_options() -> None:
    def fake_signer(request: dict) -> dict:
        request["headers"]["Authorization"] = "AWS4-HMAC-SHA256 Signed"
        return request

    gateway = UnifiedGateway(
        "bedrock",
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "k",
        interface_type="amazon_bedrock",
        provider_options={
            "aws_region": "us-east-1",
            "aws_access_key_id": "AKIA",
            "aws_secret_access_key": "SECRET",
            "max_tokens": 222,
        },
        bedrock_signer=fake_signer,
    )

    request = gateway._build_raw_request("hello")

    assert request["url"].endswith("/model/anthropic.claude-3-5-sonnet-20241022-v2:0/invoke")
    assert request["headers"]["Authorization"] == "AWS4-HMAC-SHA256 Signed"
    assert request["headers"]["Content-Type"] == "application/json"
    assert request["json"]["max_tokens"] == 222
    assert request["json"]["anthropic_version"] == "bedrock-2023-05-31"


def test_gateway_retries_responses_server_errors_then_succeeds() -> None:
    class DummyHttpResponse:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self) -> dict:
            return self._payload

    calls = []

    async def fake_post(url: str, headers: dict, json: dict):
        calls.append((url, headers, json))
        if len(calls) == 1:
            return DummyHttpResponse(500, {})
        return DummyHttpResponse(200, {"output": [{"content": [{"type": "output_text", "text": "pong"}]}]})

    gateway = UnifiedGateway(
        "openai-compatible",
        "gpt-5.2",
        "k",
        base_url="https://api.example.com/v1",
        interface_type="openai_responses",
        raw_post_func=fake_post,
    )

    result = asyncio.run(gateway.async_generate("hello"))

    assert result == "pong"
    assert len(calls) == 2


def test_gateway_reports_empty_responses_output_with_endpoint_context() -> None:
    class DummyHttpResponse:
        status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"output": []}

    async def fake_post(url: str, headers: dict, json: dict):
        return DummyHttpResponse()

    gateway = UnifiedGateway(
        "openai-compatible",
        "gpt-5.2",
        "k",
        base_url="https://api.example.com/v1",
        interface_type="openai_responses",
        raw_post_func=fake_post,
    )

    result = asyncio.run(gateway.async_generate("hello"))

    assert "/responses" in result
    assert "empty responses output" in result


def test_gateway_reports_empty_chat_stream_with_endpoint_context() -> None:
    async def failing_completion(**kwargs):
        raise RuntimeError("blocked")

    async def fake_fallback(prompt: str) -> str:
        return "[ERROR] /v1/chat/completions SSE response did not contain content"

    gateway = UnifiedGateway(
        "openai-compatible",
        "gpt-x",
        "k",
        base_url="https://example.com/v1",
        interface_type="openai_compatible",
        completion_func=failing_completion,
    )
    gateway._fallback_openai_chat = fake_fallback  # type: ignore[method-assign]

    result = asyncio.run(gateway.async_generate("hello"))

    assert "/v1/chat/completions" in result
