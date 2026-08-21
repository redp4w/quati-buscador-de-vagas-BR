from __future__ import annotations

import html as html_lib
import json
import re
from collections.abc import Collection, Iterable, Iterator
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from quati.core.browser.interface import Browser
from quati.core.browser.url_safety import host_is_allowed, validate_public_https_url
from quati.domain import JobInput
from quati.domain.job import normalized_key

from .base import JobPlugin


def _fetch_bounded_pages(
    browser: Browser,
    urls: Iterable[str],
    *,
    allowed_hosts: Collection[str],
    allow_subresources: bool = True,
) -> list[str]:
    """Preserva páginas já obtidas se uma paginação posterior for recusada."""
    pages: list[str] = []
    for url in urls:
        try:
            pages.append(
                browser.fetch_html(
                    url,
                    allowed_hosts=allowed_hosts,
                    allow_subresources=allow_subresources,
                )
            )
        except RuntimeError:
            if not pages:
                raise
            break
    return pages


class PublicStructuredPlugin(JobPlugin):
    """Base para sites públicos que expõem JobPosting ou links de vagas no HTML."""

    job_path_markers: tuple[str, ...] = ("/jobs/", "/job/", "/viewjob", "/vagas/")
    experimental = True

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        html = browser.fetch_html(safe_url, allowed_hosts=self.allowed_hosts)
        return self.parse_html(html, safe_url)

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        soup = BeautifulSoup(html, "html.parser")
        company = soup.find("h1")
        company_name = company.get_text(" ", strip=True) if company else "Não informado"
        jobs: list[JobInput] = []
        seen: set[str] = set()

        for item in self._json_ld_items(soup):
            if not self._is_job_posting(item):
                continue
            job = self._job_from_json_ld(item, page_url, company_name)
            if job and job.url not in seen:
                jobs.append(job)
                seen.add(job.url)

        for anchor in soup.select("a[href]"):
            raw_url = urljoin(page_url, anchor.get("href", ""))
            if not self._is_job_url(raw_url) or raw_url in seen:
                continue
            title = anchor.get_text(" ", strip=True) or anchor.get("aria-label", "")
            if not title:
                continue
            try:
                jobs.append(
                    JobInput(
                        source=self.name,
                        external_id=urlsplit(raw_url).path.rstrip("/").rsplit("/", 1)[-1],
                        title=title,
                        company=company_name,
                        location="",
                        url=raw_url,
                    )
                )
                seen.add(raw_url)
            except ValueError:
                continue
        return jobs

    def _json_ld_items(self, soup: BeautifulSoup) -> Iterator[dict]:
        for node in soup.select('script[type="application/ld+json"]'):
            raw_value = node.string or ""
            try:
                data = json.loads(raw_value)
            except json.JSONDecodeError:
                try:
                    data = json.loads(html_lib.unescape(raw_value))
                except json.JSONDecodeError:
                    continue
            yield from self._walk(data)

    def _walk(self, value: object) -> Iterator[dict]:
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                yield from self._walk(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from self._walk(nested)

    @staticmethod
    def _is_job_posting(item: dict) -> bool:
        value = item.get("@type")
        return value == "JobPosting" or (isinstance(value, list) and "JobPosting" in value)

    def _job_from_json_ld(
        self, item: dict, page_url: str, fallback_company: str
    ) -> JobInput | None:
        raw_url = urljoin(page_url, str(item.get("url", "")))
        if not self._is_job_url(raw_url):
            return None
        organization = item.get("hiringOrganization") or {}
        job_location = item.get("jobLocation") or {}
        if isinstance(job_location, list):
            job_location = job_location[0] if job_location else {}
        address = job_location.get("address") or {} if isinstance(job_location, dict) else {}
        location = ", ".join(
            str(address[key])
            for key in ("addressLocality", "addressRegion", "addressCountry")
            if address.get(key)
        )
        identifier = item.get("identifier") or {}
        external_id = (
            identifier.get("value", "") if isinstance(identifier, dict) else str(identifier)
        )
        try:
            return JobInput(
                source=self.name,
                external_id=str(external_id) or urlsplit(raw_url).path.rsplit("/", 1)[-1],
                title=str(item.get("title", "")),
                company=str(organization.get("name") or fallback_company),
                location=location,
                url=raw_url,
                description=BeautifulSoup(str(item.get("description", "")), "html.parser").get_text(
                    " "
                ),
                published_at=str(item.get("datePosted", "")),
            )
        except ValueError:
            return None

    def _is_job_url(self, url: str) -> bool:
        try:
            safe_url = validate_public_https_url(url, self.allowed_hosts)
        except ValueError:
            return False
        parsed = urlsplit(safe_url)
        return host_is_allowed(parsed.hostname or "", self.allowed_hosts) and any(
            marker in parsed.path for marker in self.job_path_markers
        )


class GreenhousePlugin(PublicStructuredPlugin):
    name = "greenhouse"
    display_name = "Greenhouse"
    allowed_hosts: Collection[str] = ("greenhouse.io",)
    experimental = False


class LeverPlugin(PublicStructuredPlugin):
    name = "lever"
    display_name = "Lever"
    allowed_hosts: Collection[str] = ("lever.co",)
    experimental = False

    def _is_job_url(self, url: str) -> bool:
        try:
            safe_url = validate_public_https_url(url, self.allowed_hosts)
        except ValueError:
            return False
        parsed = urlsplit(safe_url)
        path_parts = [part for part in parsed.path.split("/") if part]
        return host_is_allowed(parsed.hostname or "", self.allowed_hosts) and len(path_parts) >= 2


class WorkdayPlugin(PublicStructuredPlugin):
    name = "workday"
    display_name = "Workday"
    allowed_hosts: Collection[str] = ("myworkdayjobs.com",)
    job_path_markers = ("/job/",)


class AshbyPlugin(PublicStructuredPlugin):
    name = "ashby"
    display_name = "Ashby"
    allowed_hosts: Collection[str] = ("ashbyhq.com",)
    experimental = False

    def _is_job_url(self, url: str) -> bool:
        try:
            safe_url = validate_public_https_url(url, self.allowed_hosts)
        except ValueError:
            return False
        parsed = urlsplit(safe_url)
        path_parts = [part for part in parsed.path.split("/") if part]
        return host_is_allowed(parsed.hostname or "", self.allowed_hosts) and len(path_parts) >= 2


class SolidesPlugin(PublicStructuredPlugin):
    """Consulta a busca pública do portal e também aceita uma vaga direta."""

    name = "solides"
    display_name = "Sólides Vagas"
    allowed_hosts: Collection[str] = ("solides.com.br", "solides.jobs")
    job_path_markers = ("/vaga/", "/vacancies/")
    experimental = False

    def __init__(self, *, max_pages: int = 3) -> None:
        if not 1 <= max_pages <= 3:
            raise ValueError("O limite da Sólides deve ficar entre 1 e 3 páginas.")
        self.max_pages = max_pages

    def prepare_entry_url(self, entry_url: str) -> str:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        parsed = urlsplit(safe_url)
        if parsed.hostname == "apigw.solides.com.br":
            if parsed.path.rstrip("/") != "/jobs/v3/portal-vacancies-new":
                raise ValueError("Use somente a busca pública de vagas da Sólides.")
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            allowed = {"title", "take", "page"}
            if any(name not in allowed for name, _ in pairs):
                raise ValueError("A busca da Sólides contém filtros não permitidos.")
            if len({name for name, _ in pairs}) != len(pairs):
                raise ValueError("A busca da Sólides contém filtros duplicados.")
            parameters = dict(pairs)
            title = parameters.get("title", "").strip()
            if not title or len(title) > 300:
                raise ValueError("A busca da Sólides exige um cargo válido.")
            if parameters.get("take", "10") != "10":
                raise ValueError("A busca da Sólides deve pedir dez vagas por página.")
            page = parameters.get("page", "1")
            if not page.isdigit() or not 1 <= int(page) <= self.max_pages:
                raise ValueError("A página da busca da Sólides é inválida.")
            return safe_url
        if not self._is_job_url(safe_url):
            raise ValueError("Use a busca pública ou uma vaga individual da Sólides.")
        return safe_url

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = self.prepare_entry_url(entry_url)
        if urlsplit(safe_url).hostname == "apigw.solides.com.br":
            jobs: dict[str, JobInput] = {}
            for page_number in range(1, self.max_pages + 1):
                page_url = self._api_page_url(safe_url, page_number)
                payload = browser.fetch_json(page_url, allowed_hosts=self.allowed_hosts)
                page_jobs, total_pages = self.parse_payload(payload)
                jobs.update({job.url: job for job in page_jobs})
                if page_number >= total_pages:
                    break
            return list(jobs.values())
        html = browser.fetch_html(
            safe_url,
            allowed_hosts=self.allowed_hosts,
            allow_subresources=False,
        )
        return self.parse_html(html, safe_url)

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        jobs = super().parse_html(html, page_url)
        path = urlsplit(page_url).path
        marker = "/vaga/" if "/vaga/" in path else "/vacancies/"
        external_id = path.split(marker, 1)[-1].split("/", 1)[0]
        return [
            JobInput(
                source=job.source,
                external_id=external_id,
                title=job.title,
                company=job.company,
                location=job.location,
                url=job.url,
                description=job.description,
                published_at=job.published_at,
            )
            for job in jobs
        ]

    def parse_payload(self, payload: object) -> tuple[list[JobInput], int]:
        if not isinstance(payload, dict) or payload.get("success") is not True:
            raise ValueError("A Sólides retornou uma resposta inesperada.")
        response = payload.get("data")
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            raise ValueError("A Sólides retornou uma lista de vagas inválida.")
        raw_total_pages = response.get("totalPages", 1)
        total_pages = int(raw_total_pages) if str(raw_total_pages).isdigit() else 1
        total_pages = max(1, min(total_pages, self.max_pages))
        jobs: list[JobInput] = []
        for item in response["data"]:
            if not isinstance(item, dict):
                continue
            raw_url = str(item.get("redirectLink") or "")
            try:
                safe_url = validate_public_https_url(raw_url, self.allowed_hosts)
            except ValueError:
                continue
            city = item.get("city") if isinstance(item.get("city"), dict) else {}
            state = item.get("state") if isinstance(item.get("state"), dict) else {}
            location = ", ".join(
                value
                for value in (str(city.get("name") or ""), str(state.get("code") or ""))
                if value
            )
            mode = str(item.get("jobType") or "")
            if item.get("homeOffice") is True:
                mode = "remoto"
                location = location or "Remoto"
            description = BeautifulSoup(
                str(item.get("description") or ""), "html.parser"
            ).get_text(" ", strip=True)
            if mode:
                description = f"{description} Modalidade: {mode}."
            if item.get("peopleWithDisabilities") is True or item.get("pcdOnly") is True:
                description = f"{description} Vaga elegível para PCD."
            try:
                jobs.append(
                    JobInput(
                        source=self.name,
                        external_id=str(item.get("id") or ""),
                        title=str(item.get("title") or ""),
                        company=str(item.get("companyName") or "Não informado"),
                        location=location,
                        url=safe_url,
                        description=description,
                        published_at=str(item.get("createdAt") or ""),
                    )
                )
            except ValueError:
                continue
        return jobs, total_pages

    @staticmethod
    def _api_page_url(url: str, page_number: int) -> str:
        parsed = urlsplit(url)
        parameters = dict(parse_qsl(parsed.query, keep_blank_values=True))
        parameters["take"] = "10"
        parameters["page"] = str(page_number)
        return urlunsplit(parsed._replace(query=urlencode(parameters)))


class EmpregosPlugin(PublicStructuredPlugin):
    name = "empregos"
    display_name = "Empregos.com.br"
    allowed_hosts: Collection[str] = ("empregos.com.br",)
    job_path_markers = ("/vaga/",)
    experimental = False

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        html = browser.fetch_html(
            safe_url,
            allowed_hosts=self.allowed_hosts,
            allow_subresources=False,
        )
        return self.parse_html(html, safe_url)

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        jobs = {job.url: job for job in super().parse_html(html, page_url)}
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div#job-card"):
            anchor = card.select_one('a[href^="/vaga/"]')
            if anchor is None:
                continue
            raw_url = urljoin(page_url, anchor.get("href", ""))
            if not self._is_job_url(raw_url):
                continue
            location = ""
            for image in card.select("img[alt]"):
                if "localizacao" in self._normalized(image.get("alt", "")):
                    location = image.parent.get_text(" ", strip=True)
                    break
            published = next(
                (
                    node.get_text(" ", strip=True)
                    for node in card.select("div")
                    if node.get_text(" ", strip=True).startswith("Publicada")
                    and len(node.get_text(" ", strip=True)) < 80
                ),
                "",
            )
            try:
                job = JobInput(
                    source=self.name,
                    external_id=urlsplit(raw_url).path.split("/vaga/", 1)[-1].split("/", 1)[0],
                    title=self._node_text(card.select_one("h2")),
                    company=self._node_text(card.select_one("h3"), "Não informado"),
                    location=location,
                    url=raw_url,
                    description=self._node_text(card.select_one("div.line-clamp-5")),
                    published_at=published,
                )
            except ValueError:
                continue
            jobs[job.url] = job
        return list(jobs.values())

    @staticmethod
    def _node_text(node: object | None, fallback: str = "") -> str:
        return node.get_text(" ", strip=True) if node is not None else fallback

    @staticmethod
    def _normalized(value: str) -> str:
        return normalized_key(value)


class EmpregandoBrasilPlugin(PublicStructuredPlugin):
    name = "empregando_brasil"
    display_name = "Empregando Brasil"
    allowed_hosts: Collection[str] = ("empregandobrasil.com.br",)
    job_path_markers = ("/vagas/",)
    experimental = False

    def __init__(self, *, max_pages: int = 3) -> None:
        if not 1 <= max_pages <= 5:
            raise ValueError("O limite de páginas deve estar entre 1 e 5.")
        self.max_pages = max_pages

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        html_pages = _fetch_bounded_pages(
            browser,
            (self._page_url(safe_url, page_number) for page_number in range(1, self.max_pages + 1)),
            allowed_hosts=self.allowed_hosts,
            allow_subresources=False,
        )
        jobs: dict[str, JobInput] = {}
        for html in html_pages:
            jobs.update({job.url: job for job in self.parse_html(html, safe_url)})
        return list(jobs.values())

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        jobs = {job.url: job for job in super().parse_html(html, page_url)}
        soup = BeautifulSoup(html, "html.parser")
        pcd_filtered = ("diversity", "pcd") in parse_qsl(
            urlsplit(page_url).query, keep_blank_values=True
        )
        for card in soup.select("li.jobs-item"):
            anchor = card.select_one('a.rowlink[href^="/vagas/"]')
            if anchor is None:
                continue
            raw_url = urljoin(page_url, anchor.get("href", ""))
            if not self._is_job_url(raw_url):
                continue
            metadata = [node.get_text(" ", strip=True) for node in card.select(".jobs-meta span")]
            description = self._node_text(card.select_one(".tl-desc"))
            if pcd_filtered:
                description += " Elegível para PCD conforme filtro público do portal."
            try:
                job = JobInput(
                    source=self.name,
                    external_id=urlsplit(raw_url).path.strip("/").rsplit("/", 1)[-1],
                    title=self._node_text(card.select_one(".jobs-title")),
                    company=self._node_text(card.select_one(".jobs-foot .muted"), "Não informado"),
                    location=metadata[0] if metadata else "",
                    url=raw_url,
                    description=description,
                    published_at=metadata[-1] if len(metadata) > 1 else "",
                )
            except ValueError:
                continue
            jobs[job.url] = job
        return list(jobs.values())

    @staticmethod
    def _page_url(url: str, page_number: int) -> str:
        parsed = urlsplit(url)
        parameters = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if page_number > 1:
            parameters["page"] = str(page_number)
        else:
            parameters.pop("page", None)
        return urlunsplit(parsed._replace(query=urlencode(parameters)))

    @staticmethod
    def _node_text(node: object | None, fallback: str = "") -> str:
        return node.get_text(" ", strip=True) if node is not None else fallback


class MindsightPlugin(PublicStructuredPlugin):
    """Consulta vagas públicas da Mindsight via API central ou páginas de empresas."""

    name = "mindsight"
    display_name = "Mindsight"
    allowed_hosts: Collection[str] = (
        "mindsight.com.br",
        "central.mindsight.com.br",
        "oportunidades.mindsight.com.br",
    )
    job_path_markers = ("/register", "/vagas/", "/vaga/", "/job-postings/")
    experimental = False

    def __init__(self, *, max_pages: int = 3) -> None:
        if not 1 <= max_pages <= 5:
            raise ValueError("O limite de páginas deve estar entre 1 e 5.")
        self.max_pages = max_pages

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        parsed = urlsplit(safe_url)
        if parsed.hostname == "central.mindsight.com.br" and "/api/v1/job-postings" in parsed.path:
            jobs: dict[str, JobInput] = {}
            for page_number in range(1, self.max_pages + 1):
                page_url = self._api_page_url(safe_url, page_number)
                try:
                    payload = browser.fetch_json(page_url, allowed_hosts=self.allowed_hosts)
                except (RuntimeError, ValueError):
                    break
                page_jobs, has_next = self.parse_payload(payload)
                jobs.update({job.url: job for job in page_jobs})
                if not has_next:
                    break
            return list(jobs.values())
        html = browser.fetch_html(
            safe_url,
            allowed_hosts=self.allowed_hosts,
            allow_subresources=True,
        )
        return self.parse_html(html, safe_url)

    def parse_payload(self, payload: object) -> tuple[list[JobInput], bool]:
        if not isinstance(payload, dict):
            raise ValueError("Resposta JSON inválida da Mindsight.")
        results = payload.get("results")
        if not isinstance(results, list):
            raise ValueError("Lista de vagas ausente na resposta da Mindsight.")
        has_next = bool(payload.get("next"))
        jobs: list[JobInput] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            tenant = str(item.get("tenant") or "").strip()
            posting_id = item.get("ats_job_posting_id") or item.get("id")
            if tenant and posting_id:
                raw_url = f"https://oportunidades.mindsight.com.br/{tenant}/{posting_id}/register"
            else:
                raw_url = "https://central.mindsight.com.br/"
            try:
                safe_url = validate_public_https_url(raw_url, self.allowed_hosts)
            except ValueError:
                continue
            loc_parts = [
                str(item.get(k) or "").strip()
                for k in ("city", "state", "country")
                if item.get(k)
            ]
            location = ", ".join(loc_parts)
            work_model = str(item.get("work_model") or "").strip()
            desc = BeautifulSoup(
                str(item.get("description") or item.get("name") or ""), "html.parser"
            ).get_text(" ", strip=True)
            if work_model:
                desc += f" Modalidade: {work_model}."
            external_id = str(item.get("id") or posting_id or "")
            try:
                jobs.append(
                    JobInput(
                        source=self.name,
                        external_id=external_id,
                        title=str(item.get("name") or ""),
                        company=str(item.get("company_name") or "Não informado"),
                        location=location,
                        url=safe_url,
                        description=desc,
                        published_at=str(item.get("created_at") or ""),
                    )
                )
            except ValueError:
                continue
        return jobs, has_next

    @staticmethod
    def _api_page_url(url: str, page_number: int) -> str:
        parsed = urlsplit(url)
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        params["page"] = str(page_number)
        if "page_size" not in params:
            params["page_size"] = "20"
        return urlunsplit(parsed._replace(query=urlencode(params)))


class LatoJobsPlugin(PublicStructuredPlugin):
    """Consulta vagas públicas e oportunidades de tecnologia na Lato Jobs."""

    name = "latojobs"
    display_name = "Lato Jobs"
    allowed_hosts: Collection[str] = ("latojobs.com", "www.latojobs.com")
    job_path_markers = ("/jobs/",)
    experimental = False
    _UUID_RE = re.compile(
        r"/jobs/([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
    )

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        html = browser.fetch_html(
            safe_url,
            allowed_hosts=self.allowed_hosts,
            allow_subresources=True,
        )
        return self.parse_html(html, safe_url)

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        jobs = {job.url: job for job in super().parse_html(html, page_url)}
        soup = BeautifulSoup(html, "html.parser")
        for link in soup.select("a[href]"):
            href = link.get("href", "")
            match = self._UUID_RE.search(href)
            if not match:
                continue
            raw_url = urljoin(page_url, href.split("?")[0])
            if raw_url in jobs:
                continue
            title = link.get_text(" ", strip=True)
            if not title or len(title) < 3:
                continue
            card = link.find_parent("div", class_=lambda c: bool(c and "group" in c))
            company = "Não informado"
            location = ""
            desc = title
            if card is not None:
                company_node = card.select_one('a[href*="/companies/"]') or card.select_one(
                    "p.text-\\[13px\\]"
                )
                if company_node:
                    company = company_node.get_text(" ", strip=True) or company
                badges = [span.get_text(" ", strip=True) for span in card.select("span")]
                location = next(
                    (
                        b
                        for b in badges
                        if any(
                            k in b.lower()
                            for k in (
                                "brazil",
                                "brasil",
                                "sao paulo",
                                "remote",
                                "remoto",
                                "latam",
                            )
                        )
                    ),
                    "",
                )
                desc = card.get_text(" | ", strip=True)
            try:
                job = JobInput(
                    source=self.name,
                    external_id=match.group(1),
                    title=title,
                    company=company,
                    location=location,
                    url=raw_url,
                    description=desc,
                )
                jobs[job.url] = job
            except ValueError:
                continue
        return list(jobs.values())


class GupyPlugin(PublicStructuredPlugin):
    """Consulta vagas públicas na Gupy via API de busca ou páginas de empresas."""

    name = "gupy"
    display_name = "Gupy"
    allowed_hosts: Collection[str] = (
        "gupy.io",
        "portal.gupy.io",
        "employability-portal.gupy.io",
    )
    job_path_markers = ("/job/", "/jobs/", "/vagas/")
    experimental = False

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        parsed = urlsplit(safe_url)
        if "employability-portal.gupy.io" in (parsed.hostname or ""):
            try:
                payload = browser.fetch_json(safe_url, allowed_hosts=self.allowed_hosts)
                return self.parse_payload(payload)
            except (RuntimeError, ValueError):
                pass
        html = browser.fetch_html(
            safe_url,
            allowed_hosts=self.allowed_hosts,
            allow_subresources=True,
        )
        return self.parse_html(html, safe_url)

    def parse_payload(self, payload: object) -> list[JobInput]:
        if not isinstance(payload, dict):
            raise ValueError("Resposta JSON inválida da Gupy.")
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("Lista de vagas ausente na resposta da Gupy.")
        jobs: list[JobInput] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            raw_url = str(item.get("jobUrl") or "").strip()
            if not raw_url:
                continue
            try:
                safe_url = validate_public_https_url(raw_url, self.allowed_hosts)
            except ValueError:
                continue
            city = str(item.get("city") or "").strip()
            state = str(item.get("state") or "").strip()
            location = f"{city}, {state}".strip(", ")
            workplace = str(item.get("workplaceType") or "").strip()
            desc = str(item.get("description") or item.get("name") or "")
            if workplace:
                desc += f" Modalidade: {workplace}."
            if item.get("isPcd") is True:
                desc += " Vaga elegível para PCD."
            company = str(
                item.get("careerPageName") or item.get("companyName") or "Não informado"
            )
            job_id = str(
                item.get("id")
                or item.get("jobId")
                or urlsplit(safe_url).path.rstrip("/").split("/")[-1]
            )
            try:
                jobs.append(
                    JobInput(
                        source=self.name,
                        external_id=job_id,
                        title=str(item.get("name") or ""),
                        company=company,
                        location=location,
                        url=safe_url,
                        description=desc,
                        published_at=str(item.get("publishedDate") or ""),
                    )
                )
            except ValueError:
                continue
        return jobs

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        jobs = {job.url: job for job in super().parse_html(html, page_url)}
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.select('a[href*="/job/"]'):
            raw_url = urljoin(page_url, anchor.get("href", ""))
            if not self._is_job_url(raw_url):
                continue
            text = anchor.get_text("\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            title = lines[1] if len(lines) > 1 else (lines[0] if lines else "")
            company = lines[0] if len(lines) > 1 else "Não informado"
            location = next(
                (
                    line
                    for line in lines
                    if any(
                        sep in line
                        for sep in (" - ", " / ", "Remoto", "Presencial", "Híbrido")
                    )
                ),
                "",
            )
            try:
                job = JobInput(
                    source=self.name,
                    external_id=urlsplit(raw_url).path.rstrip("/").split("/")[-1],
                    title=title or "Vaga",
                    company=company,
                    location=location,
                    url=raw_url,
                    description=text,
                )
                jobs[job.url] = job
            except ValueError:
                continue
        return list(jobs.values())


class LinkedInPlugin(PublicStructuredPlugin):
    """Consulta anúncios públicos de emprego no LinkedIn sem exigência de conta."""

    name = "linkedin"
    display_name = "LinkedIn"
    allowed_hosts: Collection[str] = ("linkedin.com", "www.linkedin.com")
    job_path_markers = ("/jobs/view/", "/jobs/search/", "/jobs-guest/")
    experimental = False

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        html = browser.fetch_html(
            safe_url,
            allowed_hosts=self.allowed_hosts,
            allow_subresources=True,
        )
        return self.parse_html(html, safe_url)

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        jobs = {job.url: job for job in super().parse_html(html, page_url)}
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("li, div.base-card, div.job-search-card"):
            title_node = card.select_one("h3.base-search-card__title, h3, a.base-card__full-link")
            link_node = card.select_one("a.base-card__full-link, a[href*='/jobs/view/']")
            if not title_node or not link_node:
                continue
            raw_url = urljoin(page_url, link_node.get("href", "").split("?")[0])
            if not self._is_job_url(raw_url):
                continue
            company_node = card.select_one(
                "h4.base-search-card__subtitle, a.hidden-nested-link, h4"
            )
            loc_node = card.select_one("span.job-search-card__location")
            time_node = card.select_one("time")
            title = title_node.get_text(" ", strip=True)
            company = company_node.get_text(" ", strip=True) if company_node else "Não informado"
            location = loc_node.get_text(" ", strip=True) if loc_node else ""
            published = time_node.get("datetime", "") if time_node else ""
            parts = urlsplit(raw_url).path.rstrip("/").split("-")
            external_id = parts[-1] if parts else urlsplit(raw_url).path.rstrip("/").split("/")[-1]
            try:
                job = JobInput(
                    source=self.name,
                    external_id=external_id,
                    title=title,
                    company=company,
                    location=location,
                    url=raw_url,
                    description=card.get_text(" ", strip=True),
                    published_at=published,
                )
                jobs[job.url] = job
            except ValueError:
                continue
        return list(jobs.values())


class IndeedPlugin(PublicStructuredPlugin):
    """Consulta vagas públicas do Indeed via renderização e extração HTML."""

    name = "indeed"
    display_name = "Indeed"
    allowed_hosts: Collection[str] = ("indeed.com", "br.indeed.com", "www.indeed.com")
    job_path_markers = ("/jobs", "/viewjob", "/rc/clk", "/cmp/")
    experimental = False

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        html = browser.fetch_html(
            safe_url,
            allowed_hosts=self.allowed_hosts,
            allow_subresources=True,
        )
        return self.parse_html(html, safe_url)

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        jobs = {job.url: job for job in super().parse_html(html, page_url)}
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("div.job_seen_beacon, td.resultContent, div.cardOutline"):
            title_node = card.select_one("h2.jobTitle a, a.jcs-JobTitle, h2.jobTitle span")
            link_node = card.select_one(
                "h2.jobTitle a, a.jcs-JobTitle, a[href*='/rc/clk'], a[href*='/viewjob']"
            )
            if not title_node or not link_node:
                continue
            raw_url = urljoin(page_url, link_node.get("href", ""))
            company_node = card.select_one('span[data-testid="company-name"], span.companyName')
            loc_node = card.select_one('div[data-testid="text-location"], div.companyLocation')
            snippet_node = card.select_one("div.job-snippet, div.underShelfFooter")
            date_node = card.select_one('span.date, span[data-testid="myJobsStateDate"]')
            title = title_node.get_text(" ", strip=True)
            company = company_node.get_text(" ", strip=True) if company_node else "Não informado"
            location = loc_node.get_text(" ", strip=True) if loc_node else ""
            desc = snippet_node.get_text(" ", strip=True) if snippet_node else ""
            published = date_node.get_text(" ", strip=True) if date_node else ""
            job_key = link_node.get("data-jk") or urlsplit(raw_url).path.rstrip("/").split("/")[-1]
            try:
                job = JobInput(
                    source=self.name,
                    external_id=str(job_key),
                    title=title,
                    company=company,
                    location=location,
                    url=raw_url,
                    description=desc,
                    published_at=published,
                )
                jobs[job.url] = job
            except ValueError:
                continue
        return list(jobs.values())


class VagasComPlugin(PublicStructuredPlugin):
    """Consulta vagas abertas publicamente no portal Vagas.com."""

    name = "vagas_com"
    display_name = "Vagas.com"
    allowed_hosts: Collection[str] = ("vagas.com.br", "www.vagas.com.br")
    job_path_markers = ("/vagas/", "/vagas-de-", "/vaga/")
    experimental = False

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        html = browser.fetch_html(
            safe_url,
            allowed_hosts=self.allowed_hosts,
            allow_subresources=False,
        )
        return self.parse_html(html, safe_url)

    def parse_html(self, html: str, page_url: str) -> list[JobInput]:
        jobs = {job.url: job for job in super().parse_html(html, page_url)}
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("li.vaga, article.vaga, div.vaga"):
            link = card.select_one("a.link-detalhes-vaga, a[href*='/vagas/v']")
            if not link:
                continue
            raw_url = urljoin(page_url, link.get("href", ""))
            if not self._is_job_url(raw_url):
                continue
            title = link.get_text(" ", strip=True)
            company_node = card.select_one("span.empr")
            loc_node = card.select_one("span.vaga-local")
            desc_node = card.select_one("div.detalhes")
            published_node = card.select_one("span.data-publicacao")
            company = company_node.get_text(" ", strip=True) if company_node else "Não informado"
            location = loc_node.get_text(" ", strip=True) if loc_node else ""
            desc = desc_node.get_text(" ", strip=True) if desc_node else ""
            published = published_node.get_text(" ", strip=True) if published_node else ""
            path = urlsplit(raw_url).path.rstrip("/")
            external_id = (
                path.split("/vagas/")[-1].split("/")[0]
                if "/vagas/" in path
                else path.split("/")[-1]
            )
            try:
                job = JobInput(
                    source=self.name,
                    external_id=external_id,
                    title=title,
                    company=company,
                    location=location,
                    url=raw_url,
                    description=desc,
                    published_at=published,
                )
                jobs[job.url] = job
            except ValueError:
                continue
        return list(jobs.values())
