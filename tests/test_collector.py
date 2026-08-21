from quati.plugins import GreenhousePlugin
from quati.services import JobCollector
from quati.storage import SQLiteJobRepository


class FakeBrowser:
    def fetch_html(self, url: str, *, allowed_hosts: tuple[str, ...]) -> str:
        assert url == "https://boards.greenhouse.io/acme"
        assert allowed_hosts == ("greenhouse.io",)
        return """
        <h1>Acme</h1>
        <a href="/acme/jobs/101">Analista de SOC I - Monitoramento</a>
        """


def test_collects_and_persists_a_public_job(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        result = JobCollector(repository, FakeBrowser()).collect(
            GreenhousePlugin(), "https://boards.greenhouse.io/acme"
        )

        assert result.found == 1
        assert result.inserted == 1
        assert repository.list_jobs()[0].title == "Analista de SOC I - Monitoramento"
        assert repository.list_alerts(unread_only=True)[0].kind == "new"
    finally:
        repository.close()


def test_filters_jobs_before_persisting(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        result = JobCollector(repository, FakeBrowser()).collect(
            GreenhousePlugin(),
            "https://boards.greenhouse.io/acme",
            job_filter=lambda job: False,
        )

        assert result.found == 0
        assert result.filtered == 1
        assert repository.list_jobs() == []
    finally:
        repository.close()
