from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256

from quati.core.browser.url_safety import validate_public_https_url

_SOURCE_RE = re.compile(r"^[a-z0-9_-]{1,32}$")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_SPREADSHEET_FORMULA_RE = re.compile(r"^[\s]*[=+\-@]")
_PCD_ELIGIBILITY_RE = re.compile(
    r"\b(?:pcd|pessoa(?:s)? com deficiencia|vaga(?:s)? inclusiva(?:s)? para "
    r"pessoa(?:s)? com deficiencia)\b"
)
_PCD_NEGATION_RE = re.compile(
    r"\bnao (?:e |esta )?(?:elegivel|disponivel|destinad[ao])(?:.{0,40})\bpcd\b"
)


def clean_text(value: str | None, *, max_length: int = 10_000) -> str:
    """Normaliza texto externo antes de gravá-lo ou mostrá-lo."""
    if not value:
        return ""
    if not isinstance(value, str):
        raise ValueError("Texto inválido.")
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _CONTROL_CHARS_RE.sub(" ", normalized)
    # Controles não podem unir palavras que estavam em linhas separadas.
    normalized = "".join(
        " " if unicodedata.category(character) in {"Cc", "Cf"} else character
        for character in normalized
    )
    normalized = " ".join(normalized.split())
    return normalized[:max_length]


def safe_table_text(value: str | None, *, max_length: int = 10_000) -> str:
    """Neutraliza fórmulas ao exportar tabelas para CSV sem alterar o dado armazenado."""
    normalized = clean_text(value, max_length=max_length)
    return f"'{normalized}" if _SPREADSHEET_FORMULA_RE.match(normalized) else normalized


def normalized_key(value: str) -> str:
    """Cria chave estável sem conservar conteúdo pessoal ou formatação externa."""
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return _NON_ALNUM_RE.sub(" ", ascii_value.lower()).strip()


def job_dedupe_key(title: str, company: str, location: str) -> str:
    normalized = "\x1f".join(normalized_key(value) for value in (title, company, location))
    return sha256(normalized.encode("utf-8")).hexdigest()


def is_pcd_eligible_text(*values: str) -> bool:
    """Detecta somente indicações explícitas de elegibilidade para pessoas com deficiência."""
    text = normalized_key(" ".join(values))
    return bool(_PCD_ELIGIBILITY_RE.search(text) and not _PCD_NEGATION_RE.search(text))


@dataclass(frozen=True, slots=True)
class JobInput:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    published_at: str = ""

    def __post_init__(self) -> None:
        source = clean_text(self.source, max_length=32).lower()
        if not _SOURCE_RE.fullmatch(source):
            raise ValueError("Fonte inválida.")

        url = validate_public_https_url(self.url)
        external_id = clean_text(self.external_id, max_length=256)
        if not external_id:
            external_id = sha256(url.encode("utf-8")).hexdigest()[:32]

        title = clean_text(self.title, max_length=500)
        company = clean_text(self.company, max_length=500)
        if not title or not company:
            raise ValueError("Vaga exige título e empresa.")

        object.__setattr__(self, "source", source)
        object.__setattr__(self, "external_id", external_id)
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "company", company)
        object.__setattr__(self, "location", clean_text(self.location, max_length=500))
        object.__setattr__(self, "url", url)
        object.__setattr__(self, "description", clean_text(self.description, max_length=50_000))
        object.__setattr__(self, "published_at", clean_text(self.published_at, max_length=100))

    @property
    def content_hash(self) -> str:
        content = "\x1f".join(
            (self.title, self.company, self.location, self.description, self.published_at)
        )
        return sha256(content.encode("utf-8")).hexdigest()

    @property
    def dedupe_key(self) -> str:
        return job_dedupe_key(self.title, self.company, self.location)


@dataclass(frozen=True, slots=True)
class JobRecord:
    id: int
    source: str
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    published_at: str
    status: str
    first_seen_at: datetime
    last_seen_at: datetime

    @classmethod
    def from_row(cls, row: object) -> JobRecord:
        return cls(
            id=row["id"],
            source=row["source"],
            external_id=row["external_id"],
            title=row["title"],
            company=row["company"],
            location=row["location"],
            url=row["url"],
            description=row["description"],
            published_at=row["published_at"],
            status=row["status"],
            first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
        )


def utc_now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)
