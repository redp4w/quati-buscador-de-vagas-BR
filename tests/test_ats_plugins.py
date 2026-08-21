from collections.abc import Collection, Mapping

from quati.plugins import (
    AshbyAPIPlugin,
    GreenhouseAPIPlugin,
    LeverAPIPlugin,
    RecruiteeAPIPlugin,
    SmartRecruitersAPIPlugin,
    WorkablePublicPlugin,
)


class JSONBrowser:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.urls: list[str] = []

    def fetch_json(
        self,
        url: str,
        *,
        allowed_hosts: Collection[str],
        headers: Mapping[str, str] | None = None,
    ) -> object:
        del allowed_hosts, headers
        self.urls.append(url)
        return self.payload


def test_greenhouse_uses_public_board_api_and_catalog_company_name() -> None:
    browser = JSONBrowser(
        {
            "jobs": [
                {
                    "id": 123,
                    "title": "Analista de segurança júnior",
                    "location": {"name": "São Paulo, SP"},
                    "absolute_url": "https://job-boards.greenhouse.io/ifoodcarreiras/jobs/123",
                    "content": "<p>Monitoramento e resposta a incidentes.</p>",
                    "updated_at": "2026-08-15T10:00:00Z",
                }
            ]
        }
    )

    jobs = GreenhouseAPIPlugin().collect(
        browser, "https://job-boards.greenhouse.io/ifoodcarreiras"
    )

    assert browser.urls == [
        "https://boards-api.greenhouse.io/v1/boards/ifoodcarreiras/jobs?content=true"
    ]
    assert jobs[0].company == "iFood"
    assert jobs[0].title == "Analista de segurança júnior"


def test_lever_uses_bounded_public_postings_api() -> None:
    browser = JSONBrowser(
        [
            {
                "id": "abc",
                "text": "Pessoa desenvolvedora júnior",
                "categories": {"location": "Campinas, SP"},
                "descriptionPlain": "Python e APIs.",
                "hostedUrl": "https://jobs.lever.co/ciandt/abc",
                "workplaceType": "hybrid",
            }
        ]
    )

    jobs = LeverAPIPlugin().collect(browser, "https://jobs.lever.co/ciandt")

    assert len(browser.urls) == 1
    assert "limit=100" in browser.urls[0]
    assert jobs[0].company == "CI&T"
    assert "hybrid" in jobs[0].description


def test_ashby_reads_only_published_job_board_response() -> None:
    browser = JSONBrowser(
        {
            "jobs": [
                {
                    "title": "Nutricionista",
                    "location": "Sorocaba, SP",
                    "descriptionPlain": "Atendimento clínico.",
                    "publishedAt": "2026-08-10",
                    "jobUrl": "https://jobs.ashbyhq.com/acme/abc",
                    "workplaceType": "OnSite",
                }
            ]
        }
    )

    jobs = AshbyAPIPlugin().collect(browser, "https://jobs.ashbyhq.com/acme")

    assert jobs[0].title == "Nutricionista"
    assert jobs[0].location == "Sorocaba, SP"


def test_smartrecruiters_builds_human_job_url() -> None:
    browser = JSONBrowser(
        {
            "totalFound": 1,
            "content": [
                {
                    "id": "7440001",
                    "name": "Engenheiro de processos",
                    "company": {"name": "Bosch"},
                    "location": {
                        "city": "Campinas",
                        "region": "SP",
                        "country": "BR",
                        "remote": False,
                    },
                    "releasedDate": "2026-08-15",
                    "experienceLevel": {"label": "Júnior"},
                }
            ],
        }
    )

    jobs = SmartRecruitersAPIPlugin().collect(
        browser, "https://careers.smartrecruiters.com/BoschGroup/brazil"
    )

    assert jobs[0].url.startswith("https://jobs.smartrecruiters.com/BoschGroup/7440001-")
    assert jobs[0].location == "Campinas, SP, BR"


def test_recruitee_uses_tenant_careers_api() -> None:
    browser = JSONBrowser(
        {
            "offers": [
                {
                    "id": 7,
                    "title": "Assistente administrativo",
                    "careers_url": "https://acme.recruitee.com/o/assistente",
                    "location": "Itu, SP",
                    "description": "Rotinas administrativas.",
                }
            ]
        }
    )

    jobs = RecruiteeAPIPlugin().collect(browser, "https://acme.recruitee.com/")

    assert browser.urls == ["https://acme.recruitee.com/api/offers/"]
    assert jobs[0].company == "Acme"


def test_workable_uses_documented_public_account_endpoint() -> None:
    browser = JSONBrowser(
        {
            "jobs": [
                {
                    "id": "x1",
                    "title": "Cozinheiro",
                    "url": "https://acme.workable.com/jobs/x1",
                    "description": "Cozinha industrial.",
                    "location": {
                        "location_str": "Sorocaba, SP",
                        "workplace_type": "on_site",
                    },
                }
            ]
        }
    )

    jobs = WorkablePublicPlugin().collect(browser, "https://acme.workable.com/")

    assert browser.urls == ["https://www.workable.com/api/accounts/acme?details=true"]
    assert jobs[0].title == "Cozinheiro"
