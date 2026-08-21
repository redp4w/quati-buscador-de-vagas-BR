from __future__ import annotations

from collections.abc import Collection
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from quati.config.sources import load_source_catalog
from quati.core.browser.interface import Browser
from quati.core.browser.url_safety import validate_public_https_url
from quati.domain import JobInput
from quati.domain.job import normalized_key

from .base import JobPlugin

_PAGE_SIZE = 100
_MAX_API_PAGES = 3


def _plain_html(value: object) -> str:
    return BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True)


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _items(value: object) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))


def _company_name(source: str, entry_url: str, fallback: str) -> str:
    canonical = _canonical_url(entry_url)
    for company in load_source_catalog().companies:
        if company.source == source and _canonical_url(company.url) == canonical:
            return company.name
    return fallback


def _path_token(entry_url: str) -> str:
    parts = [part for part in urlsplit(entry_url).path.split("/") if part]
    if not parts or len(parts[0]) > 100:
        raise ValueError("A página pública da empresa não contém um identificador válido.")
    return parts[0]


def _job(
    *,
    source: str,
    external_id: object,
    title: object,
    company: object,
    location: object,
    url: object,
    description: object = "",
    published_at: object = "",
    url_hosts: Collection[str],
) -> JobInput | None:
    try:
        safe_url = validate_public_https_url(str(url or ""), url_hosts)
        return JobInput(
            source=source,
            external_id=str(external_id or ""),
            title=str(title or ""),
            company=str(company or ""),
            location=str(location or ""),
            url=safe_url,
            description=_plain_html(description),
            published_at=str(published_at or ""),
        )
    except ValueError:
        return None


class GreenhouseAPIPlugin(JobPlugin):
    """Vagas publicadas por empresa na Job Board API oficial do Greenhouse."""

    name = "greenhouse"
    display_name = "Greenhouse — empresas catalogadas"
    allowed_hosts: Collection[str] = ("greenhouse.io",)

    def prepare_entry_url(self, entry_url: str) -> str:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        _path_token(safe_url)
        return _canonical_url(safe_url)

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_entry = self.prepare_entry_url(entry_url)
        board = _path_token(safe_entry)
        api_base = f"https://boards-api.greenhouse.io/v1/boards/{quote(board, safe='')}/jobs"
        try:
            payload = browser.fetch_json(
                f"{api_base}?content=true",
                allowed_hosts=self.allowed_hosts,
            )
        except ValueError:
            # Quadros muito grandes podem exceder o limite defensivo com descrições completas.
            payload = browser.fetch_json(api_base, allowed_hosts=self.allowed_hosts)
        company = _company_name(self.name, safe_entry, board.replace("-", " ").title())
        jobs: list[JobInput] = []
        for item in _items(_mapping(payload).get("jobs")):
            location = _mapping(item.get("location")).get("name", "")
            job = _job(
                source=self.name,
                external_id=item.get("id"),
                title=item.get("title"),
                company=company,
                location=location,
                url=item.get("absolute_url"),
                description=item.get("content", ""),
                published_at=item.get("updated_at", ""),
                url_hosts=self.allowed_hosts,
            )
            if job:
                jobs.append(job)
        return jobs


class LeverAPIPlugin(JobPlugin):
    """Vagas publicadas por empresa na Postings API oficial do Lever."""

    name = "lever"
    display_name = "Lever — empresas catalogadas"
    allowed_hosts: Collection[str] = ("lever.co",)

    def prepare_entry_url(self, entry_url: str) -> str:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        _path_token(safe_url)
        return _canonical_url(safe_url)

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_entry = self.prepare_entry_url(entry_url)
        site = _path_token(safe_entry)
        company = _company_name(self.name, safe_entry, site.replace("-", " ").title())
        jobs: list[JobInput] = []
        for page in range(_MAX_API_PAGES):
            query = urlencode(
                {"mode": "json", "skip": page * _PAGE_SIZE, "limit": _PAGE_SIZE}
            )
            payload = browser.fetch_json(
                f"https://api.lever.co/v0/postings/{quote(site, safe='')}?{query}",
                allowed_hosts=self.allowed_hosts,
            )
            batch = _items(payload)
            for item in batch:
                categories = _mapping(item.get("categories"))
                all_locations = categories.get("allLocations")
                locations = (
                    [str(value) for value in all_locations]
                    if isinstance(all_locations, list)
                    else []
                )
                location = ", ".join(locations) or str(categories.get("location") or "")
                if not location and item.get("country"):
                    location = str(item["country"])
                descriptions: list[str] = [
                    str(item.get("descriptionPlain") or item.get("openingPlain") or "")
                ]
                descriptions.extend(
                    _plain_html(section.get("content")) for section in _items(item.get("lists"))
                )
                workplace = str(item.get("workplaceType") or "")
                if workplace and workplace != "unspecified":
                    descriptions.append(f"Modalidade: {workplace}.")
                job = _job(
                    source=self.name,
                    external_id=item.get("id"),
                    title=item.get("text"),
                    company=company,
                    location=location,
                    url=item.get("hostedUrl"),
                    description=" ".join(descriptions),
                    url_hosts=self.allowed_hosts,
                )
                if job:
                    jobs.append(job)
            if len(batch) < _PAGE_SIZE:
                break
        return jobs


