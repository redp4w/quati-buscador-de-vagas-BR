from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from threading import RLock

from quati.domain import JobInput, JobRecord, job_dedupe_key
from quati.domain.job import clean_text, utc_now


def _serialized(method):
    """Impede transações simultâneas na conexão compartilhada entre sessões Streamlit."""

    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._connection_lock:
            return method(self, *args, **kwargs)

    return wrapper


@dataclass(frozen=True, slots=True)
class UpsertResult:
    job_id: int
    inserted: bool
    updated: bool


@dataclass(frozen=True, slots=True)
class CollectionRun:
    id: int
    source: str
    entry_url: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    found_count: int
    inserted_count: int
    updated_count: int
    error_message: str

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> CollectionRun:
        return cls(
            id=row["id"],
            source=row["source"],
            entry_url=row["entry_url"],
            status=row["status"],
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
            found_count=row["found_count"],
            inserted_count=row["inserted_count"],
            updated_count=row["updated_count"],
            error_message=row["error_message"],
        )


@dataclass(frozen=True, slots=True)
class JobChange:
    id: int
    job_id: int
    run_id: int | None
    changed_at: datetime
    changed_fields: tuple[str, ...]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> JobChange:
        return cls(
            id=row["id"],
            job_id=row["job_id"],
            run_id=row["run_id"],
            changed_at=datetime.fromisoformat(row["changed_at"]),
            changed_fields=tuple(json.loads(row["changed_fields"])),
        )


@dataclass(frozen=True, slots=True)
class SearchSchedule:
    id: int
    source: str
    entry_url: str
    interval_minutes: int
    enabled: bool
    last_run_at: datetime | None
    next_run_at: datetime

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> SearchSchedule:
        return cls(
            id=row["id"],
            source=row["source"],
            entry_url=row["entry_url"],
            interval_minutes=row["interval_minutes"],
            enabled=bool(row["enabled"]),
            last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
            next_run_at=datetime.fromisoformat(row["next_run_at"]),
        )


@dataclass(frozen=True, slots=True)
class JobAlert:
    id: int
    job_id: int
    run_id: int | None
    kind: str
    message: str
    created_at: datetime
    read: bool

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> JobAlert:
        return cls(
            id=row["id"],
            job_id=row["job_id"],
            run_id=row["run_id"],
            kind=row["kind"],
            message=row["message"],
            created_at=datetime.fromisoformat(row["created_at"]),
            read=bool(row["is_read"]),
        )


