from datetime import timedelta

from quati.domain.job import utc_now
from quati.plugins import GreenhousePlugin
from quati.services import SearchScheduler
from quati.storage import SQLiteJobRepository


class FakeBrowser:
    def fetch_html(self, url: str, *, allowed_hosts: tuple[str, ...]) -> str:
        return """
        <h1>Acme</h1>
        <a data-testid="job-list__listitem-href" href="/jobs/1">
          <div><div>Analista</div><div>Remoto</div></div>
        </a>
        """


def test_scheduler_runs_due_search_once(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        schedule = repository.create_schedule(
            "greenhouse", "https://boards.greenhouse.io/acme", interval_minutes=15
        )
        results = SearchScheduler(repository, FakeBrowser()).run_due(
            {"greenhouse": GreenhousePlugin()}
        )
        updated = repository.get_schedule(schedule.id)

        assert results[0].inserted == 1
        assert updated.last_run_at is not None
        assert updated.next_run_at > utc_now() + timedelta(minutes=14)
        assert (
            SearchScheduler(repository, FakeBrowser()).run_due({"greenhouse": GreenhousePlugin()})
            == []
        )
    finally:
        repository.close()


def test_scheduler_isolates_failure_and_continues_other_searches(tmp_path) -> None:
    class SometimesFailingBrowser(FakeBrowser):
        def fetch_html(self, url: str, *, allowed_hosts: tuple[str, ...]) -> str:
            if "fail" in url:
                raise RuntimeError("falha esperada")
            return super().fetch_html(url, allowed_hosts=allowed_hosts)

    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        failed = repository.create_schedule(
            "greenhouse", "https://fail.greenhouse.io/acme", interval_minutes=15
        )
        successful = repository.create_schedule(
            "greenhouse", "https://boards.greenhouse.io/acme", interval_minutes=15
        )

        results = SearchScheduler(repository, SometimesFailingBrowser()).run_due(
            {"greenhouse": GreenhousePlugin()}
        )

        assert len(results) == 1
        assert repository.get_schedule(failed.id).last_run_at is not None
        assert repository.get_schedule(successful.id).last_run_at is not None
        assert {run.status for run in repository.list_runs()} == {"failed", "completed"}
    finally:
        repository.close()
