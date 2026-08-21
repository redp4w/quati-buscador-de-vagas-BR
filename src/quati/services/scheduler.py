from __future__ import annotations

from collections.abc import Mapping

from quati.core.browser.interface import Browser
from quati.plugins.base import JobPlugin
from quati.storage import SQLiteJobRepository

from .collector import CollectionResult, JobCollector


class SearchScheduler:
    """Executa buscas vencidas quando chamado por CLI, tarefa agendada ou Docker."""

    def __init__(self, repository: SQLiteJobRepository, browser: Browser) -> None:
        self.repository = repository
        self.browser = browser

    def run_due(self, plugins: Mapping[str, JobPlugin]) -> list[CollectionResult]:
        results: list[CollectionResult] = []
        for schedule in self.repository.due_schedules():
            plugin = plugins.get(schedule.source)
            if plugin is None:
                self.repository.set_schedule_enabled(schedule.id, False)
                continue
            try:
                collector = JobCollector(self.repository, self.browser)
                results.append(collector.collect(plugin, schedule.entry_url))
            # Uma fonte com falha não deve interromper as demais.
            except Exception:  # nosec B112
                # A falha fica registrada pela coleta e não impede os demais agendamentos.
                continue
            finally:
                self.repository.mark_schedule_run(schedule.id)
        return results
