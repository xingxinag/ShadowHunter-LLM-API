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


def test_gateway_omits_top_p_for_openai_compatible_chat() -> None:
    captured = {}

    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return DummyResponse("ok")

    gateway = UnifiedGateway("openai-compatible", "gpt-x", "k", completion_func=fake_completion)
    result = asyncio.run(gateway.async_generate("hello"))

    assert result == "ok"
    assert "top_p" not in captured


def test_gateway_keeps_top_p_for_other_interfaces() -> None:
    captured = {}

    async def fake_completion(**kwargs):
        captured.update(kwargs)
        return DummyResponse("ok")

    gateway = UnifiedGateway("anthropic", "claude-x", "k", interface_type="anthropic", completion_func=fake_completion)
    result = asyncio.run(gateway.async_generate("hello"))

    assert result == "ok"
    assert captured["top_p"] == 0.9


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
    gateway = UnifiedGateway("gemini", "gemini-2.5-pro", "k", interface_type="google_gemini")
    assert gateway.interface_type == "google_gemini"


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
