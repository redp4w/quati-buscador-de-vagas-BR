from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlencode

from quati.config.sources import load_source_catalog, portal_endpoint
from quati.core.browser.interface import Browser
from quati.domain import JobInput, JobRecord, is_pcd_eligible_text
from quati.domain.job import clean_text, normalized_key
from quati.location import (
    brazilian_state_name,
    canonical_brazilian_location,
    distance_km,
    has_explicit_brazilian_state,
    location_country,
    location_state_abbreviation,
    resolve_brazilian_city,
    split_brazilian_location,
)
from quati.plugins.base import JobPlugin
from quati.profile import WORK_MODES
from quati.storage import SQLiteJobRepository

from .collector import CollectionResult, JobCollector

SUPPORTED_DISCOVERY_SOURCES = (
    "adzuna",
    "empregos",
    "empregando_brasil",
    "solides",
    "gupy",
    "linkedin",
    "indeed",
    "vagas_com",
    "mindsight",
    "latojobs",
    "inhire",
    "greenhouse",
    "lever",
    "ashby",
    "smartrecruiters",
    "recruitee",
    "workable",
)
SUPPORTED_PARTIAL_SOURCES: tuple[str, ...] = ()
SUPPORTED_ASSISTED_SOURCES = (
    "jobbol",
    "programathor",
    "bne",
)
SUPPORTED_SEARCH_SOURCES = (
    SUPPORTED_DISCOVERY_SOURCES + SUPPORTED_PARTIAL_SOURCES + SUPPORTED_ASSISTED_SOURCES
)
_RECENCY_SECONDS = {"24h": "86400", "7d": "604800", "30d": "2592000"}
_RECENCY_DAYS = {"24h": "1", "7d": "7", "30d": "30"}
_LEVEL_CODES = {"Estágio": "1", "Júnior": "2", "Pleno": "3", "Sênior": "4"}
_LINKEDIN_WORK_MODE_CODES = {"Presencial": "1", "Remoto": "2", "Híbrido": "3"}
_REMOTE_RE = re.compile(r"\b(remoto|remote|home office|teletrabalho)\b")
_HYBRID_RE = re.compile(r"\b(hibrido|hybrid)\b")
_ONSITE_RE = re.compile(r"\b(presencial|on site|onsite)\b")
_REMOTE_FILTERED_SOURCES = frozenset({"gupy", "indeed", "programathor"})


@dataclass(frozen=True, slots=True)
class SearchRequest:
    keywords: str
    location: str = ""
    sources: tuple[str, ...] = SUPPORTED_DISCOVERY_SOURCES
    recency: str = "7d"
    remote_only: bool = False
    roles: tuple[str, ...] = ()
    levels: tuple[str, ...] = ()
    work_modes: tuple[str, ...] = ()
    max_distance_km: int = 80
    pcd_only: bool = False

    def __post_init__(self) -> None:
        keywords = clean_text(self.keywords, max_length=300)
        location = clean_text(self.location, max_length=200)
        if normalized_key(location) in {"brasil", "brazil"}:
            location = ""
        elif location:
            city, state = split_brazilian_location(location)
            if not state or (city and not has_explicit_brazilian_state(location)):
                raise ValueError("Selecione o estado e, se quiser, uma cidade válida.")
            location = canonical_brazilian_location(city, state)
        sources = tuple(
            dict.fromkeys(clean_text(item, max_length=20).lower() for item in self.sources)
        )
        roles = tuple(
            dict.fromkeys(role for item in self.roles if (role := clean_text(item, max_length=100)))
        )
        levels = tuple(dict.fromkeys(clean_text(item, max_length=20) for item in self.levels))
        work_modes = tuple(
            dict.fromkeys(clean_text(item, max_length=20) for item in self.work_modes)
        )
        if not keywords and not roles:
            raise ValueError("Informe ao menos um cargo ou palavra-chave.")
        if len(roles) > 5:
            raise ValueError("Use no máximo cinco cargos por busca.")
        if any(level not in _LEVEL_CODES for level in levels):
            raise ValueError("Nível profissional inválido.")
        if any(mode not in WORK_MODES for mode in work_modes):
            raise ValueError("Modalidade de trabalho inválida.")
        if not 1 <= self.max_distance_km <= 500:
            raise ValueError("O raio da busca deve estar entre 1 e 500 km.")
        if not sources or any(source not in SUPPORTED_SEARCH_SOURCES for source in sources):
            raise ValueError("Selecione ao menos uma fonte compatível.")
        if self.recency not in {"any", *_RECENCY_SECONDS}:
            raise ValueError("Período inválido.")
        object.__setattr__(self, "keywords", keywords)
        object.__setattr__(self, "location", location)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "roles", roles)
        object.__setattr__(self, "levels", levels)
        object.__setattr__(self, "work_modes", work_modes)

    def queries_for(self, source: str) -> tuple[str, ...]:
        if source == "jobbol" and self.roles:
            return self.roles
        if self.roles:
            return tuple(f"{role} {self.keywords}".strip()[:300] for role in self.roles)
        return (self.keywords,)


