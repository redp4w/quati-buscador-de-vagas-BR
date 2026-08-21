from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from quati.domain.job import clean_text
from quati.security import EncryptedJSONVault

from .service import ResumeDocument, extract_resume, normalize_resume_text

_MAX_RESUMES = 20
_MAX_TOTAL_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class StoredResume:
    id: str
    label: str
    filename: str
    content: bytes
    text: str
    created_at: datetime
    content_hash: str

    def as_document(self) -> ResumeDocument:
        return ResumeDocument(filename=self.filename, text=self.text)


class ResumeVault:
    """Biblioteca de currículos cifrada; nenhum arquivo é salvo em texto claro."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._vault = EncryptedJSONVault(path)

    def exists(self) -> bool:
        return self._vault.exists()

    def uses_current_format(self) -> bool:
        return self._vault.uses_current_format()

    def load(self, passphrase: str) -> list[StoredResume]:
        if not self.exists():
            return []
        payload = self._vault.load(passphrase)
        if not isinstance(payload, dict) or payload.get("version") != 1:
            raise ValueError("Biblioteca de currículos inválida.")
        items = payload.get("resumes")
        if not isinstance(items, list) or len(items) > _MAX_RESUMES:
            raise ValueError("Biblioteca de currículos inválida.")
        resumes = [self._decode(item) for item in items]
        if sum(len(item.content) for item in resumes) > _MAX_TOTAL_BYTES:
            raise ValueError("Biblioteca de currículos excedeu o limite permitido.")
        return resumes

    def add(self, passphrase: str, *, label: str, filename: str, content: bytes) -> StoredResume:
        safe_label = clean_text(label, max_length=100)
        if not safe_label:
            raise ValueError("Informe um nome para o currículo.")
        document = extract_resume(filename, content)
        resumes = self.load(passphrase)
        digest = sha256(content).hexdigest()
        if any(item.content_hash == digest for item in resumes):
            raise ValueError("Este currículo já está na biblioteca.")
        if len(resumes) >= _MAX_RESUMES:
            raise ValueError("A biblioteca aceita no máximo 20 currículos.")
        if sum(len(item.content) for item in resumes) + len(content) > _MAX_TOTAL_BYTES:
            raise ValueError("A biblioteca aceita no máximo 50 MB no total.")
        stored = StoredResume(
            id=uuid4().hex,
            label=safe_label,
            filename=document.filename,
            content=bytes(content),
            text=document.text,
            created_at=datetime.now(UTC).replace(microsecond=0),
            content_hash=digest,
        )
        self.save([*resumes, stored], passphrase)
        return stored

    def delete(self, passphrase: str, resume_id: str) -> None:
        resumes = self.load(passphrase)
        remaining = [item for item in resumes if item.id != resume_id]
        if len(remaining) == len(resumes):
            raise ValueError("Currículo não encontrado.")
        self.save(remaining, passphrase)

    def save(self, resumes: list[StoredResume], passphrase: str) -> None:
        self._vault.save(
            {"version": 1, "resumes": [self._encode(item) for item in resumes]},
            passphrase,
        )

    @staticmethod
    def _encode(resume: StoredResume) -> dict[str, str]:
        return {
            "id": resume.id,
            "label": resume.label,
            "filename": resume.filename,
            "content": base64.b64encode(resume.content).decode("ascii"),
            "text": resume.text,
            "created_at": resume.created_at.isoformat(),
            "content_hash": resume.content_hash,
        }

    @staticmethod
    def _decode(value: object) -> StoredResume:
        if not isinstance(value, dict):
            raise ValueError("Biblioteca de currículos inválida.")
        try:
            content = base64.b64decode(value["content"], validate=True)
            created_at = datetime.fromisoformat(str(value["created_at"]))
            stored = StoredResume(
                id=clean_text(str(value["id"]), max_length=64),
                label=clean_text(str(value["label"]), max_length=100),
                filename=Path(str(value["filename"])).name,
                content=content,
                text=normalize_resume_text(str(value["text"])),
                created_at=created_at,
                content_hash=clean_text(str(value["content_hash"]), max_length=64),
            )
        except (KeyError, TypeError, ValueError, binascii.Error) as exc:
            raise ValueError("Biblioteca de currículos inválida.") from exc
        if (
            not stored.id
            or not stored.label
            or not stored.filename
            or not stored.text
            or sha256(stored.content).hexdigest() != stored.content_hash
        ):
            raise ValueError("Biblioteca de currículos inválida.")
        return stored
