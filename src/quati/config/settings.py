from __future__ import annotations

import re
from ipaddress import ip_address
from urllib.parse import urlsplit

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from quati.core.browser.url_safety import validate_public_https_url

AIProviderName = str
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_PROVIDER_RE = re.compile(r"^[a-z0-9_]{1,32}$")


class Settings(BaseSettings):
    """Configuração local; segredos nunca são gravados no banco ou em logs."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="QUATI_", extra="ignore")

    ai_provider: AIProviderName = "none"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    openai_compatible_base_url: str = "http://127.0.0.1:1234/v1"
    openai_compatible_model: str = "local-model"
    openai_compatible_api_key: SecretStr | None = None
    adzuna_app_id: SecretStr | None = None
    adzuna_app_key: SecretStr | None = None

    @field_validator("ai_provider")
    @classmethod
    def validate_ai_provider_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not _PROVIDER_RE.fullmatch(normalized):
            raise ValueError("Nome do provedor de IA inválido.")
        return normalized

    @field_validator("ollama_base_url")
    @classmethod
    def validate_local_ollama_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS:
            raise ValueError("Ollama deve apontar para um endereço local.")
        return value.rstrip("/")

    @field_validator("openai_compatible_base_url")
    @classmethod
    def validate_openai_compatible_url(cls, value: str) -> str:
        parsed = urlsplit(value.strip())
        if parsed.hostname in _LOCAL_HOSTS:
            if (
                parsed.scheme != "http"
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("A API local deve usar HTTP sem credenciais na URL.")
            return value.rstrip("/")
        validate_public_https_url(value)
        try:
            address = ip_address(parsed.hostname or "")
        except ValueError:
            address = None
        if address is not None:
            raise ValueError("A API externa deve usar um domínio HTTPS público.")
        return value.rstrip("/")

    @property
    def ai_is_external(self) -> bool:
        if self.ai_provider == "gemini":
            return True
        if self.ai_provider != "openai_compatible":
            return False
        return urlsplit(self.openai_compatible_base_url).hostname not in _LOCAL_HOSTS

    @property
    def adzuna_is_configured(self) -> bool:
        return bool(self.adzuna_app_id and self.adzuna_app_key)