@dataclass(frozen=True, slots=True)
class SearchTarget:
    source: str
    url: str
    label: str = ""
    apply_text_filter: bool = False


@dataclass(frozen=True, slots=True)
class SourceDiscoveryResult:
    source: str
    url: str
    collection: CollectionResult | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    sources: tuple[SourceDiscoveryResult, ...]
    assisted: tuple[SearchTarget, ...] = ()

    @property
    def found(self) -> int:
        return sum(item.collection.found for item in self.sources if item.collection)

    @property
    def inserted(self) -> int:
        return sum(item.collection.inserted for item in self.sources if item.collection)

    @property
    def updated(self) -> int:
        return sum(item.collection.updated for item in self.sources if item.collection)

    @property
    def filtered(self) -> int:
        return sum(item.collection.filtered for item in self.sources if item.collection)


def build_search_targets(request: SearchRequest) -> tuple[SearchTarget, ...]:
    builders = {
        "adzuna": _adzuna_url,
        "empregos": _empregos_url,
        "empregando_brasil": _empregando_brasil_url,
        "solides": _solides_url,
        "gupy": _gupy_url,
        "linkedin": _linkedin_url,
        "indeed": _indeed_url,
        "vagas_com": _vagas_com_url,
        "mindsight": _mindsight_url,
        "latojobs": _latojobs_url,
    }
    return tuple(
        SearchTarget(source, builders[source](request, query))
        for source in request.sources
        if source in builders
        for query in request.queries_for(source)
    )


def build_assisted_search_targets(request: SearchRequest) -> tuple[SearchTarget, ...]:
    builders = {
        "jobbol": _jobbol_url,
        "programathor": _programathor_url,
        "bne": _bne_url,
    }
    generated = tuple(
        SearchTarget(source, builders[source](request, query), label=query)
        for source in request.sources
        if source in builders
        for query in request.queries_for(source)
    )
    company_pages = tuple(
        SearchTarget(company.source, company.url, label=company.name)
        for company in load_source_catalog().companies
        if company.enabled
        and company.source in request.sources
        and company.source not in SUPPORTED_DISCOVERY_SOURCES
    )
    return generated + company_pages


def build_company_targets(request: SearchRequest) -> tuple[SearchTarget, ...]:
    """Complementa a descoberta com páginas públicas declaradas no catálogo local."""
    return tuple(
        SearchTarget(
            company.source,
            company.url,
            label=company.name,
            apply_text_filter=True,
        )
        for company in load_source_catalog().companies
        if company.enabled
        and company.source in request.sources
        and company.source in SUPPORTED_DISCOVERY_SOURCES
    )


class MultiSourceDiscovery:
    def __init__(self, repository: SQLiteJobRepository, browser: Browser) -> None:
        self.repository = repository
        self.browser = browser

    def collect(self, request: SearchRequest, plugins: dict[str, JobPlugin]) -> DiscoveryResult:
        results: list[SourceDiscoveryResult] = []
        automatic_targets = (*build_search_targets(request), *build_company_targets(request))
        for target in automatic_targets:
            plugin = plugins.get(target.source)
            if plugin is None:
                results.append(
                    SourceDiscoveryResult(target.source, target.url, error="Fonte indisponível.")
                )
                continue
            try:
                collection = JobCollector(self.repository, self.browser).collect(
                    plugin,
                    target.url,
                    job_filter=lambda job, target=target: (
                        job_matches_search(job, request)
                        and (not target.apply_text_filter or job_matches_search_terms(job, request))
                    ),
                )
                results.append(SourceDiscoveryResult(target.source, target.url, collection))
            except (RuntimeError, ValueError):
                results.append(
                    SourceDiscoveryResult(
                        target.source,
                        target.url,
                        error="A fonte recusou ou não expôs resultados públicos.",
                    )
                )
        return DiscoveryResult(tuple(results), build_assisted_search_targets(request))