@dataclass(frozen=True, slots=True)
class ApplicationRecord:
    id: int
    job_id: int
    resume_id: str
    strategy: str
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> ApplicationRecord:
        return cls(
            id=row["id"],
            job_id=row["job_id"],
            resume_id=row["resume_id"],
            strategy=row["strategy"],
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


_APPLICATION_STRATEGIES = frozenset({"standard", "tailored"})
_APPLICATION_STATUSES = frozenset(
    {"saved", "prepared", "opened", "submitted", "interview", "rejected", "offer", "withdrawn"}
)


class SQLiteJobRepository:
    """Banco local com SQL parametrizado, histórico e migração sem perda de dados."""

    def __init__(self, database_path: Path | str) -> None:
        self.path = Path(database_path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection_lock = RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute("PRAGMA journal_mode = WAL")
        self._connection.execute("PRAGMA busy_timeout = 5000")
        self._create_schema()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    external_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT NOT NULL,
                    published_at TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    last_run_id INTEGER,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    UNIQUE(source, external_id)
                )
                """
            )
            self._ensure_column("jobs", "status", "TEXT NOT NULL DEFAULT 'active'")
            self._ensure_column("jobs", "last_run_id", "INTEGER")
            self._ensure_column("jobs", "dedupe_key", "TEXT NOT NULL DEFAULT ''")
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS collection_runs (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    entry_url TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('running', 'completed', 'failed')),
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    found_count INTEGER NOT NULL DEFAULT 0,
                    inserted_count INTEGER NOT NULL DEFAULT 0,
                    updated_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT NOT NULL DEFAULT ''
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_revisions (
                    id INTEGER PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    run_id INTEGER REFERENCES collection_runs(id) ON DELETE SET NULL,
                    changed_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    current_hash TEXT NOT NULL,
                    changed_fields TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS search_schedules (
                    id INTEGER PRIMARY KEY,
                    source TEXT NOT NULL,
                    entry_url TEXT NOT NULL,
                    interval_minutes INTEGER NOT NULL CHECK(interval_minutes BETWEEN 15 AND 10080),
                    enabled INTEGER NOT NULL DEFAULT 1 CHECK(enabled IN (0, 1)),
                    last_run_at TEXT,
                    next_run_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_last_seen ON jobs(last_seen_at DESC)"
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_collection_runs_started "
                "ON collection_runs(started_at DESC)"
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_revisions_job "
                "ON job_revisions(job_id, changed_at DESC)"
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_search_schedules_due "
                "ON search_schedules(enabled, next_run_at)"
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_alerts (
                    id INTEGER PRIMARY KEY,
                    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    run_id INTEGER REFERENCES collection_runs(id) ON DELETE SET NULL,
                    kind TEXT NOT NULL CHECK(kind IN ('new', 'changed')),
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0 CHECK(is_read IN (0, 1)),
                    UNIQUE(job_id, run_id, kind)
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY,
                    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
                    resume_id TEXT NOT NULL DEFAULT '',
                    strategy TEXT NOT NULL CHECK(strategy IN ('standard', 'tailored')),
                    status TEXT NOT NULL CHECK(status IN (
                        'saved', 'prepared', 'opened', 'submitted', 'interview',
                        'rejected', 'offer', 'withdrawn'
                    )),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_dedupe ON jobs(dedupe_key, last_seen_at DESC)"
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_job_alerts_unread "
                "ON job_alerts(is_read, created_at DESC)"
            )
            self._connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_applications_status "
                "ON applications(status, updated_at DESC)"
            )
            self._backfill_dedupe_keys()

    def _ensure_column(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self._connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self._connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def _backfill_dedupe_keys(self) -> None:
        rows = self._connection.execute(
            "SELECT id, title, company, location FROM jobs WHERE dedupe_key = ''"
        ).fetchall()
        for row in rows:
            self._connection.execute(
                "UPDATE jobs SET dedupe_key = ? WHERE id = ?",
                (job_dedupe_key(row["title"], row["company"], row["location"]), row["id"]),
            )

    @_serialized
    def start_run(self, source: str, entry_url: str) -> CollectionRun:
        timestamp = utc_now().isoformat()
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO collection_runs (source, entry_url, status, started_at)
                VALUES (?, ?, 'running', ?)
                """,
                (
                    clean_text(source, max_length=32),
                    clean_text(entry_url, max_length=2_048),
                    timestamp,
                ),
            )
        return self.get_run(cursor.lastrowid)

    @_serialized
    def finish_run(
        self,
        run_id: int,
        *,
        found_count: int = 0,
        inserted_count: int = 0,
        updated_count: int = 0,
        error_message: str = "",
    ) -> CollectionRun:
        status = "failed" if error_message else "completed"
        with self._connection:
            self._connection.execute(
                """
                UPDATE collection_runs
                SET status = ?, completed_at = ?, found_count = ?, inserted_count = ?,
                    updated_count = ?, error_message = ?
                WHERE id = ? AND status = 'running'
                """,
                (
                    status,
                    utc_now().isoformat(),
                    max(found_count, 0),
                    max(inserted_count, 0),
                    max(updated_count, 0),
                    clean_text(error_message, max_length=500),
                    run_id,
                ),
            )
        return self.get_run(run_id)

    @_serialized
    def get_run(self, run_id: int) -> CollectionRun:
        row = self._connection.execute(
            "SELECT * FROM collection_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if not row:
            raise ValueError("Coleta não encontrada.")
        return CollectionRun.from_row(row)

    @_serialized
    def list_runs(self, *, limit: int = 50) -> list[CollectionRun]:
        safe_limit = min(max(limit, 1), 500)
        rows = self._connection.execute(
            "SELECT * FROM collection_runs ORDER BY started_at DESC LIMIT ?", (safe_limit,)
        ).fetchall()
        return [CollectionRun.from_row(row) for row in rows]

    @_serialized
    def upsert(self, job: JobInput) -> bool:
        """Compatibilidade: retorna True somente para vagas novas."""
        return self.upsert_with_result(job).inserted

    @_serialized
    def upsert_with_result(self, job: JobInput, *, run_id: int | None = None) -> UpsertResult:
        timestamp = utc_now().isoformat()
        tracked_fields = ("title", "company", "location", "url", "description", "published_at")
        with self._connection:
            existing = self._connection.execute(
                "SELECT * FROM jobs WHERE source = ? AND external_id = ?",
                (job.source, job.external_id),
            ).fetchone()
            if existing is None:
                cursor = self._connection.execute(
                    """
                    INSERT INTO jobs (
                        source, external_id, title, company, location, url, description,
                        published_at, content_hash, dedupe_key, status, last_run_id,
                        first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                    """,
                    (
                        job.source,
                        job.external_id,
                        job.title,
                        job.company,
                        job.location,
                        job.url,
                        job.description,
                        job.published_at,
                        job.content_hash,
                        job.dedupe_key,
                        run_id,
                        timestamp,
                        timestamp,
                    ),
                )
                return UpsertResult(job_id=cursor.lastrowid, inserted=True, updated=False)

            changed_fields = tuple(
                field for field in tracked_fields if existing[field] != getattr(job, field)
            )
            updated = bool(changed_fields)
            self._connection.execute(
                """
                UPDATE jobs
                SET title = ?, company = ?, location = ?, url = ?, description = ?,
                    published_at = ?, content_hash = ?, dedupe_key = ?, status = 'active',
                    last_run_id = ?, last_seen_at = ?
                WHERE id = ?
                """,
                (
                    job.title,
                    job.company,
                    job.location,
                    job.url,
                    job.description,
                    job.published_at,
                    job.content_hash,
                    job.dedupe_key,
                    run_id,
                    timestamp,
                    existing["id"],
                ),
            )
            if updated:
                self._connection.execute(
                    """
                    INSERT INTO job_revisions (
                        job_id, run_id, changed_at, previous_hash, current_hash, changed_fields
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        existing["id"],
                        run_id,
                        timestamp,
                        existing["content_hash"],
                        job.content_hash,
                        json.dumps(changed_fields),
                    ),
                )
            return UpsertResult(job_id=existing["id"], inserted=False, updated=updated)

    @_serialized
    def list_changes(self, *, limit: int = 100) -> list[JobChange]:
        safe_limit = min(max(limit, 1), 500)
        rows = self._connection.execute(
            "SELECT * FROM job_revisions ORDER BY changed_at DESC LIMIT ?", (safe_limit,)
        ).fetchall()
        return [JobChange.from_row(row) for row in rows]

    @_serialized
    def create_schedule(
        self, source: str, entry_url: str, *, interval_minutes: int
    ) -> SearchSchedule:
        if not 15 <= interval_minutes <= 10_080:
            raise ValueError("O intervalo deve estar entre 15 minutos e 7 dias.")
        timestamp = utc_now().isoformat()
        with self._connection:
            cursor = self._connection.execute(
                """
                INSERT INTO search_schedules (source, entry_url, interval_minutes, next_run_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    clean_text(source, max_length=32),
                    clean_text(entry_url, max_length=2_048),
                    interval_minutes,
                    timestamp,
                ),
            )
        return self.get_schedule(cursor.lastrowid)

    @_serialized
    def get_schedule(self, schedule_id: int) -> SearchSchedule:
        row = self._connection.execute(
            "SELECT * FROM search_schedules WHERE id = ?", (schedule_id,)
        ).fetchone()
        if not row:
            raise ValueError("Agendamento não encontrado.")
        return SearchSchedule.from_row(row)

    @_serialized
    def list_schedules(self, *, enabled_only: bool = False) -> list[SearchSchedule]:
        query = "SELECT * FROM search_schedules"
        parameters: tuple[object, ...] = ()
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY next_run_at ASC"
        rows = self._connection.execute(query, parameters).fetchall()
        return [SearchSchedule.from_row(row) for row in rows]

    @_serialized
    def due_schedules(self, *, now: datetime | None = None) -> list[SearchSchedule]:
        timestamp = (now or utc_now()).isoformat()
        rows = self._connection.execute(
            """
            SELECT * FROM search_schedules
            WHERE enabled = 1 AND next_run_at <= ?
            ORDER BY next_run_at ASC
            """,
            (timestamp,),
        ).fetchall()
        return [SearchSchedule.from_row(row) for row in rows]

    @_serialized
    def mark_schedule_run(self, schedule_id: int, *, now: datetime | None = None) -> SearchSchedule:
        current = self.get_schedule(schedule_id)
        timestamp = now or utc_now()
        next_run = timestamp.timestamp() + current.interval_minutes * 60
        next_timestamp = datetime.fromtimestamp(next_run, tz=timestamp.tzinfo).isoformat()
        with self._connection:
            self._connection.execute(
                """
                UPDATE search_schedules SET last_run_at = ?, next_run_at = ?
                WHERE id = ?
                """,
                (timestamp.isoformat(), next_timestamp, schedule_id),
            )
        return self.get_schedule(schedule_id)

    @_serialized
    def set_schedule_enabled(self, schedule_id: int, enabled: bool) -> SearchSchedule:
        with self._connection:
            self._connection.execute(
                "UPDATE search_schedules SET enabled = ? WHERE id = ?",
                (int(enabled), schedule_id),
            )
        return self.get_schedule(schedule_id)

    @_serialized
    def delete_schedule(self, schedule_id: int) -> None:
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM search_schedules WHERE id = ?",
                (schedule_id,),
            )
        if cursor.rowcount != 1:
            raise ValueError("Agendamento não encontrado.")

    @_serialized
    def create_alert(self, job_id: int, *, run_id: int | None, kind: str, message: str) -> JobAlert:
        if kind not in {"new", "changed"}:
            raise ValueError("Tipo de alerta inválido.")
        with self._connection:
            self._connection.execute(
                """
                INSERT OR IGNORE INTO job_alerts (
                    job_id, run_id, kind, message, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    run_id,
                    kind,
                    clean_text(message, max_length=500),
                    utc_now().isoformat(),
                ),
            )
        row = self._connection.execute(
            """
            SELECT * FROM job_alerts
            WHERE job_id = ? AND run_id IS ? AND kind = ?
            ORDER BY id DESC LIMIT 1
            """,
            (job_id, run_id, kind),
        ).fetchone()
        if not row:
            raise RuntimeError("Não foi possível registrar o alerta.")
        return JobAlert.from_row(row)

    @_serialized
    def list_alerts(self, *, unread_only: bool = False, limit: int = 100) -> list[JobAlert]:
        safe_limit = min(max(limit, 1), 500)
        query = "SELECT * FROM job_alerts"
        if unread_only:
            query += " WHERE is_read = 0"
        query += " ORDER BY created_at DESC LIMIT ?"
        rows = self._connection.execute(query, (safe_limit,)).fetchall()
        return [JobAlert.from_row(row) for row in rows]

    @_serialized
    def mark_alert_read(self, alert_id: int, *, read: bool = True) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE job_alerts SET is_read = ? WHERE id = ?", (int(read), alert_id)
            )

    @_serialized
    def mark_all_alerts_read(self) -> None:
        with self._connection:
            self._connection.execute("UPDATE job_alerts SET is_read = 1 WHERE is_read = 0")

    @_serialized
    def save_application(
        self,
        job_id: int,
        *,
        resume_id: str = "",
        strategy: str = "standard",
        status: str = "prepared",
    ) -> ApplicationRecord:
        if strategy not in _APPLICATION_STRATEGIES:
            raise ValueError("Estratégia de currículo inválida.")
        if status not in _APPLICATION_STATUSES:
            raise ValueError("Status de candidatura inválido.")
        self.get_job(job_id)
        timestamp = utc_now().isoformat()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO applications (
                    job_id, resume_id, strategy, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    resume_id = excluded.resume_id,
                    strategy = excluded.strategy,
                    status = excluded.status,
                    updated_at = excluded.updated_at
                """,
                (
                    job_id,
                    clean_text(resume_id, max_length=64),
                    strategy,
                    status,
                    timestamp,
                    timestamp,
                ),
            )
        return self.get_application_for_job(job_id)

    @_serialized
    def get_application_for_job(self, job_id: int) -> ApplicationRecord:
        row = self._connection.execute(
            "SELECT * FROM applications WHERE job_id = ?", (job_id,)
        ).fetchone()
        if not row:
            raise ValueError("Candidatura não encontrada.")
        return ApplicationRecord.from_row(row)

    @_serialized
    def list_applications(self, *, limit: int = 500) -> list[ApplicationRecord]:
        safe_limit = min(max(limit, 1), 1_000)
        rows = self._connection.execute(
            "SELECT * FROM applications ORDER BY updated_at DESC LIMIT ?", (safe_limit,)
        ).fetchall()
        return [ApplicationRecord.from_row(row) for row in rows]

    @_serialized
    def set_application_status(self, application_id: int, status: str) -> ApplicationRecord:
        if status not in _APPLICATION_STATUSES:
            raise ValueError("Status de candidatura inválido.")
        with self._connection:
            self._connection.execute(
                "UPDATE applications SET status = ?, updated_at = ? WHERE id = ?",
                (status, utc_now().isoformat(), application_id),
            )
        row = self._connection.execute(
            "SELECT * FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not row:
            raise ValueError("Candidatura não encontrada.")
        return ApplicationRecord.from_row(row)

    @_serialized
    def delete_application(self, application_id: int) -> None:
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM applications WHERE id = ?", (application_id,)
            )
        if cursor.rowcount != 1:
            raise ValueError("Vaga preparada não encontrada.")

    @_serialized
    def archive_stale_jobs(self, *, older_than_days: int = 60, now: datetime | None = None) -> int:
        """Arquiva sem apagar; uma nova coleta reativa a vaga automaticamente."""
        if not 7 <= older_than_days <= 3_650:
            raise ValueError("O prazo de arquivamento deve estar entre 7 e 3650 dias.")
        cutoff = (now or utc_now()) - timedelta(days=older_than_days)
        with self._connection:
            cursor = self._connection.execute(
                """
                UPDATE jobs SET status = 'archived'
                WHERE status = 'active' AND last_seen_at < ?
                """,
                (cutoff.isoformat(),),
            )
        return max(cursor.rowcount, 0)

    @_serialized
    def stats(self) -> dict[str, int]:
        row = self._connection.execute(
            """
            SELECT COUNT(*) AS total, SUM(status = 'active') AS active
            FROM jobs
            """
        ).fetchone()
        changes = self._connection.execute("SELECT COUNT(*) AS total FROM job_revisions").fetchone()
        alerts = self._connection.execute(
            "SELECT COUNT(*) AS total FROM job_alerts WHERE is_read = 0"
        ).fetchone()
        applications = self._connection.execute(
            "SELECT COUNT(*) AS total FROM applications"
        ).fetchone()
        return {
            "total_jobs": row["total"],
            "active_jobs": row["active"] or 0,
            "changes": changes["total"],
            "unread_alerts": alerts["total"],
            "applications": applications["total"],
        }

    @_serialized
    def list_jobs(
        self, *, query: str = "", limit: int = 100, deduplicate: bool = True
    ) -> list[JobRecord]:
        safe_limit = min(max(limit, 1), 500)
        search = clean_text(query, max_length=200)
        if search:
            pattern = f"%{search}%"
            if deduplicate:
                rows = self._connection.execute(
                    """
                    SELECT * FROM jobs
                    WHERE (title LIKE ? OR company LIKE ? OR location LIKE ?)
                    AND id IN (SELECT MAX(id) FROM jobs GROUP BY dedupe_key)
                    ORDER BY last_seen_at DESC LIMIT ?
                    """,
                    (pattern, pattern, pattern, safe_limit),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    """
                    SELECT * FROM jobs
                    WHERE title LIKE ? OR company LIKE ? OR location LIKE ?
                    ORDER BY last_seen_at DESC LIMIT ?
                    """,
                    (pattern, pattern, pattern, safe_limit),
                ).fetchall()
        else:
            if deduplicate:
                rows = self._connection.execute(
                    """
                    SELECT * FROM jobs
                    WHERE id IN (SELECT MAX(id) FROM jobs GROUP BY dedupe_key)
                    ORDER BY last_seen_at DESC LIMIT ?
                    """,
                    (safe_limit,),
                ).fetchall()
            else:
                rows = self._connection.execute(
                    "SELECT * FROM jobs ORDER BY last_seen_at DESC LIMIT ?",
                    (safe_limit,),
                ).fetchall()
        return [JobRecord.from_row(row) for row in rows]

    @_serialized
    def get_job(self, job_id: int) -> JobRecord:
        row = self._connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            raise ValueError("Vaga não encontrada.")
        return JobRecord.from_row(row)

    @_serialized
    def close(self) -> None:
        self._connection.close()
