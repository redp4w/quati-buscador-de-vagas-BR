from urllib.parse import parse_qs, urlsplit

import pytest

from quati.domain import JobInput
from quati.portals import (
    ASSISTED_PORTAL_IDS,
    AUTOMATIC_PORTAL_IDS,
    PARTIAL_PORTAL_IDS,
    SEARCHABLE_PORTAL_IDS,
)
from quati.services import (
    SearchRequest,
    build_assisted_search_targets,
    build_company_targets,
    build_search_targets,
    job_matches_search,
    job_matches_search_terms,
)
from quati.services.discovery import (
    SUPPORTED_ASSISTED_SOURCES,
    SUPPORTED_DISCOVERY_SOURCES,
    SUPPORTED_PARTIAL_SOURCES,
    SUPPORTED_SEARCH_SOURCES,
)


def test_builds_bounded_public_searches_for_all_supported_sources() -> None:
    request = SearchRequest(
        "segurança da informação",
        "São Paulo, SP",
        recency="7d",
        remote_only=True,
    )
    targets = {target.source: target.url for target in build_search_targets(request)}
    assert targets["empregos"].endswith("/vagas/seguranca-da-informacao-em-sao-paulo-sp")
    assert targets["empregando_brasil"].startswith("https://empregandobrasil.com.br/buscar/?")
    assert "inhire" not in targets  # InHire parte das empresas declaradas no YAML.


def test_portal_catalog_and_discovery_registry_stay_aligned() -> None:
    assert set(AUTOMATIC_PORTAL_IDS) == set(SUPPORTED_DISCOVERY_SOURCES)
    assert set(ASSISTED_PORTAL_IDS) == set(SUPPORTED_ASSISTED_SOURCES)
    assert set(PARTIAL_PORTAL_IDS) == set(SUPPORTED_PARTIAL_SOURCES)
    assert set(SEARCHABLE_PORTAL_IDS) == set(SUPPORTED_SEARCH_SOURCES)


def test_linkedin_builds_automatic_search_with_guest_api() -> None:
    request = SearchRequest(
        "Windows",
        "Sorocaba, SP",
        sources=("linkedin",),
        roles=("Analista de suporte", "Analista de segurança"),
        levels=("Júnior", "Pleno"),
        work_modes=("Híbrido", "Remoto"),
        recency="7d",
    )

    targets = build_search_targets(request)
    assert len(targets) == 2
    first_query = parse_qs(urlsplit(targets[0].url).query)
    assert first_query == {
        "keywords": ["Analista de suporte Windows"],
        "location": ["Sorocaba, SP"],
        "sortBy": ["DD"],
        "f_TPR": ["r604800"],
        "f_E": ["2,3"],
        "f_WT": ["3,2"],
    }
    assert build_assisted_search_targets(request) == ()


def test_configured_company_pages_are_bounded_and_filtered() -> None:
    request = SearchRequest("cozinheiro", "Itu, SP", sources=("inhire",))

    targets = build_company_targets(request)

    assert {target.label for target in targets} == {"Share People Hub", "Resid Club"}
    assert all(target.source == "inhire" for target in targets)
    assert all(target.apply_text_filter for target in targets)


def test_company_page_text_filter_accepts_professions_outside_technology() -> None:
    request = SearchRequest("cozinha industrial", roles=("Cozinheiro",), sources=("inhire",))
    matching = _job("Itu, SP", description="Preparo de refeições em cozinha industrial")
    matching = JobInput(
        source="inhire",
        external_id="cozinheiro",
        title="Cozinheiro",
        company="Empresa",
        location="Itu, SP",
        url="https://empresa.inhire.app/vagas/cozinheiro",
        description=matching.description,
    )
    unrelated = JobInput(
        source="inhire",
        external_id="dev",
        title="Desenvolvedor Python",
        company="Empresa",
        location="Itu, SP",
        url="https://empresa.inhire.app/vagas/dev",
        description="Desenvolvimento de sistemas web.",
    )

    assert job_matches_search_terms(matching, request)
    assert not job_matches_search_terms(unrelated, request)


def test_gupy_uses_validated_state_and_omits_country_as_state() -> None:
    state_url = build_search_targets(
        SearchRequest("Python", "Campinas, SP", sources=("gupy",))
    )[0].url
    country_url = build_search_targets(
        SearchRequest("Python", "Brasil", sources=("gupy",))
    )[0].url

    # Aceita tanto %20 quanto + para espaços na codificação URL
    assert "state=S%C3%A3o" in state_url and "Paulo" in state_url
    assert "state=" not in country_url
    assert "city=" not in country_url


