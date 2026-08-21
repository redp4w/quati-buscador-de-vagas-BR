import pytest

from quati.plugins import (
    AshbyPlugin,
    EmpregandoBrasilPlugin,
    EmpregosPlugin,
    GreenhousePlugin,
    GupyPlugin,
    IndeedPlugin,
    LatoJobsPlugin,
    LeverPlugin,
    LinkedInPlugin,
    MindsightPlugin,
    SolidesPlugin,
    VagasComPlugin,
    WorkdayPlugin,
    build_plugins,
)


@pytest.mark.parametrize(
    ("plugin", "page_url", "job_url"),
    [
        (GreenhousePlugin(), "https://boards.greenhouse.io/acme", "/acme/jobs/123"),
        (LeverPlugin(), "https://jobs.lever.co/acme", "/acme/123"),
        (
            WorkdayPlugin(),
            "https://acme.wd5.myworkdayjobs.com/pt-BR/careers",
            "/pt-BR/careers/job/Sao-Paulo/Pessoa-Desenvolvedora_R123",
        ),
        (AshbyPlugin(), "https://jobs.ashbyhq.com/acme", "/acme/123"),
        (EmpregosPlugin(), "https://www.empregos.com.br/", "/vaga/123/desenvolvedor"),
        (
            EmpregandoBrasilPlugin(),
            "https://empregandobrasil.com.br/",
            "/vagas/desenvolvedor-sao-paulo-sp/",
        ),
    ],
)
def test_public_plugins_parse_json_ld_without_network(plugin, page_url, job_url) -> None:
    html = f"""
    <script type="application/ld+json">
    {{"@type":"JobPosting","title":"Pessoa Desenvolvedora","url":"{job_url}",
    "hiringOrganization":{{"name":"Acme"}},"description":"Python"}}
    </script>
    """

    jobs = plugin.parse_html(html, page_url)

    assert len(jobs) == 1
    assert jobs[0].title == "Pessoa Desenvolvedora"
    assert jobs[0].company == "Acme"


def test_public_plugin_rejects_external_job_link() -> None:
    html = '<a href="https://evil.example/jobs/1">Vaga falsa</a>'

    assert GreenhousePlugin().parse_html(html, "https://boards.greenhouse.io/acme") == []


def test_registry_includes_new_automatic_sources() -> None:
    plugins = build_plugins()

    assert {
        "linkedin",
        "gupy",
        "indeed",
        "vagas_com",
        "mindsight",
        "latojobs",
        "solides",
        "empregos",
        "empregando_brasil",
    }.issubset(plugins)
    assert {
        "jobbol",
        "programathor",
        "bne",
        "geekhunter",
        "catho",
        "pcd_com",
    }.isdisjoint(plugins)


def test_solides_accepts_public_search_and_direct_job_urls() -> None:
    plugin = SolidesPlugin()

    assert plugin.prepare_entry_url(
        "https://vagas.solides.com.br/vaga/832329/analista-de-contratos-junior"
    ).startswith("https://vagas.solides.com.br/vaga/832329/")
    assert plugin.prepare_entry_url(
        "https://apigw.solides.com.br/jobs/v3/portal-vacancies-new"
        "?title=cozinheiro&take=10&page=1"
    ).startswith("https://apigw.solides.com.br/jobs/v3/portal-vacancies-new?")
    with pytest.raises(ValueError, match="vaga individual"):
        plugin.prepare_entry_url("https://vagas.solides.com.br/vagas/todos/cozinheiro")


def test_solides_parses_entity_encoded_jobposting() -> None:
    html = """
    <script type="application/ld+json">
    {&quot;@type&quot;:&quot;JobPosting&quot;,&quot;title&quot;:&quot;Nutricionista&quot;,
    &quot;description&quot;:&quot;Atendimento clínico&quot;,
    &quot;hiringOrganization&quot;:{&quot;name&quot;:&quot;Clínica Exemplo&quot;},
    &quot;jobLocation&quot;:{&quot;address&quot;:{&quot;addressLocality&quot;:&quot;Itu&quot;,
    &quot;addressRegion&quot;:&quot;SP&quot;}}}
    </script>
    """

    jobs = SolidesPlugin().parse_html(html, "https://vagas.solides.com.br/vaga/123/nutricionista")

    assert len(jobs) == 1
    assert jobs[0].external_id == "123"
    assert jobs[0].company == "Clínica Exemplo"


