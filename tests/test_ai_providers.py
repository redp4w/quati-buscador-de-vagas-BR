import httpx
import pytest

from quati.ai.providers import GeminiClient, OllamaClient, OpenAICompatibleClient
from quati.config import Settings


def test_gemini_sends_api_key_in_header_not_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "secret-value" not in str(request.url)
        assert request.headers["x-goog-api-key"] == "secret-value"
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Resposta"}]}}]},
        )

    settings = Settings(
        ai_provider="gemini",
        gemini_api_key="secret-value",  # pragma: allowlist secret
        _env_file=None,
    )
    client = GeminiClient(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.generate("Teste").text == "Resposta"


def test_ollama_uses_only_local_endpoint_and_disables_streaming() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "127.0.0.1"
        assert request.url.path == "/api/generate"
        assert b'"stream":false' in request.content
        return httpx.Response(200, json={"response": "Local"})

    settings = Settings(ai_provider="ollama", _env_file=None)
    client = OllamaClient(settings, client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.generate("Teste").text == "Local"


def test_openai_compatible_client_keeps_key_in_header() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://models.example.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret-value"
        assert "secret-value" not in str(request.url)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "Compatível"}}]},
        )

    settings = Settings(
        ai_provider="openai_compatible",
        openai_compatible_base_url="https://models.example.com/v1",
        openai_compatible_model="modelo-livre",
        openai_compatible_api_key="secret-value",  # pragma: allowlist secret
        _env_file=None,
    )
    client = OpenAICompatibleClient(
        settings, client=httpx.Client(transport=httpx.MockTransport(handler))
    )

    assert client.generate("Teste").text == "Compatível"


def test_ai_provider_rejects_oversized_response() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=b"x" * (2 * 1024 * 1024 + 1))
        )
    )
    provider = OllamaClient(Settings(ai_provider="ollama", _env_file=None), client=client)

    with pytest.raises(ValueError, match="excedeu"):
        provider.generate("Teste")