def test_gupy_expands_city_and_state_to_state_search_for_nearby_jobs() -> None:
    url = build_search_targets(SearchRequest("Cozinheiro", "Itu, SP", sources=("gupy",)))[0].url

    # Aceita tanto %20 quanto + para espaços na codificação URL
    assert "state=S%C3%A3o" in url and "Paulo" in url
    assert "city=Itu" in url
    assert "Seguran%C3%A7a" not in url


def test_rejects_empty_or_unknown_discovery_requests() -> None:
    try:
        SearchRequest("   ")
    except ValueError as exc:
        assert "Informe" in str(exc)
    else:
        raise AssertionError("A busca vazia deveria ser rejeitada.")

    try:
        SearchRequest("Python", sources=("fonte-desconhecida",))
    except ValueError as exc:
        assert "fonte" in str(exc).lower()
    else:
        raise AssertionError("A fonte desconhecida deveria ser rejeitada.")


def test_multiple_roles_create_bounded_queries_per_portal() -> None:
    request = SearchRequest(
        "Windows",
        "Itu, SP",
        sources=("gupy", "empregos"),
        roles=("Analista de segurança", "Analista de suporte"),
        levels=("Júnior", "Pleno"),
    )

    automatic_targets = build_search_targets(request)
    gupy_targets = [item for item in automatic_targets if item.source == "gupy"]
    empregos_targets = [item for item in automatic_targets if item.source == "empregos"]

    assert len(gupy_targets) == 2
    assert {target.label for target in gupy_targets} == {""}
    assert len(empregos_targets) == 2
    assert empregos_targets[0].url.endswith("/vagas/analista-de-seguranca-windows-em-itu-sp")


def test_jobbol_uses_bounded_public_role_and_location_routes() -> None:
    request = SearchRequest(
        "Windows",
        "Itu, SP",
        sources=("jobbol",),
        roles=("Analista de segurança", "Analista de suporte"),
    )

    targets = build_assisted_search_targets(request)

    assert [target.url for target in targets] == [
        "https://www.jobbol.com.br/cargos/analista-de-seguranca/itu-sp",
        "https://www.jobbol.com.br/cargos/analista-de-suporte/itu-sp",
    ]


def test_programathor_uses_public_filters_without_account_data() -> None:
    request = SearchRequest(
        "Python",
        "Itu, SP",
        sources=("programathor",),
        remote_only=True,
        levels=("Júnior",),
    )

    target = build_assisted_search_targets(request)[0]
    query = parse_qs(urlsplit(target.url).query)

    assert urlsplit(target.url).path == "/jobs-python"
    assert query == {"remoto": ["true"], "expertise": ["Júnior"]}


def test_programathor_creates_one_query_for_each_role() -> None:
    request = SearchRequest(
        "Windows",
        sources=("programathor",),
        roles=("Segurança da informação", "Analista de suporte"),
    )

    targets = build_assisted_search_targets(request)

    assert [urlsplit(target.url).path for target in targets] == [
        "/jobs-seguranca-da-informacao-windows",
        "/jobs-analista-de-suporte-windows",
    ]


def test_vagas_com_uses_indexable_public_search_route() -> None:
    request = SearchRequest(
        "SIEM",
        "Itu, SP",
        sources=("vagas_com",),
        roles=("Analista de segurança",),
    )

    target = build_search_targets(request)[0]

    assert urlsplit(target.url).path == "/vagas-de-analista-de-seguranca-siem"
    assert parse_qs(urlsplit(target.url).query)["q"] == ["Analista de segurança SIEM"]


def test_empregando_brasil_uses_public_pcd_filter() -> None:
    request = SearchRequest(
        "administrativo",
        "Sorocaba, SP",
        sources=("empregando_brasil",),
        pcd_only=True,
    )

    query = parse_qs(urlsplit(build_search_targets(request)[0].url).query)

    assert query["q"] == ["administrativo"]
    assert query["city"] == ["Sorocaba, SP"]
    assert query["diversity"] == ["pcd"]


