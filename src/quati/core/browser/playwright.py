from __future__ import annotations

import json
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import TypeVar
from urllib.parse import urlsplit

import httpx

from .url_safety import (
    host_is_allowed,
    validate_public_hostname_resolution,
    validate_public_https_url,
)

_Result = TypeVar("_Result")
_MAX_HTML_CHARS = 5_000_000
_MAX_JSON_BYTES = 2_000_000
_SAFE_JSON_HEADERS = frozenset({"accept", "user-agent", "x-inhire-client", "x-tenant"})


@dataclass(slots=True)
class PlaywrightBrowser:
    """Playwright sem perfil persistente, downloads ou permissões."""

    timeout_ms: int = 20_000

    def fetch_html(
        self,
        url: str,
        *,
        allowed_hosts: Collection[str],
        allow_subresources: bool = True,
    ) -> str:
        return self._run(
            url,
            allowed_hosts,
            self._settled_content,
            allow_subresources=allow_subresources,
        )

    def fetch_paginated_html(
        self,
        url: str,
        *,
        allowed_hosts: Collection[str],
        next_button_selector: str,
        item_selector: str,
        max_pages: int,
    ) -> list[str]:
        if not 1 <= max_pages <= 5:
            raise ValueError("O limite de páginas deve estar entre 1 e 5.")

        def collect_pages(page: object) -> list[str]:
            pages: list[str] = []
            try:
                page.locator(item_selector).first.wait_for(
                    state="attached", timeout=min(self.timeout_ms, 7_000)
                )
            except Exception as exc:
                if exc.__class__.__name__ != "TimeoutError":
                    raise
            self._settle_page(page)
            for page_number in range(max_pages):
                pages.append(self._safe_content(page))
                if page_number + 1 == max_pages:
                    break

                next_button = page.locator(next_button_selector)
                if (
                    not next_button.count()
                    or not next_button.is_visible()
                    or not next_button.is_enabled()
                ):
                    break

                first_item = page.locator(item_selector).first
                previous_href = first_item.get_attribute("href") if first_item.count() else None
                next_button.click()
                if not previous_href:
                    page.wait_for_timeout(500)
                    self._settle_page(page)
                    continue
                try:
                    page.wait_for_function(
                        """([selector, previousHref]) => {
                            const item = document.querySelector(selector);
                            return item && item.getAttribute('href') !== previousHref;
                        }""",
                        arg=[item_selector, previous_href],
                    )
                except Exception as exc:  # Falha fechada: preserva somente páginas confirmadas.
                    if exc.__class__.__name__ == "TimeoutError":
                        break
                    raise
                self._settle_page(page)
            return pages

        return self._run(url, allowed_hosts, collect_pages, allow_subresources=True)

    def fetch_json(
        self,
        url: str,
        *,
        allowed_hosts: Collection[str],
        headers: Mapping[str, str] | None = None,
    ) -> object:
        """Consulta APIs públicas sem cookies, proxy do ambiente ou redirecionamentos."""
        safe_url = validate_public_https_url(url, allowed_hosts)
        host = urlsplit(safe_url).hostname or ""
        validate_public_hostname_resolution(host)

        request_headers: dict[str, str] = {}
        for raw_name, raw_value in (headers or {}).items():
            name = raw_name.strip().lower()
            value = raw_value.strip()
            if (
                name not in _SAFE_JSON_HEADERS
                or not value
                or len(value) > 200
                or "\r" in value
                or "\n" in value
            ):
                raise ValueError("Cabeçalho não permitido na consulta pública.")
            request_headers[name] = value

        timeout_seconds = max(1.0, self.timeout_ms / 1_000)
        try:
            with httpx.Client(
                timeout=timeout_seconds,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream("GET", safe_url, headers=request_headers) as response:
                    if response.is_redirect or response.status_code >= 400:
                        raise RuntimeError("A fonte pública recusou a consulta.")
                    content_type = response.headers.get("content-type", "").lower()
                    if "json" not in content_type:
                        raise ValueError("A fonte não retornou JSON público.")
                    declared_size = response.headers.get("content-length", "")
                    if declared_size.isdigit() and int(declared_size) > _MAX_JSON_BYTES:
                        raise ValueError("A resposta JSON excedeu o limite de tamanho permitido.")
                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > _MAX_JSON_BYTES:
                            raise ValueError(
                                "A resposta JSON excedeu o limite de tamanho permitido."
                            )
        except httpx.HTTPError as exc:
            raise RuntimeError("A fonte pública recusou a consulta.") from exc
        try:
            return json.loads(body.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("A fonte retornou JSON inválido.") from exc

    def _settled_content(self, page: object) -> str:
        self._settle_page(page)
        return self._safe_content(page)

    def _settle_page(self, page: object) -> None:
        try:
            page.wait_for_load_state("networkidle", timeout=min(self.timeout_ms, 5_000))
        except Exception as exc:
            if exc.__class__.__name__ != "TimeoutError":
                raise
        page.wait_for_timeout(250)

    def _run(
        self,
        url: str,
        allowed_hosts: Collection[str],
        action: Callable[[object], _Result],
        *,
        allow_subresources: bool,
    ) -> _Result:
        safe_url = validate_public_https_url(url, allowed_hosts)
        safe_host = urlsplit(safe_url).hostname or ""
        validate_public_hostname_resolution(safe_host)
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - depende da instalação local
            raise RuntimeError("Instale a dependência Playwright antes de coletar vagas.") from exc

        checked_hosts = {safe_host}

        def route_request(route: object) -> None:
            if not allow_subresources and route.request.resource_type != "document":
                route.abort()
                return
            request_url = route.request.url
            if request_url.startswith(("about:", "data:")):
                route.continue_()
                return
            try:
                candidate = validate_public_https_url(request_url, allowed_hosts)
                candidate_host = urlsplit(candidate).hostname or ""
                if candidate_host not in checked_hosts:
                    validate_public_hostname_resolution(candidate_host)
                    checked_hosts.add(candidate_host)
                if host_is_allowed(candidate_host, allowed_hosts):
                    route.continue_()
                    return
            except ValueError:
                pass
            route.abort()

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(
                accept_downloads=False,
                java_script_enabled=True,
                permissions=[],
                service_workers="block",
            )
            try:
                page = context.new_page()
                page.set_default_timeout(self.timeout_ms)
                page.route("**/*", route_request)
                response = page.goto(safe_url, wait_until="domcontentloaded")
                if response is not None and response.status >= 400:
                    raise RuntimeError("A fonte pública recusou a coleta.")
                validate_public_https_url(page.url, allowed_hosts)
                return action(page)
            finally:
                context.close()
                browser.close()

    @staticmethod
    def _safe_content(page: object) -> str:
        html = page.content()
        if len(html) > _MAX_HTML_CHARS:
            raise ValueError("A página excedeu o limite de tamanho permitido.")
        return html
