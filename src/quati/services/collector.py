from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from quati.core.browser.interface import Browser
from quati.domain import JobInput
from quati.plugins.base import JobPlugin
from quati.storage import SQLiteJobRepository


@dataclass(frozen=True, slots=True)
class CollectionResult:
    found: int
    inserted: int
    updated: int
    run_id: int
    filtered: int = 0


class JobCollector:
    def __init__(self, repository: SQLiteJobRepository, browser: Browser) -> None:
        self.repository = repository
        self.browser = browser

    def collect(
        self,
        plugin: JobPlugin,
        entry_url: str,
        *,
        job_filter: Callable[[JobInput], bool] | None = None,
    ) -> CollectionResult:
        safe_entry_url = plugin.prepare_entry_url(entry_url)
        run = self.repository.start_run(plugin.name, safe_entry_url)
        try:
            collected_jobs = plugin.collect(self.browser, safe_entry_url)
            jobs = (
                [job for job in collected_jobs if job_filter(job)]
                if job_filter is not None
                else collected_jobs
            )
            outcomes = [self.repository.upsert_with_result(job, run_id=run.id) for job in jobs]
            for job, outcome in zip(jobs, outcomes, strict=True):
                if outcome.inserted:
                    self.repository.create_alert(
                        outcome.job_id,
                        run_id=run.id,
                        kind="new",
                        message=f"Nova vaga: {job.title} — {job.company}",
                    )
                elif outcome.updated:
                    self.repository.create_alert(
                        outcome.job_id,
                        run_id=run.id,
                        kind="changed",
                        message=f"Vaga atualizada: {job.title} — {job.company}",
                    )
            inserted = sum(outcome.inserted for outcome in outcomes)
            updated = sum(outcome.updated for outcome in outcomes)
            self.repository.finish_run(
                run.id,
                found_count=len(jobs),
                inserted_count=inserted,
                updated_count=updated,
            )
            return CollectionResult(
                found=len(jobs),
                inserted=inserted,
                updated=updated,
                run_id=run.id,
                filtered=len(collected_jobs) - len(jobs),
            )
        except Exception as exc:
            self.repository.finish_run(run.id, error_message=str(exc))
            raise
