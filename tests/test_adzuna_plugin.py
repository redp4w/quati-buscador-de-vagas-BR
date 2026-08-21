from urllib.parse import parse_qs, urlsplit

import pytest

from quati.config import JobSourceConfiguration, JobSourceConfigurationVault
from quati.plugins import AdzunaPlugin


class AdzunaJsonBrowser:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.request_url = ""

    def fetch_json(
        self,
        url: str,
        *,
        allowed_hosts: tuple[str, ...],
        headers: dict[str, str] | None = None,
    ) -> object:
        assert allowed_hosts == ("api.adzuna.com",)
        assert headers is None
        self.request_url = url
        return self.payload


def test_adzuna_collects_official_api_results_with_runtime_credentials() -> None:
    browser = AdzunaJsonBrowser(
        {
            "results": [
                {
                    "id": "123",
                    "title": "Cozinheiro",
                    "company": {"display_name": "Restaurante Exemplo"},
                    "location": {"display_name": "Sorocaba, São Paulo"},
                    "redirect_url": "https://www.adzuna.com.br/details/123",
                    "description": "Cozinha industrial",
                    "created": "2026-08-15T10:00:00Z",
                }
            ]
        }
    )
    plugin = AdzunaPlugin("app-id", "app-key")
    entry_url = (
        "https://api.adzuna.com/v1/api/jobs/br/search/1?"
        "results_per_page=50&what=cozinheiro&where=Sorocaba%2C+SP"
    )

    jobs = plugin.collect(browser, entry_url)

    assert len(jobs) == 1
    assert jobs[0].title == "Cozinheiro"
    assert jobs[0].company == "Restaurante Exemplo"
    request_query = parse_qs(urlsplit(browser.request_url).query)
    assert request_query["app_id"] == ["app-id"]
    assert request_query["app_key"] == ["app-key"]
    assert "app_id" not in plugin.prepare_entry_url(entry_url)


def test_adzuna_requires_credentials_and_rejects_them_in_the_entry_url() -> None:
    plugin = AdzunaPlugin()
    entry_url = "https://api.adzuna.com/v1/api/jobs/br/search/1?what=cozinheiro"

    with pytest.raises(ValueError, match="Configure"):
        plugin.collect(AdzunaJsonBrowser({}), entry_url)
    with pytest.raises(ValueError, match="parâmetros"):
        plugin.prepare_entry_url(f"{entry_url}&app_key=nao-persistir")
    with pytest.raises(ValueError, match="entre 1 e 50"):
        plugin.prepare_entry_url(f"{entry_url}&results_per_page=5000")
    with pytest.raises(ValueError, match="duplicados"):
        plugin.prepare_entry_url(f"{entry_url}&what=duplicado")


def test_adzuna_ignores_result_urls_outside_its_public_domain() -> None:
    browser = AdzunaJsonBrowser(
        {
            "results": [
                {
                    "id": "123",
                    "title": "Vaga falsa",
                    "company": {"display_name": "Exemplo"},
                    "location": {"display_name": "Brasil"},
                    "redirect_url": "https://example.com/captura",
                }
            ]
        }
    )

    jobs = AdzunaPlugin("app-id", "app-key").collect(
        browser,
        "https://api.adzuna.com/v1/api/jobs/br/search/1?what=teste",
    )

    assert jobs == []


def test_job_source_configuration_is_encrypted_and_validates_both_keys(tmp_path) -> None:
    vault = JobSourceConfigurationVault(tmp_path / "sources.enc")
    configuration = JobSourceConfiguration("app-id", "app-key")

    vault.save(configuration, "senha-local-segura")

    assert vault.load("senha-local-segura") == configuration
    assert b"app-key" not in (tmp_path / "sources.enc").read_bytes()
    with pytest.raises(ValueError, match="App ID"):
        JobSourceConfiguration("app-id", "")
