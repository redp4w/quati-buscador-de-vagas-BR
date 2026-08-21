from __future__ import annotations

from collections.abc import Collection
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from quati.core.browser.interface import Browser
from quati.core.browser.url_safety import validate_public_https_url
from quati.domain import JobInput

from .base import JobPlugin

_SEARCH_HOST = "api.adzuna.com"
_RESULT_HOSTS = ("adzuna.com.br",)
_ALLOWED_QUERY_PARAMETERS = frozenset(
    {
        "results_per_page",
        "what",
        "where",
        "sort_by",
        "max_days_old",
        "full_time",
        "part_time",
        "permanent",
        "contract",
    }
)


class AdzunaPlugin(JobPlugin):
    """Consulta a API oficial da Adzuna sem persistir as credenciais na busca."""

    name = "adzuna"
    display_name = "Adzuna — API oficial"
    allowed_hosts: Collection[str] = (_SEARCH_HOST, *_RESULT_HOSTS)
    experimental = False
    _max_jobs = 50

    def __init__(self, app_id: str = "", app_key: str = "") -> None:
        self._app_id = self._validate_secret(app_id, "App ID")
        self._app_key = self._validate_secret(app_key, "app key")
        if bool(self._app_id) != bool(self._app_key):
            raise ValueError("Informe o App ID e a app key da Adzuna.")

    @property
    def configured(self) -> bool:
        return bool(self._app_id and self._app_key)

    def prepare_entry_url(self, entry_url: str) -> str:
        safe_url = validate_public_https_url(entry_url, (_SEARCH_HOST,))
        parsed = urlsplit(safe_url)
        if parsed.path != "/v1/api/jobs/br/search/1":
            raise ValueError("Use a pesquisa brasileira da API oficial da Adzuna.")
        raw_parameters = parse_qsl(parsed.query, keep_blank_values=False)
        if any(name not in _ALLOWED_QUERY_PARAMETERS for name, _ in raw_parameters):
            raise ValueError("A pesquisa da Adzuna contém parâmetros não permitidos.")
        parameters = dict(raw_parameters)
        if len(parameters) != len(raw_parameters):
            raise ValueError("A pesquisa da Adzuna contém filtros duplicados.")
        self._validate_query_parameters(parameters)
        return urlunsplit(parsed._replace(query=urlencode(parameters)))

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        if not self.configured:
            raise ValueError("Configure o App ID e a app key da Adzuna antes de pesquisar.")
        safe_entry_url = self.prepare_entry_url(entry_url)
        parsed = urlsplit(safe_entry_url)
        parameters = parse_qsl(parsed.query, keep_blank_values=False)
        parameters.extend((("app_id", self._app_id), ("app_key", self._app_key)))
        request_url = urlunsplit(parsed._replace(query=urlencode(parameters)))
        payload = browser.fetch_json(request_url, allowed_hosts=(_SEARCH_HOST,))
        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise ValueError("A Adzuna retornou uma resposta inesperada.")
        jobs: list[JobInput] = []
        for item in payload["results"][: self._max_jobs]:
            job = self._job_from_item(item)
            if job is not None:
                jobs.append(job)
        return jobs

    @staticmethod
    def _job_from_item(item: object) -> JobInput | None:
        if not isinstance(item, dict):
            return None
        company = item.get("company") or {}
        location = item.get("location") or {}
        if not isinstance(company, dict) or not isinstance(location, dict):
            return None
        try:
            result_url = validate_public_https_url(
                str(item.get("redirect_url", "")),
                _RESULT_HOSTS,
            )
            return JobInput(
                source="adzuna",
                external_id=str(item.get("id", "")),
                title=str(item.get("title", "")),
                company=str(company.get("display_name") or "Não informado"),
                location=str(location.get("display_name", "")),
                url=result_url,
                description=str(item.get("description", "")),
                published_at=str(item.get("created", "")),
            )
        except ValueError:
            return None

    @staticmethod
    def _validate_secret(value: str, label: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{label} da Adzuna inválido.")
        secret = value.strip()
        if len(secret) > 512 or any(
            ord(character) < 33 or ord(character) == 127 for character in secret
        ):
            raise ValueError(f"{label} da Adzuna inválido.")
        return secret

    @staticmethod
    def _validate_query_parameters(parameters: dict[str, str]) -> None:
        for name in ("what", "where"):
            value = parameters.get(name, "")
            limit = 300 if name == "what" else 200
            if value and len(value) > limit:
                raise ValueError("A pesquisa da Adzuna excedeu o limite de texto.")
        results = parameters.get("results_per_page", "20")
        days = parameters.get("max_days_old", "30")
        if not results.isdigit() or not 1 <= int(results) <= 50:
            raise ValueError("A pesquisa da Adzuna deve pedir entre 1 e 50 vagas.")
        if not days.isdigit() or not 1 <= int(days) <= 365:
            raise ValueError("O período da pesquisa da Adzuna é inválido.")
        if parameters.get("sort_by", "relevance") not in {"date", "relevance", "salary"}:
            raise ValueError("A ordenação da Adzuna é inválida.")
        for name in ("full_time", "part_time", "permanent", "contract"):
            if name in parameters and parameters[name] not in {"0", "1"}:
                raise ValueError("Um filtro da Adzuna é inválido.")
