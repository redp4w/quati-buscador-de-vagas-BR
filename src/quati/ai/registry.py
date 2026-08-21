from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from quati.config import Settings

from .providers import (
    GeminiClient,
    GeneratedText,
    OllamaClient,
    OpenAICompatibleClient,
)


class TextGenerator(Protocol):
    def generate(self, prompt: str) -> GeneratedText: ...


@dataclass(frozen=True, slots=True)
class AIProviderModule:
    name: str
    label: str
    description: str
    factory: Callable[[Settings], TextGenerator] | None
    is_external: Callable[[Settings], bool]


class AIProviderRegistry:
    """Registro explícito: novos provedores entram sem alterar o serviço de IA."""

    def __init__(self) -> None:
        self._modules: dict[str, AIProviderModule] = {}

    def register(self, module: AIProviderModule) -> None:
        if module.name in self._modules:
            raise ValueError(f"Provedor de IA já registrado: {module.name}")
        self._modules[module.name] = module

    def modules(self) -> tuple[AIProviderModule, ...]:
        return tuple(self._modules.values())

    def get(self, name: str) -> AIProviderModule:
        try:
            return self._modules[name]
        except KeyError as exc:
            raise ValueError("Provedor de IA inválido.") from exc

    def create(self, settings: Settings) -> TextGenerator:
        module = self.get(settings.ai_provider)
        if module.factory is None:
            raise ValueError("Selecione um provedor de IA.")
        return module.factory(settings)

    def requires_external_consent(self, settings: Settings) -> bool:
        return self.get(settings.ai_provider).is_external(settings)


def build_ai_provider_registry() -> AIProviderRegistry:
    registry = AIProviderRegistry()
    registry.register(
        AIProviderModule(
            "none",
            "Análise local",
            "Calcula a compatibilidade sem usar modelo generativo nem acessar a internet.",
            None,
            lambda settings: False,
        )
    )
    registry.register(
        AIProviderModule(
            "ollama",
            "Ollama local",
            "Usa modelos abertos executados no seu computador.",
            OllamaClient,
            lambda settings: False,
        )
    )
    registry.register(
        AIProviderModule(
            "gemini",
            "Gemini API",
            "Usa uma conta do Google AI Studio e pede autorização antes de enviar dados.",
            GeminiClient,
            lambda settings: True,
        )
    )
    registry.register(
        AIProviderModule(
            "openai_compatible",
            "API compatível com OpenAI",
            "LM Studio, LocalAI, llama.cpp, vLLM ou serviço HTTPS compatível.",
            OpenAICompatibleClient,
            lambda settings: settings.ai_is_external,
        )
    )
    return registry
