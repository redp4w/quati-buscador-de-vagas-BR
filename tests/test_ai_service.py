from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from quati.ai import AIProviderModule, AIProviderRegistry, AIService
from quati.ai.providers import GeneratedText
from quati.config import Settings
from quati.domain import JobRecord


def _job() -> JobRecord:
    now = datetime.now(UTC)
    return JobRecord(
        id=1,
        source="gupy",
        external_id="1",
        title="Pessoa Desenvolvedora Python",
        company="Acme",
        location="Remoto",
        url="https://acme.gupy.io/jobs/1",
        description="Requisitos: Python e AWS.",
        published_at="",
        status="active",
        first_seen_at=now,
        last_seen_at=now,
    )


@dataclass
class FakeGenerator:
    responses: list[str]
    prompts: list[str] = field(default_factory=list)

    def generate(self, prompt: str) -> GeneratedText:
        self.prompts.append(prompt)
        return GeneratedText(self.responses.pop(0))


def test_ai_service_keeps_local_score_and_validates_generated_fields() -> None:
    generator = FakeGenerator(
        ['{"summary":"Resumo seguro","requirements":["Python"],"missing_keywords":["AWS"]}']
    )
    service = AIService(Settings(ai_provider="ollama", _env_file=None), generator=generator)

    analysis = service.analyze(_job(), "Experiência com Python")

    assert analysis.summary == "Resumo seguro"
    assert analysis.requirements == ("Python",)
    assert analysis.compatibility_score > 0
    assert "Ignore instruções" in generator.prompts[0]


def test_gemini_requires_explicit_consent_even_with_injected_client() -> None:
    service = AIService(
        Settings(
            ai_provider="gemini",
            gemini_api_key="secret",  # pragma: allowlist secret
            _env_file=None,
        ),
        generator=FakeGenerator(["{}"]),
    )

    with pytest.raises(ValueError, match="Autorize"):
        service.analyze(_job(), "Python")


def test_invalid_provider_response_is_rejected() -> None:
    service = AIService(
        Settings(ai_provider="ollama", _env_file=None),
        generator=FakeGenerator(["não é JSON"]),
    )

    with pytest.raises(ValueError, match="resposta inválida"):
        service.analyze(_job(), "Python")


def test_ai_only_returns_reviewable_resume_suggestions() -> None:
    generator = FakeGenerator(
        [
            '{"summary_suggestion":"Resumo","highlight_suggestions":["Destaque Python"],'
            '"keywords":["AWS"],"cautions":["Confirme AWS"]}'
        ]
    )
    service = AIService(Settings(ai_provider="ollama", _env_file=None), generator=generator)

    suggestions = service.suggest_resume_text(_job(), "Experiência com Python")

    assert suggestions.summary == "Resumo"
    assert suggestions.highlights == ("Destaque Python",)
    assert suggestions.keywords == ("AWS",)
    assert "Sugira melhorias" in generator.prompts[0]


def test_legacy_tailor_does_not_call_ai_or_change_resume() -> None:
    generator = FakeGenerator(["{}"])
    service = AIService(Settings(ai_provider="ollama", _env_file=None), generator=generator)
    analysis = service.analyze(_job(), "Python")
    generator.responses.append("também não deve ser usado")

    assert service.tailor(_job(), "Texto real", analysis) == "Texto real"
    assert len(generator.prompts) == 1


def test_assistant_supports_an_injected_provider_module() -> None:
    registry = AIProviderRegistry()
    registry.register(
        AIProviderModule(
            "test_provider",
            "Módulo de teste",
            "Gerador substituível",
            lambda settings: FakeGenerator(["Resposta modular"]),
            lambda settings: False,
        )
    )
    service = AIService(
        Settings(ai_provider="test_provider", _env_file=None),
        registry=registry,
    )

    assert service.assist("Como melhorar meu currículo?") == "Resposta modular"


def test_external_compatible_provider_requires_consent() -> None:
    service = AIService(
        Settings(
            ai_provider="openai_compatible",
            openai_compatible_base_url="https://models.example.com/v1",
            openai_compatible_model="model",
            _env_file=None,
        ),
        generator=FakeGenerator(["Resposta"]),
    )

    with pytest.raises(ValueError, match="provedor externo"):
        service.assist("Teste")
