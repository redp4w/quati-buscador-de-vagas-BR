from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from quati.domain.job import clean_text
from quati.security import EncryptedJSONVault

from .settings import AIProviderName, Settings

_MODEL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
_PROVIDERS = {"none", "ollama", "gemini", "openai_compatible"}


@dataclass(frozen=True, slots=True)
class AIConfiguration:
    provider: AIProviderName = "none"
    model: str = ""
    endpoint: str = ""
    api_key: str = ""
    include_profile_context: bool = False
    external_consent: bool = False

    def __post_init__(self) -> None:
        provider = clean_text(self.provider, max_length=32).lower()
        model = clean_text(self.model, max_length=200)
        endpoint = self.endpoint.strip()[:2_048]
        api_key = self.api_key.strip()[:10_000]
        if not isinstance(self.include_profile_context, bool) or not isinstance(
            self.external_consent, bool
        ):
            raise ValueError("Preferências de IA inválidas.")
        if provider not in _PROVIDERS:
            raise ValueError("Provedor de IA inválido.")
        if provider != "none" and not _MODEL_RE.fullmatch(model):
            raise ValueError("Modelo de IA inválido.")
        if provider == "gemini" and not api_key:
            raise ValueError("Informe a chave da API do Gemini.")
        if provider == "openai_compatible" and not endpoint:
            raise ValueError("Informe o endereço da API compatível.")
        if api_key and any(ord(character) < 33 or ord(character) == 127 for character in api_key):
            raise ValueError("Chave de API inválida.")
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "model", model)
        object.__setattr__(self, "endpoint", endpoint)
        object.__setattr__(self, "api_key", api_key)
        self.to_settings()

    def to_settings(self) -> Settings:
        values: dict[str, object] = {"ai_provider": self.provider, "_env_file": None}
        if self.provider == "ollama":
            values.update(ollama_model=self.model, ollama_base_url=self.endpoint)
        elif self.provider == "gemini":
            values.update(gemini_model=self.model, gemini_api_key=self.api_key)
        elif self.provider == "openai_compatible":
            values.update(
                openai_compatible_model=self.model,
                openai_compatible_base_url=self.endpoint,
                openai_compatible_api_key=self.api_key or None,
            )
        return Settings(**values)

    @classmethod
    def from_settings(cls, settings: Settings) -> AIConfiguration:
        if settings.ai_provider == "ollama":
            return cls("ollama", settings.ollama_model, settings.ollama_base_url)
        if settings.ai_provider == "gemini":
            key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
            return cls("gemini", settings.gemini_model, api_key=key)
        if settings.ai_provider == "openai_compatible":
            key = (
                settings.openai_compatible_api_key.get_secret_value()
                if settings.openai_compatible_api_key
                else ""
            )
            return cls(
                "openai_compatible",
                settings.openai_compatible_model,
                settings.openai_compatible_base_url,
                key,
            )
        return cls()


class AIConfigurationVault:
    """Configuração e chave de API cifradas localmente."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._vault = EncryptedJSONVault(path, max_ciphertext_bytes=64 * 1024)

    def exists(self) -> bool:
        return self._vault.exists()

    def uses_current_format(self) -> bool:
        return self._vault.uses_current_format()

    def save(self, configuration: AIConfiguration, passphrase: str) -> None:
        self._vault.save(
            {
                "version": 2,
                "provider": configuration.provider,
                "model": configuration.model,
                "endpoint": configuration.endpoint,
                "api_key": configuration.api_key,
                "include_profile_context": configuration.include_profile_context,
                "external_consent": configuration.external_consent,
            },
            passphrase,
        )

    def load(self, passphrase: str) -> AIConfiguration:
        value = self._vault.load(passphrase)
        if not isinstance(value, dict) or value.get("version") not in {1, 2}:
            raise ValueError("Configuração de IA inválida.")
        version = value["version"]
        expected = {"version", "provider", "model", "endpoint", "api_key"}
        if version == 2:
            expected |= {"include_profile_context", "external_consent"}
        if set(value) != expected:
            raise ValueError("Configuração de IA inválida.")
        string_fields = {"provider", "model", "endpoint", "api_key"}
        if not all(isinstance(value[key], str) for key in string_fields):
            raise ValueError("Configuração de IA inválida.")
        if version == 2 and not all(
            isinstance(value[key], bool) for key in {"include_profile_context", "external_consent"}
        ):
            raise ValueError("Configuração de IA inválida.")
        return AIConfiguration(
            provider=value["provider"],
            model=value["model"],
            endpoint=value["endpoint"],
            api_key=value["api_key"],
            include_profile_context=value.get("include_profile_context", False),
            external_consent=value.get("external_consent", False),
        )
