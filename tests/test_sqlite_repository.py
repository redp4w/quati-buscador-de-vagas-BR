import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from quati.domain import JobInput
from quati.storage import SQLiteJobRepository


def _job(title: str = "Analista de Dados") -> JobInput:
    return JobInput(
        source="gupy",
        external_id="abc-123",
        title=title,
        company="Acme",
        location="Remoto",
        url="https://acme.gupy.io/job/abc-123",
        description="SQL",
    )


def test_shared_repository_serializes_concurrent_writes(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "concurrent.sqlite3")

    def write(worker: int) -> None:
        for index in range(20):
            repository.upsert(
                JobInput(
                    source="gupy",
                    external_id=f"{worker}-{index}",
                    title="Cozinheiro",
                    company="Empresa",
                    location="Itu, SP",
                    url=f"https://empresa.gupy.io/jobs/{worker}-{index}",
                )
            )

    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(write, range(8)))

        assert repository.stats()["total_jobs"] == 160
    finally:
        repository.close()


def test_upsert_and_search_are_local_and_deduplicated(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        assert repository.upsert(_job()) is True
        assert repository.upsert(_job("Analista de Dados Sênior")) is False

        jobs = repository.list_jobs(query="Sênior")
        assert len(jobs) == 1
        assert jobs[0].title == "Analista de Dados Sênior"
        assert jobs[0].description == "SQL"
    finally:
        repository.close()


def test_search_input_is_bound_as_data_not_sql(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        repository.upsert(_job())
        assert repository.list_jobs(query="' OR 1=1 --") == []
        assert len(repository.list_jobs()) == 1
    finally:
        repository.close()


def test_run_and_revision_history_are_recorded(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        run = repository.start_run("gupy", "https://acme.gupy.io/")
        first = repository.upsert_with_result(_job(), run_id=run.id)
        second = repository.upsert_with_result(_job("Analista de Dados Sênior"), run_id=run.id)
        completed = repository.finish_run(run.id, found_count=2, inserted_count=1, updated_count=1)

        assert first.inserted and not first.updated
        assert not second.inserted and second.updated
        assert completed.status == "completed"
        assert completed.updated_count == 1
        assert repository.list_changes()[0].changed_fields == ("title",)
        assert repository.stats()["changes"] == 1
    finally:
        repository.close()


def test_migrates_legacy_jobs_database_without_losing_rows(tmp_path) -> None:
    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.execute(
        """
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
            title TEXT NOT NULL, company TEXT NOT NULL, location TEXT NOT NULL,
            url TEXT NOT NULL, description TEXT NOT NULL, published_at TEXT NOT NULL,
            content_hash TEXT NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
            UNIQUE(source, external_id)
        )
        """
    )
    connection.execute(
        """
        INSERT INTO jobs VALUES (1, 'gupy', 'old', 'Analista', 'Acme', 'Remoto',
        'https://acme.gupy.io/jobs/old', '', '', 'hash',
        '2026-08-07T00:00:00+00:00', '2026-08-07T00:00:00+00:00')
        """
    )
    connection.commit()
    connection.close()

    repository = SQLiteJobRepository(database)
    try:
        assert repository.list_jobs()[0].status == "active"
    finally:
        repository.close()


def test_deduplicates_equivalent_jobs_across_sources(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        repository.upsert(_job())
        repository.upsert(
            JobInput(
                source="linkedin",
                external_id="other-id",
                title="Analista de Dados",
                company="Acme",
                location="Remoto",
                url="https://www.linkedin.com/jobs/view/other-id",
            )
        )

        assert len(repository.list_jobs()) == 1
        assert len(repository.list_jobs(deduplicate=False)) == 2
    finally:
        repository.close()


def test_alerts_and_application_workflow_are_persisted(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        outcome = repository.upsert_with_result(_job())
        alert = repository.create_alert(
            outcome.job_id, run_id=None, kind="new", message="Nova vaga"
        )
        assert repository.list_alerts(unread_only=True)[0].id == alert.id
        repository.mark_all_alerts_read()
        assert repository.list_alerts(unread_only=True) == []

        application = repository.save_application(
            outcome.job_id, resume_id="resume-1", strategy="tailored"
        )
        assert application.status == "prepared"
        updated = repository.set_application_status(application.id, "submitted")
        assert updated.status == "submitted"
        assert repository.stats()["applications"] == 1
        repository.delete_application(application.id)
        assert repository.list_applications() == []
    finally:
        repository.close()


def test_schedule_can_be_removed_without_deleting_collected_jobs(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "schedules.sqlite3")
    try:
        repository.upsert(_job())
        schedule = repository.create_schedule(
            "gupy",
            "https://acme.gupy.io/",
            interval_minutes=1_440,
        )

        repository.delete_schedule(schedule.id)

        assert repository.list_schedules() == []
        assert len(repository.list_jobs()) == 1
    finally:
        repository.close()


def test_stale_jobs_are_archived_without_deletion_and_reactivated(tmp_path) -> None:
    repository = SQLiteJobRepository(tmp_path / "jobs.sqlite3")
    try:
        repository.upsert(_job())
        repository._connection.execute(
            "UPDATE jobs SET last_seen_at = ?",
            ("2026-01-01T00:00:00+00:00",),
        )
        repository._connection.commit()

        archived = repository.archive_stale_jobs(
            older_than_days=60, now=datetime(2026, 8, 10, tzinfo=UTC)
        )

        assert archived == 1
        assert repository.list_jobs()[0].status == "archived"
        assert repository.upsert(_job()) is False
        assert repository.list_jobs()[0].status == "active"
    finally:
        repository.close()