def _gupy_url(request: SearchRequest, query: str) -> str:
    parameters: list[tuple[str, str]] = [
        ("jobName", query),
        ("limit", "20"),
        ("offset", "0"),
    ]
    if request.location:
        state = _state_from_location(request.location)
        if state:
            parameters.append(("state", state))
        city, _ = split_brazilian_location(request.location)
        if city:
            parameters.append(("city", city))
    if request.remote_only:
        parameters.append(("workplaceType", "remote"))
    return f"{portal_endpoint('gupy', 'search_url')}?{urlencode(parameters)}"


def _mindsight_url(request: SearchRequest, query: str) -> str:
    del request
    parameters = [("search", query), ("page", "1"), ("page_size", "20")]
    return f"{portal_endpoint('mindsight', 'search_url')}?{urlencode(parameters)}"


def _latojobs_url(request: SearchRequest, query: str) -> str:
    parameters: list[tuple[str, str]] = [("country", "Brazil"), ("search", query)]
    if request.location:
        city, _ = split_brazilian_location(request.location)
        if city:
            parameters.append(("city", city))
    if request.remote_only:
        parameters.append(("workMode", "remote"))
    return f"{portal_endpoint('latojobs', 'search_url')}?{urlencode(parameters)}"


def _adzuna_url(request: SearchRequest, query: str) -> str:
    parameters: list[tuple[str, str]] = [
        ("results_per_page", "50"),
        ("what", query),
        ("sort_by", "date"),
    ]
    if request.location:
        parameters.append(("where", request.location))
    if request.recency != "any":
        parameters.append(("max_days_old", _RECENCY_DAYS[request.recency]))
    return f"{portal_endpoint('adzuna', 'search_url')}?{urlencode(parameters)}"


def _indeed_url(request: SearchRequest, query: str) -> str:
    parameters = [("q", query), ("sort", "date")]
    if request.location:
        parameters.append(("l", request.location))
    if request.recency != "any":
        parameters.append(("fromage", _RECENCY_DAYS[request.recency]))
    if request.remote_only:
        parameters.append(("remotejob", "1"))
    return f"{portal_endpoint('indeed', 'search_url')}?{urlencode(parameters)}"


def _jobbol_url(request: SearchRequest, query: str) -> str:
    role_slug = _slug(query)
    route = f"{portal_endpoint('jobbol', 'search_url')}{role_slug}"
    if request.location:
        route += f"/{_slug(request.location)}"
    return route


def _programathor_url(request: SearchRequest, query: str) -> str:
    parameters: list[tuple[str, str]] = []
    if request.remote_only:
        parameters.append(("remoto", "true"))
    if len(request.levels) == 1:
        parameters.append(("expertise", request.levels[0]))
    suffix = f"?{urlencode(parameters)}" if parameters else ""
    return f"{portal_endpoint('programathor', 'search_url')}-{_slug(query)}{suffix}"


def _vagas_com_url(request: SearchRequest, query: str) -> str:
    slug = _slug(query)
    return f"{portal_endpoint('vagas_com', 'search_url')}vagas-de-{slug}?{urlencode({'q': query})}"


def _empregos_url(request: SearchRequest, query: str) -> str:
    route = f"{portal_endpoint('empregos', 'search_url')}{_slug(query)}"
    if request.location and normalized_key(request.location) not in {"brasil", "brazil"}:
        route += f"-em-{_slug(request.location)}"
    return route


def _bne_url(request: SearchRequest, query: str) -> str:
    route = f"{portal_endpoint('bne', 'search_url')}vagas-de-emprego-para-{_slug(query)}"
    if request.location and normalized_key(request.location) not in {"brasil", "brazil"}:
        route += f"-em-{_slug(request.location)}"
    return route


def _solides_url(request: SearchRequest, query: str) -> str:
    del request
    parameters = [("title", query), ("take", "10"), ("page", "1")]
    return f"{portal_endpoint('solides', 'search_url')}?{urlencode(parameters)}"


def _empregando_brasil_url(request: SearchRequest, query: str) -> str:
    parameters: list[tuple[str, str]] = [("q", query)]
    if request.location and normalized_key(request.location) not in {"brasil", "brazil"}:
        parameters.append(("city", request.location))
    if request.recency != "any":
        parameters.append(("published", request.recency))
    if request.remote_only:
        parameters.append(("remote", "1"))
    if request.pcd_only:
        parameters.append(("diversity", "pcd"))
    return f"{portal_endpoint('empregando_brasil', 'search_url')}?{urlencode(parameters)}"