class AshbyAPIPlugin(JobPlugin):
    """Vagas publicadas por empresa na Job Postings API oficial do Ashby."""

    name = "ashby"
    display_name = "Ashby — empresas catalogadas"
    allowed_hosts: Collection[str] = ("ashbyhq.com",)

    def prepare_entry_url(self, entry_url: str) -> str:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        _path_token(safe_url)
        return _canonical_url(safe_url)

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_entry = self.prepare_entry_url(entry_url)
        board = _path_token(safe_entry)
        payload = browser.fetch_json(
            f"https://api.ashbyhq.com/posting-api/job-board/{quote(board, safe='')}",
            allowed_hosts=self.allowed_hosts,
        )
        company = _company_name(self.name, safe_entry, board.replace("-", " ").title())
        jobs: list[JobInput] = []
        for item in _items(_mapping(payload).get("jobs")):
            description = item.get("descriptionPlain") or item.get("descriptionHtml") or ""
            if item.get("workplaceType"):
                description = f"{description} Modalidade: {item['workplaceType']}."
            job = _job(
                source=self.name,
                external_id=item.get("id") or item.get("jobUrl"),
                title=item.get("title"),
                company=company,
                location=item.get("location", ""),
                url=item.get("jobUrl"),
                description=description,
                published_at=item.get("publishedAt", ""),
                url_hosts=self.allowed_hosts,
            )
            if job:
                jobs.append(job)
        return jobs


class SmartRecruitersAPIPlugin(JobPlugin):
    """Anúncios ativos por empresa na Posting API pública do SmartRecruiters."""

    name = "smartrecruiters"
    display_name = "SmartRecruiters — empresas catalogadas"
    allowed_hosts: Collection[str] = ("smartrecruiters.com",)

    def prepare_entry_url(self, entry_url: str) -> str:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        _path_token(safe_url)
        return _canonical_url(safe_url)

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_entry = self.prepare_entry_url(entry_url)
        company_id = _path_token(safe_entry)
        fallback_company = _company_name(
            self.name, safe_entry, company_id.replace("-", " ").title()
        )
        jobs: list[JobInput] = []
        for page in range(_MAX_API_PAGES):
            query = urlencode(
                {"limit": _PAGE_SIZE, "offset": page * _PAGE_SIZE, "country": "br"}
            )
            payload = browser.fetch_json(
                "https://api.smartrecruiters.com/v1/companies/"
                f"{quote(company_id, safe='')}/postings?{query}",
                allowed_hosts=self.allowed_hosts,
            )
            response = _mapping(payload)
            batch = _items(response.get("content"))
            for item in batch:
                company = _mapping(item.get("company"))
                location = _mapping(item.get("location"))
                location_text = ", ".join(
                    str(location[key])
                    for key in ("city", "region", "country")
                    if location.get(key)
                )
                if location.get("remote"):
                    location_text = f"{location_text}, Remoto".strip(", ")
                title = str(item.get("name") or "")
                posting_id = str(item.get("id") or item.get("uuid") or "")
                slug = normalized_key(title).replace(" ", "-")[:100] or "vaga"
                public_url = (
                    f"https://jobs.smartrecruiters.com/{quote(company_id, safe='')}/"
                    f"{quote(posting_id, safe='')}-{slug}"
                )
                details = " ".join(
                    str(_mapping(item.get(field)).get("label") or "")
                    for field in ("department", "function", "typeOfEmployment", "experienceLevel")
                )
                job = _job(
                    source=self.name,
                    external_id=posting_id,
                    title=title,
                    company=company.get("name") or fallback_company,
                    location=location_text,
                    url=public_url,
                    description=details,
                    published_at=item.get("releasedDate", ""),
                    url_hosts=self.allowed_hosts,
                )
                if job:
                    jobs.append(job)
            if len(batch) < _PAGE_SIZE or len(jobs) >= int(response.get("totalFound") or 0):
                break
        return jobs


