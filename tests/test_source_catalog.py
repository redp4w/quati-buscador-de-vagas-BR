from pathlib import Path

import pytest

from quati.config.sources import (
    SourceCatalogError,
    load_source_catalog,
    portal_endpoint,
)


def test_default_catalog_contains_public_portals_and_companies() -> None:
    load_source_catalog.cache_clear()
    catalog = load_source_catalog()

    assert catalog.path.name == "job_sources.yml"
    assert portal_endpoint("linkedin", "search_url") == "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    assert {company.id for company in catalog.companies} == {
        "honda",
        "teltecsolutions",
        "sharepeoplehub",
        "residclub",
        "ifood",
        "quintoandar",
        "xpinc",
        "stone",
        "ciandt",
        "bosch",
        "sgs",
    }
    assert all(company.url.startswith("https://") for company in catalog.companies)


def test_public_endpoint_can_be_overridden_by_environment(monkeypatch) -> None:
    monkeypatch.setenv(
        "QUATI_SOURCE_LINKEDIN_SEARCH_URL",
        "https://br.linkedin.com/jobs/search/",
    )
    load_source_catalog.cache_clear()
    try:
        assert portal_endpoint("linkedin", "search_url") == ("https://br.linkedin.com/jobs/search/")
    finally:
        load_source_catalog.cache_clear()


def test_catalog_rejects_a_portal_redirected_to_an_untrusted_host(
    tmp_path: Path, monkeypatch
) -> None:
    catalog_path = tmp_path / "sources.yml"
    catalog_path.write_text(
        """
version: 1
portals:
  linkedin:
    access_url: https://example.invalid/jobs/
companies: []
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("QUATI_SOURCES_FILE", str(catalog_path))
    load_source_catalog.cache_clear()
    try:
        with pytest.raises(SourceCatalogError, match="URL inválida"):
            load_source_catalog()
    finally:
        load_source_catalog.cache_clear()
