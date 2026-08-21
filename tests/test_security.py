import json

import pytest

from quati.security import DeviceSecretStore, EncryptedJSONVault, validate_local_passphrase


def test_device_secret_is_created_once_and_not_written_to_project(tmp_path) -> None:
    storage: dict[tuple[str, str], str] = {}

    def get_password(service: str, username: str) -> str | None:
        return storage.get((service, username))

    def set_password(service: str, username: str, password: str) -> None:
        storage[(service, username)] = password

    store = DeviceSecretStore(get_password, set_password, available=lambda: True)

    first = store.get_or_create()
    second = store.get_or_create()

    assert first == second
    assert len(first) >= 48
    assert list(tmp_path.iterdir()) == []


def test_device_secret_can_be_deleted_without_creating_another() -> None:
    storage = {("QUATI/local-vault", "device-key"): "segredo"}

    def get_password(service: str, username: str) -> str | None:
        return storage.get((service, username))

    def set_password(service: str, username: str, password: str) -> None:
        storage[(service, username)] = password

    def delete_password(service: str, username: str) -> None:
        storage.pop((service, username), None)

    store = DeviceSecretStore(
        get_password,
        set_password,
        delete_password,
        available=lambda: True,
    )

    store.delete()

    assert storage == {}


def test_legacy_device_secret_is_moved_and_removed() -> None:
    storage = {("JobHunterBR/local-vault", "device-key"): "segredo-antigo"}

    def get_password(service: str, username: str) -> str | None:
        return storage.get((service, username))

    def set_password(service: str, username: str, password: str) -> None:
        storage[(service, username)] = password

    def delete_password(service: str, username: str) -> None:
        storage.pop((service, username), None)

    store = DeviceSecretStore(
        get_password,
        set_password,
        delete_password,
        available=lambda: True,
    )

    assert store.get_or_create() == "segredo-antigo"
    assert storage == {("QUATI/local-vault", "device-key"): "segredo-antigo"}


def test_new_vaults_use_versioned_argon2id_format(tmp_path) -> None:
    path = tmp_path / "profile.enc"
    vault = EncryptedJSONVault(path)

    vault.save({"name": "Ana"}, "senha-local-segura")

    assert path.read_bytes().startswith(b"QUATI\x00\x02\x00")
    assert vault.load("senha-local-segura") == {"name": "Ana"}


def test_local_passphrase_has_no_minimum_length() -> None:
    validate_local_passphrase("x")

    with pytest.raises(ValueError):
        validate_local_passphrase("")


def test_legacy_pbkdf2_vault_remains_readable(tmp_path) -> None:
    path = tmp_path / "legacy.enc"
    vault = EncryptedJSONVault(path)
    salt = bytes(range(16))
    payload = json.dumps({"legacy": True}).encode("utf-8")
    path.write_bytes(salt + vault._legacy_fernet("senha-local-segura", salt).encrypt(payload))

    assert vault.load("senha-local-segura") == {"legacy": True}