class RecruiteeAPIPlugin(JobPlugin):
    """Ofertas publicadas na Careers Site API oficial do Recruitee."""

    name = "recruitee"
    display_name = "Recruitee — empresas catalogadas"
    allowed_hosts: Collection[str] = ("recruitee.com",)

    def prepare_entry_url(self, entry_url: str) -> str:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        host = urlsplit(safe_url).hostname or ""
        if host in {"recruitee.com", "www.recruitee.com"}:
            raise ValueError("Informe a página pública de uma empresa no Recruitee.")
        return _canonical_url(safe_url)

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_entry = self.prepare_entry_url(entry_url)
        parsed = urlsplit(safe_entry)
        api_url = urlunsplit(("https", parsed.netloc, "/api/offers/", "", ""))
        payload = browser.fetch_json(api_url, allowed_hosts=self.allowed_hosts)
        response = _mapping(payload)
        batch = _items(response.get("offers") if "offers" in response else payload)
        tenant = (parsed.hostname or "").split(".", 1)[0]
        company = _company_name(self.name, safe_entry, tenant.replace("-", " ").title())
        jobs: list[JobInput] = []
        for item in batch:
            locations = _items(item.get("locations"))
            location = ", ".join(
                str(value)
                for location_item in locations
                for key in ("city", "state", "country")
                if (value := location_item.get(key))
            ) or str(item.get("location") or item.get("city") or "")
            job = _job(
                source=self.name,
                external_id=item.get("id") or item.get("slug"),
                title=item.get("title"),
                company=company,
                location=location,
                url=item.get("careers_url") or item.get("url"),
                description=item.get("description") or item.get("description_html") or "",
                published_at=item.get("published_at") or item.get("created_at") or "",
                url_hosts=self.allowed_hosts,
            )
            if job:
                jobs.append(job)
        return jobs


class WorkablePublicPlugin(JobPlugin):
    """Vagas publicadas por empresa no endpoint público documentado do Workable."""

    name = "workable"
    display_name = "Workable — empresas catalogadas"
    allowed_hosts: Collection[str] = ("workable.com",)

    def prepare_entry_url(self, entry_url: str) -> str:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        self._account(safe_url)
        return _canonical_url(safe_url)

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_entry = self.prepare_entry_url(entry_url)
        account = self._account(safe_entry)
        payload = browser.fetch_json(
            f"https://www.workable.com/api/accounts/{quote(account, safe='')}?details=true",
            allowed_hosts=self.allowed_hosts,
        )
        response = _mapping(payload)
        batch = _items(response.get("jobs") if "jobs" in response else payload)
        company = _company_name(self.name, safe_entry, account.replace("-", " ").title())
        jobs: list[JobInput] = []
        for item in batch:
            location = _mapping(item.get("location"))
            location_text = str(location.get("location_str") or item.get("location_str") or "")
            description = item.get("description") or item.get("description_html") or ""
            if location.get("workplace_type"):
                description = f"{description} Modalidade: {location['workplace_type']}."
            job = _job(
                source=self.name,
                external_id=item.get("id") or item.get("shortcode"),
                title=item.get("title"),
                company=company,
                location=location_text,
                url=item.get("url") or item.get("shortlink"),
                description=description,
                published_at=item.get("created_at", ""),
                url_hosts=self.allowed_hosts,
            )
            if job:
                jobs.append(job)
        return jobs

    @staticmethod
    def _account(entry_url: str) -> str:
        parsed = urlsplit(entry_url)
        host = parsed.hostname or ""
        parts = [part for part in parsed.path.split("/") if part]
        if host == "apply.workable.com" and parts:
            account = parts[0]
        else:
            account = host.removesuffix(".workable.com")
        if not account or account in {"www", "apply"} or len(account) > 100:
            raise ValueError("Informe a página pública de uma empresa no Workable.")
        return account