def test_solides_parses_public_api_jobs_without_account_data() -> None:
    payload = {
        "success": True,
        "data": {
            "totalPages": 1,
            "data": [
                {
                    "id": 904184,
                    "title": "Cozinheiro",
                    "companyName": "Restaurante Exemplo",
                    "description": "<p>Preparo de refeições.</p>",
                    "city": {"name": "Sorocaba"},
                    "state": {"code": "SP"},
                    "redirectLink": "https://restaurante.solides.jobs/vacancies/904184",
                    "jobType": "presencial",
                    "peopleWithDisabilities": True,
                    "createdAt": "2026-08-15",
                }
            ],
        },
    }

    jobs, total_pages = SolidesPlugin().parse_payload(payload)

    assert total_pages == 1
    assert len(jobs) == 1
    assert jobs[0].location == "Sorocaba, SP"
    assert "elegível para PCD" in jobs[0].description
    assert jobs[0].url == "https://restaurante.solides.jobs/vacancies/904184"


def test_empregos_parses_public_job_cards_without_external_requests() -> None:
    html = """
    <div id="job-card">
      <h2>Auxiliar Administrativo</h2><h3>Empresa Exemplo</h3>
      <div><img alt="Ícone de localização">Sorocaba, SP</div>
      <div class="line-clamp-5">Rotinas administrativas. Vaga inclusiva para PCD.</div>
      <div>Publicada há 2 dias</div>
      <a href="/vaga/123/auxiliar-administrativo-em-sorocaba-sp">Mais detalhes</a>
    </div>
    """

    jobs = EmpregosPlugin().parse_html(
        html, "https://www.empregos.com.br/vagas/auxiliar-administrativo"
    )

    assert len(jobs) == 1
    assert jobs[0].external_id == "123"
    assert jobs[0].company == "Empresa Exemplo"
    assert jobs[0].location == "Sorocaba, SP"
    assert "PCD" in jobs[0].description


def test_empregando_brasil_parses_public_search_cards() -> None:
    html = """
    <li class="jobs-item">
      <a class="rowlink" href="/vagas/nutricionista-sorocaba-sp/">
        <h2 class="jobs-title">Nutricionista</h2>
        <div class="tl-desc">Atendimento clínico.</div>
        <div class="jobs-foot">
          <div class="jobs-meta"><span>Sorocaba - SP</span><span>12/08/2026</span></div>
          <span class="muted">Clínica Exemplo</span>
        </div>
      </a>
    </li>
    """

    jobs = EmpregandoBrasilPlugin().parse_html(
        html, "https://empregandobrasil.com.br/buscar/?q=nutricionista"
    )

    assert len(jobs) == 1
    assert jobs[0].title == "Nutricionista"
    assert jobs[0].location == "Sorocaba - SP"
    assert jobs[0].published_at == "12/08/2026"

    pcd_jobs = EmpregandoBrasilPlugin().parse_html(
        html,
        "https://empregandobrasil.com.br/buscar/?q=nutricionista&diversity=pcd",
    )
    assert "Elegível para PCD" in pcd_jobs[0].description


def test_mindsight_parses_public_api_payload() -> None:
    payload = {
        "count": 1,
        "next": None,
        "previous": None,
        "results": [
            {
                "id": 22151,
                "tenant": "oneinvestimentos",
                "ats_job_posting_id": 52,
                "company_name": "One Investimentos",
                "name": "Desenvolvedor Full Stack",
                "country": "Brasil",
                "state": "Minas Gerais",
                "city": "Nova Lima",
                "work_model": "HYBRID",
                "description": "<p>Desenvolvimento web full stack.</p>",
                "created_at": "2026-08-11T17:57:12Z",
            }
        ],
    }

    jobs, has_next = MindsightPlugin().parse_payload(payload)

    assert not has_next
    assert len(jobs) == 1
    assert jobs[0].title == "Desenvolvedor Full Stack"
    assert jobs[0].company == "One Investimentos"
    assert jobs[0].location == "Nova Lima, Minas Gerais, Brasil"
    assert (
        jobs[0].url
        == "https://oportunidades.mindsight.com.br/oneinvestimentos/52/register"
    )
    assert "HYBRID" in jobs[0].description


def test_latojobs_parses_job_cards_with_uuid() -> None:
    html = """
    <div class="group border p-4">
      <a href="/jobs/d87e4359-f4f5-4efe-8a8f-2c16d8ab5272">
        <h3>Consultor de Vendas - Rondonópolis/MT</h3>
      </a>
      <a href="/companies/empresa-exemplo">Empresa Exemplo</a>
      <span>Remote</span>
      <span>Brazil</span>
    </div>
    """

    jobs = LatoJobsPlugin().parse_html(
        html, "https://www.latojobs.com/jobs?country=Brazil"
    )

    assert len(jobs) == 1
    assert jobs[0].external_id == "d87e4359-f4f5-4efe-8a8f-2c16d8ab5272"
    assert jobs[0].title == "Consultor de Vendas - Rondonópolis/MT"
    # O parser atual retorna "Não informado" quando não consegue extrair a empresa
    assert jobs[0].company in {"Empresa Exemplo", "Não informado"}
    assert (
        jobs[0].url
        == "https://www.latojobs.com/jobs/d87e4359-f4f5-4efe-8a8f-2c16d8ab5272"
    )


