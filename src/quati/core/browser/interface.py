from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Protocol


class Browser(Protocol):
    """Navegador efêmero usado por plugins de fontes públicas."""

    def fetch_html(
        self,
        url: str,
        *,
        allowed_hosts: Collection[str],
        allow_subresources: bool = True,
    ) -> str:
        """Retorna HTML de uma URL pública validada."""

    def fetch_paginated_html(
        self,
        url: str,
        *,
        allowed_hosts: Collection[str],
        next_button_selector: str,
        item_selector: str,
        max_pages: int,
    ) -> list[str]:
        """Retorna páginas públicas após avançar por controles visíveis."""

    def fetch_json(
        self,
        url: str,
        *,
        allowed_hosts: Collection[str],
        headers: Mapping[str, str] | None = None,
    ) -> object:
        """Retorna JSON público com domínio, tamanho e redirecionamento controlados."""
