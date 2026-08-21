from quati.domain import JobInput
from quati.ui.context import (
    _repository,
    get_repository,
    request_app_shutdown,
    reset_local_account,
    reset_private_vaults,
)


class _FakeSecretStore:
    def __init__(self) -> None:
        self.deleted = False

    def delete(self) -> None:
        self.deleted = True


def test_factory_reset_removes_only_known_local_data(tmp_path, monkeypatch) -> None:
    database = tmp_path / "quati.sqlite3"
    monkeypatch.setenv("QUATI_DB", str(database))
    _repository.clear()
    repository = get_repository()
    repository.upsert(
        JobInput(
            "gupy",
            "1",
            "Cozinheiro",
            "Empresa",
            "Itu, SP",
            "https://empresa.gupy.io/jobs/1",
        )
    )
    for filename in (
        "candidate-profile.enc",
        "candidate-resumes.enc",
        "ai-configuration.enc",
        "job-source-configuration.enc",
    ):
        (tmp_path / filename).write_bytes(b"dados-cifrados")
    unrelated = tmp_path / "nao-apagar.txt"
    unrelated.write_text("preservar", encoding="utf-8")
    secret_store = _FakeSecretStore()

    reset_local_account(secret_store=secret_store)  # type: ignore[arg-type]

    assert secret_store.deleted
    assert not database.exists()
    assert not (tmp_path / "candidate-profile.enc").exists()
    assert not (tmp_path / "candidate-resumes.enc").exists()
    assert not (tmp_path / "ai-configuration.enc").exists()
    assert not (tmp_path / "job-source-configuration.enc").exists()
    assert unrelated.read_text(encoding="utf-8") == "preservar"

    fresh_repository = get_repository()
    assert fresh_repository.stats()["total_jobs"] == 0
    fresh_repository.close()
    _repository.clear()


def test_private_reset_preserves_public_jobs_and_unrelated_files(tmp_path, monkeypatch) -> None:
    database = tmp_path / "quati.sqlite3"
    monkeypatch.setenv("QUATI_DB", str(database))
    _repository.clear()
    repository = get_repository()
    repository.upsert(
        JobInput(
            "gupy",
            "2",
            "Analista",
            "Empresa",
            "Itu, SP",
            "https://empresa.gupy.io/jobs/2",
        )
    )
    for filename in (
        "candidate-profile.enc",
        "candidate-resumes.enc",
        "ai-configuration.enc",
        "job-source-configuration.enc",
    ):
        (tmp_path / filename).write_bytes(b"dados-cifrados")
    unrelated = tmp_path / "nao-apagar.txt"
    unrelated.write_text("preservar", encoding="utf-8")
    secret_store = _FakeSecretStore()

    reset_private_vaults(secret_store=secret_store)  # type: ignore[arg-type]

    assert secret_store.deleted
    assert database.exists()
    assert get_repository().stats()["total_jobs"] == 1
    assert unrelated.read_text(encoding="utf-8") == "preservar"
    assert not list(tmp_path.glob("*.enc"))
    get_repository().close()
    _repository.clear()


def test_shutdown_request_stays_next_to_local_database(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUATI_DB", str(tmp_path / "quati.sqlite3"))

    request_app_shutdown()

    assert (tmp_path / "shutdown.request").read_text(encoding="ascii") == "shutdown\n"
