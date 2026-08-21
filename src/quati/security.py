from __future__ import annotations

import base64
import json
import os
import secrets
import tempfile
from collections.abc import Callable
from pathlib import Path
from threading import Lock

import keyring
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from keyring.errors import KeyringError

_SALT_BYTES = 16
_LEGACY_KDF_ITERATIONS = 600_000
_VAULT_V2_MAGIC = b"QUATI\x00\x02\x00"
_ARGON2_ITERATIONS = 3
_ARGON2_LANES = 4
_ARGON2_MEMORY_KIB = 64 * 1024
_DEVICE_SECRET_LOCK = Lock()
# Estes valores identificam o registro do keyring; não são credenciais.
_DEVICE_KEYRING_SERVICE = "QUATI/local-vault"
_LEGACY_KEYRING_SERVICE = "JobHunterBR/local-vault"
_DEVICE_KEYRING_ACCOUNT = "device-key"


def validate_local_passphrase(passphrase: str) -> None:
    if not isinstance(passphrase, str) or not 1 <= len(passphrase) <= 1_024:
        raise ValueError("Use uma senha local com até 1.024 caracteres.")


def _keyring_available() -> bool:
    return getattr(keyring.get_keyring(), "priority", 0) > 0


class DeviceSecretStore:
    """Chave aleatória guardada pelo cofre seguro do sistema operacional."""

    def __init__(
        self,
        getter: Callable[[str, str], str | None] = keyring.get_password,
        setter: Callable[[str, str, str], None] = keyring.set_password,
        deleter: Callable[[str, str], None] = keyring.delete_password,
        available: Callable[[], bool] = _keyring_available,
    ) -> None:
        self._getter = getter
        self._setter = setter
        self._deleter = deleter
        self._available = available

    def get_or_create(self) -> str:
        try:
            if not self._available():
                raise ValueError("O cofre seguro do sistema operacional não está disponível.")
            with _DEVICE_SECRET_LOCK:
                existing = self._getter(_DEVICE_KEYRING_SERVICE, _DEVICE_KEYRING_ACCOUNT)
                if existing:
                    return existing
                legacy = self._getter(_LEGACY_KEYRING_SERVICE, _DEVICE_KEYRING_ACCOUNT)
                if legacy:
                    self._setter(_DEVICE_KEYRING_SERVICE, _DEVICE_KEYRING_ACCOUNT, legacy)
                    if self._getter(_DEVICE_KEYRING_SERVICE, _DEVICE_KEYRING_ACCOUNT) != legacy:
                        raise ValueError("Não foi possível migrar a chave do cofre do sistema.")
                    self._deleter(_LEGACY_KEYRING_SERVICE, _DEVICE_KEYRING_ACCOUNT)
                    if self._getter(_LEGACY_KEYRING_SERVICE, _DEVICE_KEYRING_ACCOUNT) is not None:
                        raise ValueError("Não foi possível remover a chave antiga do sistema.")
                    return legacy
                generated = secrets.token_urlsafe(48)
                self._setter(
                    _DEVICE_KEYRING_SERVICE,
                    _DEVICE_KEYRING_ACCOUNT,
                    generated,
                )
                stored = self._getter(_DEVICE_KEYRING_SERVICE, _DEVICE_KEYRING_ACCOUNT)
                if stored != generated:
                    raise ValueError("Não foi possível confirmar a chave no cofre do sistema.")
                return generated
        except KeyringError as exc:
            raise ValueError(
                "O cofre seguro do sistema operacional falhou. Use uma senha local."
            ) from exc

    def delete(self) -> None:
        """Remove a chave local do sistema sem criar uma nova."""
        try:
            if not self._available():
                return
            with _DEVICE_SECRET_LOCK:
                for service in (_DEVICE_KEYRING_SERVICE, _LEGACY_KEYRING_SERVICE):
                    existing = self._getter(service, _DEVICE_KEYRING_ACCOUNT)
                    if existing is None:
                        continue
                    self._deleter(service, _DEVICE_KEYRING_ACCOUNT)
                    if self._getter(service, _DEVICE_KEYRING_ACCOUNT) is not None:
                        raise ValueError("Não foi possível remover a chave do cofre do sistema.")
        except KeyringError as exc:
            raise ValueError("Não foi possível limpar o cofre seguro do sistema.") from exc


class EncryptedJSONVault:
    """Arquivo JSON cifrado com gravação atômica e senha não persistida."""

    def __init__(self, path: Path, *, max_ciphertext_bytes: int = 80 * 1024 * 1024) -> None:
        self.path = path
        self.max_ciphertext_bytes = max_ciphertext_bytes

    def exists(self) -> bool:
        return self.path.is_file()

    def uses_current_format(self) -> bool:
        if not self.exists():
            return False
        with self.path.open("rb") as handle:
            return handle.read(len(_VAULT_V2_MAGIC)) == _VAULT_V2_MAGIC

    def save(self, value: object, passphrase: str) -> None:
        validate_local_passphrase(passphrase)
        payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(payload) > self.max_ciphertext_bytes:
            raise ValueError("O cofre local excedeu o limite permitido.")
        salt = os.urandom(_SALT_BYTES)
        encrypted = _VAULT_V2_MAGIC + salt + self._fernet(passphrase, salt).encrypt(payload)
        if len(encrypted) > self.max_ciphertext_bytes:
            raise ValueError("O cofre local excedeu o limite permitido.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            if os.name != "nt":
                temporary.chmod(0o600)
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self, passphrase: str) -> object:
        validate_local_passphrase(passphrase)
        try:
            size = self.path.stat().st_size
        except FileNotFoundError as exc:
            raise ValueError("Cofre local ainda não foi criado.") from exc
        if size <= _SALT_BYTES or size > self.max_ciphertext_bytes:
            raise ValueError("Cofre local inválido.")
        with self.path.open("rb") as handle:
            payload = handle.read(self.max_ciphertext_bytes + 1)
        if len(payload) != size or len(payload) > self.max_ciphertext_bytes:
            raise ValueError("Cofre local inválido.")
        try:
            if payload.startswith(_VAULT_V2_MAGIC):
                salt_start = len(_VAULT_V2_MAGIC)
                token_start = salt_start + _SALT_BYTES
                if len(payload) <= token_start:
                    raise ValueError("Cofre local inválido.")
                clear = self._fernet(
                    passphrase, payload[salt_start:token_start]
                ).decrypt(payload[token_start:])
            else:
                clear = self._legacy_fernet(
                    passphrase, payload[:_SALT_BYTES]
                ).decrypt(payload[_SALT_BYTES:])
            return json.loads(clear)
        except (InvalidToken, json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise ValueError("Senha local incorreta ou cofre inválido.") from exc

    @staticmethod
    def _fernet(passphrase: str, salt: bytes) -> Fernet:
        derived = Argon2id(
            salt=salt,
            length=32,
            iterations=_ARGON2_ITERATIONS,
            lanes=_ARGON2_LANES,
            memory_cost=_ARGON2_MEMORY_KIB,
            ad=_VAULT_V2_MAGIC,
        ).derive(passphrase.encode("utf-8"))
        return Fernet(base64.urlsafe_b64encode(derived))

    @staticmethod
    def _legacy_fernet(passphrase: str, salt: bytes) -> Fernet:
        derived = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_LEGACY_KDF_ITERATIONS,
        ).derive(passphrase.encode("utf-8"))
        return Fernet(base64.urlsafe_b64encode(derived))
