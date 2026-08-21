from dataclasses import replace
from datetime import UTC, datetime

import pytest

from quati.ai import (
    analyze_for_profile,
    analyze_locally,
    profile_search_requirements,
    rank_jobs_for_profile,
    rank_jobs_locally,
    tailor_resume,
)
from quati.config import Settings
from quati.domain import JobRecord
from quati.profile import CandidateProfile


def _job() -> JobRecord:
    now = datetime.now(UTC)
    return JobRecord(
        id=1,
        source="gupy",
        external_id="1",
        title="Analista Python",
        company="Acme",
        location="Remoto",
        url="https://acme.gupy.io/jobs/1",
        description="Requisitos: Python, SQL e segurança de aplicações.",
        published_at="2026-08-07",
        status="active",
        first_seen_at=now,
        last_seen_at=now,
    )


def test_local_analysis_never_needs_a_network_client() -> None:
    analysis = analyze_locally(_job(), "Experiência com Python, APIs e SQL.")

    assert analysis.compatibility_score > 0
    assert analysis.requirements
    assert "segurança" in analysis.missing_keywords


def test_local_tailoring_preserves_original_information() -> None:
    output = tailor_resume("Experiência com Python.", _job(), analyze_locally(_job(), "Python"))

    assert output == "Experiência com Python."


def test_ranks_all_jobs_by_compatibility_without_hiding_low_scores() -> None:
    compatible = _job()
    other = replace(
        compatible,
        id=2,
        external_id="2",
        title="Designer de Produto",
        description="Figma, pesquisa e prototipação.",
        url="https://acme.gupy.io/jobs/2",
    )

    ranked = rank_jobs_locally([other, compatible], "Experiência com Python e SQL")

    assert [item.job.id for item in ranked] == [1, 2]
    assert len(ranked) == 2
    assert ranked[0].analysis.compatibility_score > ranked[1].analysis.compatibility_score


def test_profile_search_requirements_accepts_complete_matching_profile() -> None:
    profile = CandidateProfile(
        "Ana",
        "",
        "",
        "Itu, SP",
        "Python, SQL e segurança",
        "",
        "Experiência em SOC",
        target_roles="Segurança da informação",
        target_levels="Júnior; Pleno",
        preferred_location="Itu, SP",
        work_modes="Híbrido; Remoto",
    )

    assert profile_search_requirements(profile) == ()


def test_profile_search_requirements_explains_missing_metrics() -> None:
    profile = CandidateProfile("Ana", "", "", "", "", "", "")

    assert profile_search_requirements(profile) == (
        "cargos de interesse",
        "níveis desejados",
        "competências ou experiência",
        "modalidades de trabalho",
        "cidade-base",
    )


def test_weighted_score_prioritizes_target_role_level_and_nearby_city() -> None:
    profile = CandidateProfile(
        "Ana",
        "ana@example.com",
        "",
        "Itu, SP",
        "Windows, redes, atendimento e segurança da informação",
        "",
        "Suporte técnico e análise de incidentes",
        target_roles="Segurança da informação; Analista de suporte",
        target_levels="Júnior; Pleno",
        preferred_location="Itu, SP",
        max_distance_km="80",
        work_modes="Presencial; Híbrido",
    )
    nearby = replace(
        _job(),
        title="Analista de suporte júnior",
        location="Sorocaba, SP",
        description="Atendimento, Windows, redes e análise de incidentes.",
    )
    unrelated = replace(
        _job(),
        id=2,
        title="Gerente comercial sênior",
        location="Rio de Janeiro, RJ",
        description="Vendas, metas e gestão comercial.",
    )

    nearby_analysis = analyze_for_profile(nearby, profile)
    ranked = rank_jobs_for_profile([unrelated, nearby], profile)

    assert nearby_analysis.compatibility_score >= 75
    assert nearby_analysis.distance_km is not None
    assert nearby_analysis.distance_km < 80
    assert nearby_analysis.seniority == "Júnior"
    assert [item.job.id for item in ranked] == [nearby.id, unrelated.id]


def test_unconfigured_preference_components_do_not_lower_score() -> None:
    profile = CandidateProfile("Ana", "", "", "", "Python SQL", "", "Python SQL")

    analysis = analyze_for_profile(_job(), profile)

    assert analysis.role_score is None
    assert analysis.location_score is None
    assert analysis.seniority_score is None
    assert analysis.skills_score is not None


def test_sparse_jobs_use_title_evidence_instead_of_fixed_neutral_score() -> None:
    profile = CandidateProfile(
        "Ana",
        "",
        "",
        "",
        "segurança da informação, IAM, suporte e redes",
        "",
        "análise de acessos e suporte técnico",
    )
    security = replace(
        _job(),
        title="Analista de segurança da informação júnior — IAM",
        description="",
    )
    unrelated = replace(
        _job(),
        id=2,
        title="Executivo comercial sênior",
        description="",
    )

    security_score = analyze_for_profile(security, profile).compatibility_score
    unrelated_score = analyze_for_profile(unrelated, profile).compatibility_score

    assert security_score > unrelated_score
    assert security_score != 60


def test_senior_job_cannot_look_highly_compatible_with_junior_profile() -> None:
    profile = CandidateProfile(
        "Ana",
        "",
        "",
        "Itu, SP",
        "Python, SQL, segurança de aplicações e análise de incidentes",
        "",
        "Experiência com Python, SQL e segurança de aplicações",
        target_roles="Analista Python",
        target_levels="Júnior",
        preferred_location="Itu, SP",
        work_modes="Presencial; Remoto",
    )
    senior = replace(
        _job(),
        title="Analista Python sênior",
        location="Itu, SP",
        description="Python, SQL, segurança de aplicações e análise de incidentes.",
    )
    junior = replace(senior, id=2, title="Analista Python júnior")

    senior_analysis = analyze_for_profile(senior, profile)
    junior_analysis = analyze_for_profile(junior, profile)

    assert senior_analysis.seniority_score == 0
    assert senior_analysis.compatibility_score <= 45
    assert junior_analysis.compatibility_score > senior_analysis.compatibility_score
    assert any("limitada a 45%" in reason for reason in senior_analysis.reasons)


def test_ollama_configuration_rejects_remote_hosts() -> None:
    with pytest.raises(ValueError):
        Settings(ollama_base_url="http://example.com:11434")
