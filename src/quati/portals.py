from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from quati.config.sources import portal_endpoint

SearchMode = Literal["automatic", "partial", "assisted", "external"]
SourceKind = Literal["portal", "ats"]


@dataclass(frozen=True, slots=True)
class JobPortal:
    id: str
    label: str
    access_url: str
    search_mode: SearchMode
    note: str
    kind: SourceKind = "portal"

    @property
    def automatic_search(self) -> bool:
        return self.search_mode == "automatic"

    @property
    def assisted_search(self) -> bool:
        return self.search_mode == "assisted"

    @property
    def partial_search(self) -> bool:
        return self.search_mode == "partial"


JOB_PORTALS = (
    JobPortal(
        "gupy",
        "Gupy",
        portal_endpoint("gupy", "access_url"),
        "automatic",
        "O app pesquisa vagas públicas e quadros de empresas diretamente na Gupy.",
    ),
    JobPortal(
        "linkedin",
        "LinkedIn",
        portal_endpoint("linkedin", "access_url"),
        "automatic",
        "Consulta anúncios públicos de emprego do LinkedIn sem exigir login.",
    ),
    JobPortal(
        "indeed",
        "Indeed",
        portal_endpoint("indeed", "access_url"),
        "automatic",
        "Consulta anúncios públicos de vagas brasileiras no Indeed.",
    ),
    JobPortal(
        "mindsight",
        "Mindsight",
        portal_endpoint("mindsight", "access_url"),
        "automatic",
        "Consulta vagas públicas e posições de empresas parceiras na Mindsight.",
    ),
    JobPortal(
        "latojobs",
        "Lato Jobs",
        portal_endpoint("latojobs", "access_url"),
        "automatic",
        "Consulta vagas de tecnologia no Brasil pela plataforma Lato Jobs.",
    ),
    JobPortal(
        "geekhunter",
        "GeekHunter",
        portal_endpoint("geekhunter", "access_url"),
        "external",
        "Pesquise e faça a candidatura diretamente no navegador.",
    ),
    JobPortal(
        "jobbol",
        "Jobbol",
        portal_endpoint("jobbol", "access_url"),
        "assisted",
        "O app gera o endereço da busca; o portal recusa a coleta automática.",
    ),
    JobPortal(
        "programathor",
        "Programathor",
        portal_endpoint("programathor", "access_url"),
        "assisted",
        "O app prepara cargo e filtros; os resultados permanecem no portal.",
    ),
    JobPortal(
        "vagas_com",
        "Vagas.com",
        portal_endpoint("vagas_com", "access_url"),
        "automatic",
        "Consulta vagas públicas abertas no portal Vagas.com.",
    ),
    JobPortal(
        "empregos",
        "Empregos.com.br",
        portal_endpoint("empregos", "access_url"),
        "automatic",
        "O app consulta vagas públicas sem entrar na área de candidatos.",
    ),
    JobPortal(
        "bne",
        "BNE",
        portal_endpoint("bne", "access_url"),
        "assisted",
        "O app prepara o endereço da pesquisa sem coletar dados do portal.",
    ),
    JobPortal(
        "empregando_brasil",
        "Empregando Brasil",
        portal_endpoint("empregando_brasil", "access_url"),
        "automatic",
        "O app pesquisa resultados públicos sem acessar dados de contas.",
    ),
    JobPortal(
        "solides",
        "Sólides Vagas",
        portal_endpoint("solides", "access_url"),
        "automatic",
        "Consulta o endpoint público usado pelo portal e mantém a candidatura no site original.",
    ),
    JobPortal(
        "burh",
        "BURH",
        portal_endpoint("burh", "access_url"),
        "external",
        "A pesquisa abre no navegador.",
    ),
    JobPortal(
        "99jobs",
        "99jobs",
        portal_endpoint("99jobs", "access_url"),
        "external",
        "A pesquisa abre no navegador.",
    ),
    JobPortal(
        "trabalha_brasil",
        "Trabalha Brasil",
        portal_endpoint("trabalha_brasil", "access_url"),
        "external",
        "A pesquisa abre no navegador.",
    ),
    JobPortal(
        "adzuna",
        "Adzuna",
        portal_endpoint("adzuna", "access_url"),
        "automatic",
        "A API oficial coleta vagas públicas quando as chaves locais estão configuradas.",
    ),
    JobPortal(
        "pcd_com",
        "PCD.com.br",
        portal_endpoint("pcd_com", "access_url"),
        "external",
        "Portal especializado em vagas para pessoas com deficiência.",
    ),
    JobPortal(
        "catho",
        "Catho",
        portal_endpoint("catho", "access_url"),
        "external",
        "A pesquisa abre no navegador.",
    ),
    JobPortal(
        "bebee",
        "beBee",
        portal_endpoint("bebee", "access_url"),
        "external",
        "A pesquisa abre no navegador.",
    ),
    JobPortal(
        "trampos",
        "trampos",
        portal_endpoint("trampos", "access_url"),
        "external",
        "A pesquisa abre no navegador.",
    ),
    JobPortal(
        "infojobs",
        "Infojobs",
        portal_endpoint("infojobs", "access_url"),
        "external",
        "A pesquisa abre no navegador.",
    ),
    JobPortal(
        "glassdoor",
        "Glassdoor",
        portal_endpoint("glassdoor", "access_url"),
        "external",
        "A pesquisa abre no navegador porque o portal restringe a coleta automática.",
    ),
    JobPortal(
        "inhire",
        "InHire",
        portal_endpoint("inhire", "access_url"),
        "automatic",
        "O app consulta somente páginas públicas de empresas configuradas.",
    ),
    JobPortal(
        "greenhouse",
        "Greenhouse",
        portal_endpoint("greenhouse", "access_url"),
        "automatic",
        "Consulta a API pública oficial de empresas brasileiras catalogadas.",
        "ats",
    ),
    JobPortal(
        "lever",
        "Lever",
        portal_endpoint("lever", "access_url"),
        "automatic",
        "Consulta vagas publicadas por empresas catalogadas na API oficial.",
        "ats",
    ),
    JobPortal(
        "ashby",
        "Ashby",
        portal_endpoint("ashby", "access_url"),
        "automatic",
        "A API pública pode coletar empresas adicionadas ao catálogo.",
        "ats",
    ),
    JobPortal(
        "smartrecruiters",
        "SmartRecruiters",
        portal_endpoint("smartrecruiters", "access_url"),
        "automatic",
        "Consulta anúncios ativos de empresas brasileiras catalogadas.",
        "ats",
    ),
    JobPortal(
        "recruitee",
        "Recruitee",
        portal_endpoint("recruitee", "access_url"),
        "automatic",
        "A Careers Site API pública pode coletar empresas adicionadas ao catálogo.",
        "ats",
    ),
    JobPortal(
        "workable",
        "Workable",
        portal_endpoint("workable", "access_url"),
        "automatic",
        "O endpoint público consulta empresas adicionadas ao catálogo.",
        "ats",
    ),
    JobPortal(
        "workday",
        "Workday",
        portal_endpoint("workday", "access_url"),
        "external",
        "Aceita uma página pública específica no painel por URL.",
        "ats",
    ),
    JobPortal(
        "personio",
        "Personio",
        portal_endpoint("personio", "access_url"),
        "external",
        "O feed depende de ativação pela empresa e ainda não entra na busca principal.",
        "ats",
    ),
    JobPortal(
        "vagas_remotas",
        "Vagas Remotas",
        portal_endpoint("vagas_remotas", "access_url"),
        "external",
        "Abre o portal; os termos não autorizam coleta automática.",
    ),
    JobPortal(
        "revelo",
        "Revelo",
        portal_endpoint("revelo", "access_url"),
        "external",
        "Plataforma baseada em perfil e conta; permanece no navegador.",
    ),
    JobPortal(
        "apinfo",
        "APInfo",
        portal_endpoint("apinfo", "access_url"),
        "external",
        "Portal de tecnologia catalogado para revisão de integração.",
    ),
    JobPortal(
        "ciee",
        "CIEE",
        portal_endpoint("ciee", "access_url"),
        "external",
        "Oportunidades de estágio e aprendizagem continuam no portal.",
    ),
    JobPortal(
        "nube",
        "Nube",
        portal_endpoint("nube", "access_url"),
        "external",
        "Oportunidades de estágio permanecem no navegador.",
    ),
    JobPortal(
        "iel",
        "IEL",
        portal_endpoint("iel", "access_url"),
        "external",
        "A oferta varia por regional e ainda não possui conector comum.",
    ),
    JobPortal(
        "jooble",
        "Jooble",
        portal_endpoint("jooble", "access_url"),
        "external",
        "Agregador catalogado; uma API própria exige acordo separado.",
    ),
    JobPortal(
        "remotar",
        "Remotar",
        portal_endpoint("remotar", "access_url"),
        "external",
        "Portal remoto catalogado para revisão de integração.",
    ),
    JobPortal(
        "quickin",
        "Quickin",
        portal_endpoint("quickin", "access_url"),
        "external",
        "ATS catalogado; depende da página pública de cada empresa.",
        "ats",
    ),
    JobPortal(
        "abler",
        "Abler",
        portal_endpoint("abler", "access_url"),
        "external",
        "ATS catalogado; depende da página pública de cada empresa.",
        "ats",
    ),
    JobPortal(
        "pandape",
        "Pandapé",
        portal_endpoint("pandape", "access_url"),
        "external",
        "ATS catalogado; a integração pública ainda não foi confirmada.",
        "ats",
    ),
    JobPortal(
        "recrutei",
        "Recrutei",
        portal_endpoint("recrutei", "access_url"),
        "external",
        "ATS catalogado; depende da página pública de cada empresa.",
        "ats",
    ),
    JobPortal(
        "bamboohr",
        "BambooHR",
        portal_endpoint("bamboohr", "access_url"),
        "external",
        "ATS catalogado; o conector público ainda não foi validado.",
        "ats",
    ),
    JobPortal(
        "sap_successfactors",
        "SAP SuccessFactors",
        portal_endpoint("sap_successfactors", "access_url"),
        "external",
        "ATS empresarial com páginas variadas por tenant.",
        "ats",
    ),
    JobPortal(
        "oracle_recruiting",
        "Oracle Recruiting",
        portal_endpoint("oracle_recruiting", "access_url"),
        "external",
        "ATS empresarial com páginas variadas por tenant.",
        "ats",
    ),
)

PORTALS_BY_ID = {portal.id: portal for portal in JOB_PORTALS}
AUTOMATIC_PORTAL_IDS = tuple(portal.id for portal in JOB_PORTALS if portal.automatic_search)
ASSISTED_PORTAL_IDS = tuple(portal.id for portal in JOB_PORTALS if portal.assisted_search)
PARTIAL_PORTAL_IDS = tuple(portal.id for portal in JOB_PORTALS if portal.partial_search)
SEARCHABLE_PORTAL_IDS = tuple(
    portal.id for portal in JOB_PORTALS if portal.search_mode != "external"
)
DEFAULT_PORTAL_IDS = (
    "adzuna",
    "inhire",
    "empregos",
    "empregando_brasil",
    "gupy",
    "linkedin",
    "indeed",
    "mindsight",
    "latojobs",
    "jobbol",
    "programathor",
    "vagas_com",
    "bne",
    "solides",
    "greenhouse",
    "lever",
    "smartrecruiters",
)


def portal_ids(value: str) -> tuple[str, ...]:
    values = [item.strip().lower() for item in value.replace(",", ";").split(";")]
    return tuple(dict.fromkeys(item for item in values if item in PORTALS_BY_ID))