def _linkedin_url(request: SearchRequest, query: str) -> str:
    parameters: list[tuple[str, str]] = [
        ("keywords", query),
        ("location", request.location or "Brasil"),
        ("sortBy", "DD"),
    ]
    if request.recency != "any":
        parameters.append(("f_TPR", f"r{_RECENCY_SECONDS[request.recency]}"))
    if request.levels:
        parameters.append(("f_E", ",".join(_LEVEL_CODES[level] for level in request.levels)))
    selected_modes = ("Remoto",) if request.remote_only else request.work_modes
    if selected_modes:
        parameters.append(
            ("f_WT", ",".join(_LINKEDIN_WORK_MODE_CODES[mode] for mode in selected_modes))
        )
    return f"{portal_endpoint('linkedin', 'search_url')}?{urlencode(parameters)}"


def _slug(value: str) -> str:
    slug = normalized_key(value).replace(" ", "-")[:160].strip("-")
    if not slug:
        raise ValueError("A busca não gerou um endereço público válido.")
    return slug


def _state_from_location(location: str) -> str:
    return brazilian_state_name(location_state_abbreviation(location))


def job_matches_search(job: JobInput | JobRecord, request: SearchRequest) -> bool:
    """Aplica um escopo uniforme quando o portal ignora parte dos filtros."""
    if request.pcd_only and not job_is_pcd_eligible(job):
        return False
    if location_country(job.location) == "foreign":
        return False

    work_mode = _work_mode(job)
    selected_modes = set(request.work_modes)
    if request.remote_only:
        selected_modes = {"Remoto"}

    if not request.location:
        if not selected_modes:
            return True
        if (
            selected_modes == {"Remoto"}
            and work_mode == "Não informado"
            and job.source in _REMOTE_FILTERED_SOURCES
        ):
            return True
        return work_mode in selected_modes

    if normalized_key(request.location) in {"brasil", "brazil"}:
        return not selected_modes or work_mode in selected_modes

    remote_selected = "Remoto" in selected_modes
    local_modes = selected_modes - {"Remoto"}
    if work_mode == "Remoto":
        return remote_selected
    if (
        selected_modes == {"Remoto"}
        and work_mode == "Não informado"
        and request.remote_only
        and job.source in _REMOTE_FILTERED_SOURCES
    ):
        return True
    if selected_modes and not local_modes:
        return False
    if work_mode != "Não informado" and local_modes and work_mode not in local_modes:
        return False
    return _within_search_radius(job.location, request.location, request.max_distance_km)


def job_is_pcd_eligible(job: JobInput | JobRecord) -> bool:
    return is_pcd_eligible_text(job.title, job.description)


def job_matches_search_terms(job: JobInput | JobRecord, request: SearchRequest) -> bool:
    """Filtra páginas inteiras de empresas sem exigir coincidência literal perfeita."""
    title = normalized_key(job.title)
    text = normalized_key(f"{job.title} {job.description[:8_000]}")
    role_matches = not request.roles or any(
        _query_similarity(role, title) >= 0.6 or _query_similarity(role, text) >= 0.75
        for role in request.roles
    )
    keyword_matches = not request.keywords or _query_similarity(request.keywords, text) >= 0.6
    return role_matches and keyword_matches


def _query_similarity(query: str, text: str) -> float:
    ignored = {"a", "as", "da", "das", "de", "do", "dos", "e", "em", "para"}
    normalized_text = normalized_key(text)
    normalized_query = normalized_key(query)
    if normalized_query and normalized_query in normalized_text:
        return 1.0
    tokens = {
        token for token in normalized_key(query).split() if len(token) >= 2 and token not in ignored
    }
    if not tokens:
        return 0.0
    text_tokens = set(normalized_text.split())
    return len(tokens & text_tokens) / len(tokens)


def _work_mode(job: JobInput | JobRecord) -> str:
    text = normalized_key(f"{job.location} {job.title} {job.description[:2_000]}")
    if _REMOTE_RE.search(text):
        return "Remoto"
    if _HYBRID_RE.search(text):
        return "Híbrido"
    if _ONSITE_RE.search(text):
        return "Presencial"
    return "Não informado"


def _within_search_radius(job_location: str, search_location: str, radius_km: int) -> bool:
    origin = resolve_brazilian_city(search_location)
    destination = resolve_brazilian_city(job_location)
    if origin and destination:
        return distance_km(origin, destination) <= radius_km
    search_state = location_state_abbreviation(search_location)
    if search_state and not origin:
        return location_state_abbreviation(job_location) == search_state
    search_key = normalized_key(search_location)
    job_key = normalized_key(job_location)
    return bool(search_key and job_key and search_key in job_key)
