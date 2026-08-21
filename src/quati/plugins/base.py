from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Collection

from quati.core.browser.interface import Browser
from quati.domain import JobInput


class JobPlugin(ABC):
    name: str
    display_name: str
    allowed_hosts: Collection[str]
    experimental: bool = False

    def prepare_entry_url(self, entry_url: str) -> str:
        """Remove parâmetros privados ou transitórios antes de registrar uma busca."""
        return entry_url

    @abstractmethod
    def collect(self, browser: Browser, entry_url: str) -> list[JobInput]:
        """Coleta apenas páginas públicas da fonte."""
