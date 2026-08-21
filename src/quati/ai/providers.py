from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import httpx

from quati.config import Settings
from quati.core.browser.url_safety import validate_public_hostname_resolution

_MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_MAX_GENERATED_TEXT = 50_000


@dataclass(frozen=True, slots=True)
class GeneratedText:
    text: str


def _response_object(response: httpx.Response) -> dict[str, object]:
    response.raise_for_status()
    declared = response.headers.get("content-length")
    if declared:
        try:
            declared_size = int(declared)
        except ValueError as exc:
            raise ValueError("A resposta da IA possui tamanho inválido.") from exc
        if declared_size < 0:
            raise ValueError("A resposta da IA possui tamanho inválido.")
        if declared_size > _MAX_RESPONSE_BYTES:
            raise ValueError("A resposta da IA excedeu o limite permitido.")
    content = bytearray()
    for chunk in response.iter_bytes():
        if len(content) + len(chunk) > _MAX_RESPONSE_BYTES:
            raise ValueError("A resposta da IA excedeu o limite permitido.")
        content.extend(chunk)
    try:
        value = json.loads(content)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("A IA retornou uma resposta inválida.") from exc
    if not isinstance(value, dict):
        raise ValueError("A IA retornou uma resposta inválida.")
    return value


def _generated_text(value: object) -> GeneratedText:
    return GeneratedText(text=str(value or "").replace("\x00", "").strip()[:_MAX_GENERATED_TEXT])


class OllamaClient:
    """Cliente local do Ollama; não aceita hosts remotos."""

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._base_url = settings.ollama_base_url
        self._model = settings.ollama_model
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(60.0, connect=5.0), trust_env=False
        )

    def generate(self, prompt: str) -> GeneratedText:
        with self._client.stream(
            "POST",
            f"{self._base_url}/api/generate",
            json={
                "model": self._model,
                "prompt": prompt[:20_000],
                "stream": False,
                "options": {"num_predict": 2_048},
            },
        ) as response:
            return _generated_text(_response_object(response).get("response"))


class GeminiClient:
    """Cliente Gemini criado apenas depois da autorização explícita no aplicativo."""

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        if settings.gemini_api_key is None:
            raise ValueError("Defina QUATI_GEMINI_API_KEY para usar Gemini.")
        self._api_key = settings.gemini_api_key.get_secret_value()
        self._model = settings.gemini_model
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(60.0, connect=5.0), trust_env=False
        )

    def generate(self, prompt: str) -> GeneratedText:
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(self._model, safe='-._')}:generateContent"
        )
        with self._client.stream(
            "POST",
            endpoint,
            headers={"x-goog-api-key": self._api_key},
            json={
                "contents": [{"parts": [{"text": prompt[:20_000]}]}],
                "generationConfig": {"maxOutputTokens": 2_048},
            },
        ) as response:
            candidates = _response_object(response).get("candidates") or []
        if not candidates:
            return GeneratedText(text="")
        if not isinstance(candidates, list) or not isinstance(candidates[0], dict):
            raise ValueError("A IA retornou uma resposta inválida.")
        content = candidates[0].get("content", {})
        if not isinstance(content, dict) or not isinstance(content.get("parts", []), list):
            raise ValueError("A IA retornou uma resposta inválida.")
        parts = content.get("parts", [])
        text = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
        return _generated_text(text)


class OpenAICompatibleClient:
    """Cliente para APIs locais ou HTTPS que implementam POST /chat/completions."""

    def __init__(self, settings: Settings, *, client: httpx.Client | None = None) -> None:
        self._base_url = settings.openai_compatible_base_url
        self._host = urlsplit(self._base_url).hostname or ""
        self._validate_dns = client is None and settings.ai_is_external
        self._model = settings.openai_compatible_model
        self._api_key = (
            settings.openai_compatible_api_key.get_secret_value()
            if settings.openai_compatible_api_key
            else ""
        )
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(60.0, connect=5.0), trust_env=False
        )

    def generate(self, prompt: str) -> GeneratedText:
        if self._validate_dns:
            validate_public_hostname_resolution(self._host)
        endpoint = self._base_url
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        with self._client.stream(
            "POST",
            endpoint,
            headers=headers,
            json={
                "model": self._model,
                "messages": [{"role": "user", "content": prompt[:20_000]}],
                "stream": False,
                "max_tokens": 2_048,
                "temperature": 0.2,
            },
        ) as response:
            choices = _response_object(response).get("choices") or []
        if not choices:
            return GeneratedText(text="")
        if not isinstance(choices, list) or not isinstance(choices[0], dict):
            raise ValueError("A IA retornou uma resposta inválida.")
        message = choices[0].get("message", {})
        if not isinstance(message, dict):
            raise ValueError("A IA retornou uma resposta inválida.")
        return _generated_text(message.get("content"))
