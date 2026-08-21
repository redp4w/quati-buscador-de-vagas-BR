from datetime import UTC, datetime

import pytest

from quati.ai import analyze_for_profile
from quati.domain import JobRecord
from quati.profile import CandidateProfile


def _job(identifier: int, title: str, description: str) -> JobRecord:
    now = datetime.now(UTC)
    return JobRecord(
        id=identifier,
        source="gupy",
        external_id=str(identifier),
        title=title,
        company="Empresa Exemplo",
        location="Sorocaba, SP",
        url=f"https://empresa.gupy.io/jobs/{identifier}",
        description=description,
        published_at="",
        status="active",
        first_seen_at=now,
        last_seen_at=now,
    )


@pytest.mark.parametrize(
    ("profile", "job"),
    [
        (
            CandidateProfile(
                name="Pessoa Administração",
                email="",
                phone="",
                address="",
                skills="Excel, atendimento, pacote Office, controle de documentos",
                education="Administração",
                experience="Rotinas administrativas e organização de planilhas",
                target_roles="Assistente administrativo; Auxiliar administrativo",
                target_levels="Júnior",
                preferred_location="Itu, SP",
                max_distance_km="80",
                work_modes="Presencial; Híbrido",
            ),
            _job(
                1,
                "Assistente Administrativo Júnior",
                "Atendimento, planilhas em Excel, documentos e pacote Office.",
            ),
        ),
        (
            CandidateProfile(
                name="Pessoa Engenharia",
                email="",
                phone="",
                address="",
                skills="AutoCAD, projetos, leitura de desenho, Excel",
                education="Engenharia Civil",
                experience="Estágio em acompanhamento de obras civis",
                target_roles="Engenheiro civil; Assistente de engenharia civil",
                target_levels="Estágio; Júnior",
                preferred_location="Itu, SP",
                max_distance_km="100",
                work_modes="Presencial",
            ),
            _job(
                2,
                "Assistente de Engenharia Civil Jr",
                "Projetos de obras, AutoCAD e leitura de desenho técnico.",
            ),
        ),
        (
            CandidateProfile(
                name="Pessoa Nutrição",
                email="",
                phone="",
                address="",
                skills="UAN, boas práticas, segurança alimentar, cardápios",
                education="Nutrição",
                experience="Estágio em unidade de alimentação e nutrição",
                target_roles="Nutricionista; Assistente de nutrição",
                target_levels="Estágio; Júnior",
                preferred_location="Itu, SP",
                max_distance_km="100",
                work_modes="Presencial",
            ),
            _job(
                3,
                "Nutricionista Júnior",
                "Gestão de UAN, elaboração de cardápios e segurança alimentar.",
            ),
        ),
    ],
)
def test_relevant_jobs_score_well_across_professions(
    profile: CandidateProfile, job: JobRecord
) -> None:
    analysis = analyze_for_profile(job, profile)

    assert analysis.compatibility_score >= 60
    assert analysis.role_score is not None and analysis.role_score >= 80
    assert analysis.location_score is not None and analysis.location_score >= 70


def test_senior_job_is_capped_for_junior_nutrition_profile() -> None:
    profile = CandidateProfile(
        name="Pessoa Nutrição",
        email="",
        phone="",
        address="",
        skills="UAN, cardápios, segurança alimentar",
        education="Nutrição",
        experience="Estágio em UAN",
        target_roles="Nutricionista",
        target_levels="Júnior",
    )
    analysis = analyze_for_profile(
        _job(4, "Nutricionista Sênior", "Gestão de UAN e elaboração de cardápios."),
        profile,
    )

    assert analysis.seniority == "Sênior"
    assert analysis.compatibility_score <= 45


def test_civil_engineering_is_not_equivalent_to_software_engineering() -> None:
    profile = CandidateProfile(
        name="Pessoa Engenharia",
        email="",
        phone="",
        address="",
        skills="AutoCAD, obras e desenho técnico",
        education="Engenharia Civil",
        experience="Estágio em obras",
        target_roles="Engenheiro civil",
        target_levels="Júnior",
    )
    analysis = analyze_for_profile(
        _job(5, "Engenheiro de Software Júnior", "Python, APIs e microsserviços."),
        profile,
    )

    assert analysis.role_score is not None and analysis.role_score < 55
    assert analysis.compatibility_score <= 65
