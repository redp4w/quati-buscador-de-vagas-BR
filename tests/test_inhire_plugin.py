import pytest

from quati.plugins import InHirePlugin


class PublicJsonBrowser:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.calls: list[tuple[str, tuple[str, ...], dict[str, str]]] = []

    def fetch_json(
        self,
        url: str,
        *,
        allowed_hosts: tuple[str, ...],
        headers: dict[str, str] | None = None,
    ) -> object:
        self.calls.append((url, allowed_hosts, headers or {}))
        return self.payload


def test_inhire_reads_only_published_jobs_from_public_tenant() -> None:
    browser = PublicJsonBrowser(
        {
            "tenantName": "Empresa Exemplo",
            "jobsPage": [
                {
                    "jobId": "35af766f-c9f5-47b0-a681-1a6493744e04",
                    "displayName": "Cozinheiro",
                    "status": "published",
                    "workplaceType": "On-site",
                    "location": "Sorocaba, SP, BR",
                },
                {
                    "jobId": "d7f19b8f-56f0-4836-90a1-3da6c7e42cd7",
                    "displayName": "Vaga interna",
                    "status": "draft",
                },
            ],
        }
    )

    jobs = InHirePlugin().collect(browser, "https://empresa.inhire.app/vagas")

    assert len(jobs) == 1
    assert jobs[0].title == "Cozinheiro"
    assert jobs[0].company == "Empresa Exemplo"
    assert jobs[0].location == "Sorocaba, SP, BR"
    assert jobs[0].description == "Modalidade: Presencial."
    assert jobs[0].url.endswith("/vagas/35af766f-c9f5-47b0-a681-1a6493744e04")
    assert browser.calls == [
        (
            "https://api.inhire.app/job-posts/public/pages",
            ("inhire.app",),
            {
                "accept": "application/json",
                "x-inhire-client": "web-inhire",
                "x-tenant": "empresa",
            },
        )
    ]


@pytest.mark.parametrize(
    "url",
    (
        "https://api.inhire.app/job-posts/public/pages",
        "https://carreira.inhire.app/vagas",
        "https://sub.empresa.inhire.app/vagas",
        "https://example.com/vagas",
    ),
)
def test_inhire_rejects_non_tenant_entry_urls(url: str) -> None:
    with pytest.raises(ValueError):
        InHirePlugin().collect(PublicJsonBrowser({}), url)