def test_adzuna_builds_brazilian_api_search_without_credentials() -> None:
    request = SearchRequest(
        "cozinha industrial",
        "Sorocaba, SP",
        sources=("adzuna",),
        recency="7d",
    )

    target = build_search_targets(request)[0]
    query = parse_qs(urlsplit(target.url).query)

    assert target.source == "adzuna"
    assert urlsplit(target.url).path == "/v1/api/jobs/br/search/1"
    assert query == {
        "results_per_page": ["50"],
        "what": ["cozinha industrial"],
        "sort_by": ["date"],
        "where": ["Sorocaba, SP"],
        "max_days_old": ["7"],
    }
    assert "app_id" not in query
    assert "app_key" not in query


def test_solides_builds_automatic_public_search_url() -> None:
    request = SearchRequest("cozinha industrial", sources=("solides",))

    target = build_search_targets(request)[0]
    query = parse_qs(urlsplit(target.url).query)

    assert urlsplit(target.url).path == "/jobs/v3/portal-vacancies-new"
    assert query == {"title": ["cozinha industrial"], "take": ["10"], "page": ["1"]}
    assert build_assisted_search_targets(request) == ()


def _job(location: str, *, description: str = "", source: str = "linkedin") -> JobInput:
    return JobInput(
        source=source,
        external_id=location or "unknown",
        title="Analista",
        company="Empresa",
        location=location,
        url=f"https://www.linkedin.com/jobs/view/{abs(hash(location))}",
        description=description,
    )


def test_city_search_keeps_nearby_jobs_and_rejects_other_states() -> None:
    request = SearchRequest("Analista", "Sorocaba, SP", max_distance_km=80)

    assert job_matches_search(_job("Itu, SP"), request)
    assert not job_matches_search(_job("Rio de Janeiro, RJ"), request)


def test_state_search_accepts_only_jobs_from_the_selected_state() -> None:
    request = SearchRequest("Analista", "SP")

    assert job_matches_search(_job("Itu, SP"), request)
    assert not job_matches_search(_job("Rio de Janeiro, RJ"), request)


def test_search_rejects_city_without_state() -> None:
    with pytest.raises(ValueError, match="estado"):
        SearchRequest("Analista", "Sorocaba")


def test_remote_anywhere_requires_remote_mode() -> None:
    remote_request = SearchRequest(
        "Analista",
        "Sorocaba, SP",
        work_modes=("Remoto",),
    )
    local_request = SearchRequest("Analista", "Sorocaba, SP")

    assert job_matches_search(_job("Brasil", description="Trabalho remoto"), remote_request)
    assert not job_matches_search(_job("Brasil", description="Trabalho remoto"), local_request)


def test_blank_location_searches_brazil_and_blocks_known_foreign_results() -> None:
    request = SearchRequest("Analista", "")

    assert job_matches_search(_job("São Paulo, SP"), request)
    assert job_matches_search(_job("Remoto"), request)
    assert not job_matches_search(_job("New York, NY, United States"), request)


def test_blank_location_with_remote_mode_rejects_onsite_jobs() -> None:
    request = SearchRequest("Analista", "", work_modes=("Remoto",))

    assert job_matches_search(_job("Remoto"), request)
    assert not job_matches_search(_job("Rio de Janeiro, RJ", description="Presencial"), request)


def test_remote_filter_trusts_supported_portal_when_card_omits_mode() -> None:
    request = SearchRequest(
        "Analista",
        "Sorocaba, SP",
        remote_only=True,
        work_modes=("Remoto",),
    )

    assert job_matches_search(_job("Brasil", source="indeed"), request)


def test_location_parser_accepts_common_brazilian_separators() -> None:
    request = SearchRequest("Analista", "Sorocaba, SP", max_distance_km=100)

    assert job_matches_search(_job("Itu / SP"), request)
    assert job_matches_search(_job("São Paulo/SP (Híbrido)"), request)


def test_pcd_filter_requires_explicit_eligibility() -> None:
    request = SearchRequest("Analista", "", pcd_only=True)

    assert job_matches_search(
        _job("Remoto", description="Vaga inclusiva para pessoas com deficiência."), request
    )
    assert job_matches_search(_job("Remoto", description="Oportunidade exclusiva PCD."), request)
    assert not job_matches_search(_job("Remoto", description="Oportunidade geral."), request)
    assert not job_matches_search(
        _job("Remoto", description="Esta vaga não é elegível para PCD."), request
    )
