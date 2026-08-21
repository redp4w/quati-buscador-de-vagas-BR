from __future__ import annotations

import re
from collections.abc import Collection
from urllib.parse import urlsplit

from quati.core.browser.interface import Browser
from quati.core.browser.url_safety import validate_public_https_url
from quati.domain import JobInput

from .base import JobPlugin

_TENANT_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_JOB_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_WORKPLACE_LABELS = {
    "on-site": "Presencial",
    "onsite": "Presencial",
    "hybrid": "Híbrido",
    "remote": "Remoto",
}


class InHirePlugin(JobPlugin):
    """Lê a listagem pública de um tenant InHire, sem acessar candidaturas."""

    name = "inhire"
    display_name = "InHire — página pública de empresa"
    allowed_hosts: Collection[str] = ("inhire.app",)
    experimental = False
    _api_url = "https://api.inhire.app/job-posts/public/pages"
    _max_jobs = 500

    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        safe_url = validate_public_https_url(entry_url, self.allowed_hosts)
        tenant = self._tenant_from_url(safe_url)
        payload = browser.fetch_json(
            self._api_url,
            allowed_hosts=self.allowed_hosts,
            headers={
                "accept": "application/json",
                "x-inhire-client": "web-inhire",
                "x-tenant": tenant,
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("A InHire retornou uma resposta pública inesperada.")

        company = payload.get("tenantName")
        raw_jobs = payload.get("jobsPage")
        if not isinstance(company, str) or not company.strip() or not isinstance(raw_jobs, list):
            raise ValueError("A InHire retornou uma resposta pública incompleta.")

        jobs: list[JobInput] = []
        for item in raw_jobs[: self._max_jobs]:
            job = self._job_from_item(item, tenant, company)
            if job is not None:
                jobs.append(job)
        return jobs

    @staticmethod
    def _tenant_from_url(url: str) -> str:
        host = (urlsplit(url).hostname or "").lower()
        suffix = ".inhire.app"
        if not host.endswith(suffix):
            raise ValueError("Use uma página pública de empresa da InHire.")
        tenant = host.removesuffix(suffix)
        if (
            not _TENANT_RE.fullmatch(tenant)
            or "." in tenant
            or tenant in {"api", "www", "carreira"}
        ):
            raise ValueError("Tenant público da InHire inválido.")
        return tenant

    @staticmethod
    def _job_from_item(item: object, tenant: str, company: str) -> JobInput | None:
        if not isinstance(item, dict) or str(item.get("status", "")).lower() != "published":
            return None
        job_id = str(item.get("jobId", "")).strip().lower()
        title = str(item.get("displayName", "")).strip()
        if not _JOB_ID_RE.fullmatch(job_id) or not title:
            return None
        workplace = _WORKPLACE_LABELS.get(str(item.get("workplaceType", "")).strip().lower(), "")
        description = f"Modalidade: {workplace}." if workplace else ""
        try:
            return JobInput(
                source="inhire",
                external_id=job_id,
                title=title,
                company=company,
                location=str(item.get("location", "")),
                url=f"https://{tenant}.inhire.app/vagas/{job_id}",
                description=description,
            )
        except ValueError:
            return None
