from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from quati.security import EncryptedJSONVault


def _clean_secret(value: str, *, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} inválido.")
    secret = value.strip()
    if len(secret) > 512 or any(
        ord(character) < 33 or ord(character) == 127 for character in secret
    ):
        raise ValueError(f"{label} inválido.")
    return secret


@dataclass(frozen=True, slots=True)
class JobSourceConfiguration:
    """Credenciais opcionais de APIs de vagas, mantidas fora do histórico de buscas."""

    adzuna_app_id: str = ""
    adzuna_app_key: str = ""

    def __post_init__(self) -> None:
        app_id = _clean_secret(self.adzuna_app_id, label="App ID da Adzuna")
        app_key = _clean_secret(self.adzuna_app_key, label="App key da Adzuna")
        if bool(app_id) != bool(app_key):
            raise ValueError("Informe o App ID e a app key da Adzuna.")
        object.__setattr__(self, "adzuna_app_id", app_id)
        object.__setattr__(self, "adzuna_app_key", app_key)

    @property
    def adzuna_enabled(self) -> bool:
        return bool(self.adzuna_app_id and self.adzuna_app_key)


class JobSourceConfigurationVault:
    """Guarda chaves de APIs de busca em um cofre cifrado local."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._vault = EncryptedJSONVault(path, max_ciphertext_bytes=64 * 1024)

    def exists(self) -> bool:
        return self._vault.exists()

    def uses_current_format(self) -> bool:
        return self._vault.uses_current_format()

    def save(self, configuration: JobSourceConfiguration, passphrase: str) -> None:
        self._vault.save(
            {
                "version": 1,
                "adzuna_app_id": configuration.adzuna_app_id,
                "adzuna_app_key": configuration.adzuna_app_key,
            },
            passphrase,
        )

    def load(self, passphrase: str) -> JobSourceConfiguration:
        value = self._vault.load(passphrase)
        expected = {"version", "adzuna_app_id", "adzuna_app_key"}
        if not isinstance(value, dict) or set(value) != expected or value.get("version") != 1:
            raise ValueError("Configuração das fontes inválida.")
        if not all(isinstance(value[key], str) for key in expected - {"version"}):
            raise ValueError("Configuração das fontes inválida.")
        return JobSourceConfiguration(
            adzuna_app_id=value["adzuna_app_id"],
            adzuna_app_key=value["adzuna_app_key"],
        )
