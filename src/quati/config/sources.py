from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import yaml

from quati.core.browser.url_safety import validate_public_https_url

_MAX_CONFIG_BYTES = 128 * 1024
_MAX_COMPANIES = 50
_ID_RE = re.compile(r"^[a-z0-9_]{1,40}$")
_PORTAL_HOSTS: dict[str, tuple[str, ...]] = {
    "gupy": ("gupy.io", "portal.gupy.io", "employability-portal.gupy.io"),
    "linkedin": ("linkedin.com", "www.linkedin.com"),
    "indeed": ("indeed.com", "br.indeed.com", "www.indeed.com"),
    "mindsight": (
        "mindsight.com.br",
        "central.mindsight.com.br",
        "oportunidades.mindsight.com.br",
    ),
    "latojobs": ("latojobs.com", "www.latojobs.com"),
    "geekhunter": ("geekhunter.com",),
    "jobbol": ("jobbol.com.br",),
    "programathor": ("programathor.com.br",),
    "vagas_com": ("vagas.com.br", "www.vagas.com.br"),
    "empregos": ("empregos.com.br",),
    "bne": ("bne.com.br",),
    "empregando_brasil": ("empregandobrasil.com.br",),
    "solides": ("solides.com.br",),
    "burh": ("burh.com.br",),
    "99jobs": ("99jobs.com",),
    "trabalha_brasil": ("trabalhabrasil.com.br",),
    "adzuna": ("adzuna.com.br", "adzuna.com"),
    "pcd_com": ("pcd.com.br",),
    "catho": ("catho.com.br",),
    "bebee": ("bebee.com",),
    "trampos": ("trampos.co",),
    "infojobs": ("infojobs.com.br",),
    "glassdoor": ("glassdoor.com.br",),
    "inhire": ("inhire.com.br",),
    "greenhouse": ("greenhouse.io",),
    "lever": ("lever.co",),
    "ashby": ("ashbyhq.com",),
    "smartrecruiters": ("smartrecruiters.com",),
    "recruitee": ("recruitee.com",),
    "workable": ("workable.com",),
    "workday": ("myworkdayjobs.com",),
    "personio": ("personio.com",),
    "vagas_remotas": ("vagasremotas.net",),
    "revelo": ("revelo.com.br",),
    "apinfo": ("apinfo.com",),
    "ciee": ("ciee.org.br",),
    "nube": ("nube.com.br",),
    "iel": ("portaldaindustria.com.br",),
    "jooble": ("jooble.org",),
    "remotar": ("remotar.com.br",),
    "quickin": ("quickin.io",),
    "abler": ("abler.com.br",),
    "pandape": ("pandape.com.br",),
    "recrutei": ("recrutei.com.br",),
    "bamboohr": ("bamboohr.com",),
    "sap_successfactors": ("sap.com",),
    "oracle_recruiting": ("oracle.com",),
}
_COMPANY_SOURCE_HOSTS: dict[str, tuple[str, ...]] = {
    "gupy": ("gupy.io",),
    "inhire": ("inhire.app",),
    "greenhouse": ("greenhouse.io",),
    "lever": ("lever.co",),
    "ashby": ("ashbyhq.com",),
    "smartrecruiters": ("smartrecruiters.com",),
    "recruitee": ("recruitee.com",),
    "workable": ("workable.com",),
}


class SourceCatalogError(ValueError):
    """Configuração pública de fontes inválida."""


@dataclass(frozen=True, slots=True)
class PortalEndpoints:
    access_url: str
    search_url: str = ""


@dataclass(frozen=True, slots=True)
class CompanySource:
    id: str
    name: str
    source: str
    url: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class SourceCatalog:
    portals: MappingProxyType[str, PortalEndpoints]
    companies: tuple[CompanySource, ...]
    path: Path