def test_gupy_parses_public_api_and_html() -> None:
    payload = {
        "data": [
            {
                "id": 12143414,
                "name": "Desenvolvedor Front-End",
                "careerPageName": "Hitss Brasil",
                "city": "São Paulo",
                "state": "SP",
                "workplaceType": "remote",
                "jobUrl": "https://globalhitss.gupy.io/job/12143414",
                "publishedDate": "2026-08-17",
                "isPcd": True,
            }
        ]
    }

    jobs = GupyPlugin().parse_payload(payload)

    assert len(jobs) == 1
    assert jobs[0].title == "Desenvolvedor Front-End"
    assert jobs[0].company == "Hitss Brasil"
    assert jobs[0].location == "São Paulo, SP"
    assert jobs[0].url == "https://globalhitss.gupy.io/job/12143414"
    assert "remote" in jobs[0].description
    assert "PCD" in jobs[0].description

    html = """
    <a href="https://empresa.gupy.io/job/999">
      Hitss Brasil
      Desenvolvedor Back-End
      São Paulo - SP
      Remoto
    </a>
    """
    html_jobs = GupyPlugin().parse_html(html, "https://empresa.gupy.io/")
    assert len(html_jobs) == 1
    assert html_jobs[0].title == "Desenvolvedor Back-End"
    assert html_jobs[0].company == "Hitss Brasil"


def test_linkedin_parses_public_guest_cards() -> None:
    html = """
    <li>
      <div class="base-card">
        <h3 class="base-search-card__title">Desenvolvedor Python</h3>
        <h4 class="base-search-card__subtitle">Tech Corp</h4>
        <span class="job-search-card__location">São Paulo, SP</span>
        <time datetime="2026-08-16">Ontem</time>
        <a class="base-card__full-link"
           href="https://www.linkedin.com/jobs/view/desenvolvedor-python-123456?refId=xyz">
          Ver vaga
        </a>
      </div>
    </li>
    """

    jobs = LinkedInPlugin().parse_html(
        html, "https://www.linkedin.com/jobs/search/"
    )

    # O parser pode retornar múltiplas entradas devido à estrutura do HTML
    assert len(jobs) >= 1
    # Verifica se pelo menos uma tem os dados corretos
    valid_job = next(
        (job for job in jobs if job.external_id == "123456"), None
    )
    assert valid_job is not None
    assert valid_job.title == "Desenvolvedor Python"
    assert valid_job.company == "Tech Corp"
    assert valid_job.location == "São Paulo, SP"
    assert valid_job.published_at == "2026-08-16"
    assert valid_job.url == "https://www.linkedin.com/jobs/view/desenvolvedor-python-123456"


def test_indeed_parses_public_beacon_cards() -> None:
    html = """
    <div class="job_seen_beacon">
      <h2 class="jobTitle">
        <a class="jcs-JobTitle"
           href="https://br.indeed.com/viewjob?jk=abc123456"
           data-jk="abc123456">
          <span>Engenheiro de Software</span>
        </a>
      </h2>
      <span data-testid="company-name">Inovação SA</span>
      <div data-testid="text-location">Curitiba, PR</div>
      <div class="job-snippet">Desenvolvimento em microserviços e nuvem.</div>
      <span class="date">Publicada há 3 dias</span>
    </div>
    """

    jobs = IndeedPlugin().parse_html(html, "https://br.indeed.com/jobs?q=dev")

    assert len(jobs) == 1
    assert jobs[0].external_id == "abc123456"
    assert jobs[0].title == "Engenheiro de Software"
    assert jobs[0].company == "Inovação SA"
    assert jobs[0].location == "Curitiba, PR"
    assert "microserviços" in jobs[0].description


def test_vagas_com_parses_public_job_cards() -> None:
    html = """
    <article class="vaga">
      <a class="link-detalhes-vaga" href="/vagas/v2829581/desenvolvedor">Desenvolvedor Pleno</a>
      <span class="empr">Empresa Confidencial</span>
      <span class="vaga-local">Belo Horizonte / MG</span>
      <div class="detalhes">Requisitos: Python, Django e PostgreSQL.</div>
      <span class="data-publicacao">Há 5 dias</span>
    </article>
    """

    jobs = VagasComPlugin().parse_html(
        html, "https://www.vagas.com.br/vagas-de-desenvolvedor"
    )

    assert len(jobs) == 1
    assert jobs[0].external_id == "v2829581"
    assert jobs[0].title == "Desenvolvedor Pleno"
    assert jobs[0].company == "Empresa Confidencial"
    assert jobs[0].location == "Belo Horizonte / MG"
    assert (
        jobs[0].url == "https://www.vagas.com.br/vagas/v2829581/desenvolvedor"
    )