def _default_catalog_path() -> Path:
    configured = os.environ.get("QUATI_SOURCES_FILE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()

    project_root = Path(__file__).resolve().parents[3]
    candidates = (
        Path.cwd() / "config" / "job_sources.yml",
        project_root / "config" / "job_sources.yml",
        Path(__file__).with_name("job_sources.yml"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise SourceCatalogError("O arquivo config/job_sources.yml não foi encontrado.")


def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise SourceCatalogError("Não foi possível abrir a configuração de fontes.") from exc
    if size <= 0 or size > _MAX_CONFIG_BYTES:
        raise SourceCatalogError("A configuração de fontes está vazia ou excede 128 KB.")
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise SourceCatalogError("A configuração de fontes não é um YAML válido.") from exc
    if not isinstance(document, dict):
        raise SourceCatalogError("A configuração de fontes deve ser um objeto YAML.")
    return document


def _clean_id(value: object, *, field: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _ID_RE.fullmatch(normalized):
        raise SourceCatalogError(f"{field} inválido na configuração de fontes.")
    return normalized


def _public_url(value: object, *, hosts: tuple[str, ...], description: str) -> str:
    try:
        return validate_public_https_url(str(value or "").strip(), hosts)
    except ValueError as exc:
        raise SourceCatalogError(f"URL inválida para {description}.") from exc


def _environment_url(prefix: str, fallback: object) -> object:
    value = os.environ.get(prefix, "").strip()
    return value or fallback


@lru_cache(maxsize=1)
def load_source_catalog() -> SourceCatalog:
    path = _default_catalog_path()
    document = _read_yaml(path)
    if document.get("version") != 1:
        raise SourceCatalogError("Versão incompatível em config/job_sources.yml.")

    raw_portals = document.get("portals")
    if not isinstance(raw_portals, dict):
        raise SourceCatalogError("A seção portals deve ser um objeto YAML.")
    portals: dict[str, PortalEndpoints] = {}
    for raw_id, raw_config in raw_portals.items():
        portal_id = _clean_id(raw_id, field="Portal")
        hosts = _PORTAL_HOSTS.get(portal_id)
        if hosts is None or not isinstance(raw_config, dict):
            raise SourceCatalogError(f"Portal não reconhecido: {portal_id}.")
        env_prefix = f"QUATI_SOURCE_{portal_id.upper()}"
        access_url = _public_url(
            _environment_url(f"{env_prefix}_ACCESS_URL", raw_config.get("access_url")),
            hosts=hosts,
            description=portal_id,
        )
        raw_search_url = _environment_url(
            f"{env_prefix}_SEARCH_URL", raw_config.get("search_url", "")
        )
        search_url = (
            _public_url(raw_search_url, hosts=hosts, description=f"busca {portal_id}")
            if raw_search_url
            else ""
        )
        portals[portal_id] = PortalEndpoints(access_url, search_url)

    raw_companies = document.get("companies", [])
    if not isinstance(raw_companies, list):
        raise SourceCatalogError("A seção companies deve ser uma lista YAML.")
    if len(raw_companies) > _MAX_COMPANIES:
        raise SourceCatalogError("A configuração aceita no máximo 50 empresas.")
    companies: list[CompanySource] = []
    seen_company_ids: set[str] = set()
    for raw_company in raw_companies:
        if not isinstance(raw_company, dict):
            raise SourceCatalogError("Cada empresa deve ser um objeto YAML.")
        company_id = _clean_id(raw_company.get("id"), field="Empresa")
        if company_id in seen_company_ids:
            raise SourceCatalogError(f"Empresa duplicada: {company_id}.")
        seen_company_ids.add(company_id)
        source = _clean_id(raw_company.get("source"), field="Fonte da empresa")
        hosts = _COMPANY_SOURCE_HOSTS.get(source)
        if hosts is None:
            raise SourceCatalogError(f"Fonte de empresa não reconhecida: {source}.")
        name = str(raw_company.get("name") or "").strip()
        if not name or len(name) > 100:
            raise SourceCatalogError(f"Nome inválido para a empresa {company_id}.")
        enabled = raw_company.get("enabled", True)
        if not isinstance(enabled, bool):
            raise SourceCatalogError(f"enabled deve ser booleano para {company_id}.")
        raw_url = _environment_url(
            f"QUATI_COMPANY_{company_id.upper()}_URL", raw_company.get("url")
        )
        companies.append(
            CompanySource(
                id=company_id,
                name=name,
                source=source,
                url=_public_url(raw_url, hosts=hosts, description=name),
                enabled=enabled,
            )
        )

    return SourceCatalog(MappingProxyType(portals), tuple(companies), path)


def portal_endpoint(portal_id: str, field: str) -> str:
    portal = load_source_catalog().portals.get(portal_id)
    if portal is None:
        raise SourceCatalogError(f"Portal ausente na configuração: {portal_id}.")
    if field not in {"access_url", "search_url"}:
        raise SourceCatalogError("Campo de URL desconhecido.")
    value = getattr(portal, field)
    if not value:
        raise SourceCatalogError(f"O portal {portal_id} não possui {field} configurado.")
    return value
