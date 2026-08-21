from __future__ import annotations

import re
import unicodedata
from dataclasses import MISSING, asdict, dataclass, fields
from pathlib import Path

from quati.domain.job import clean_text, normalized_key
from quati.location import canonical_brazilian_location, split_brazilian_location
from quati.portals import DEFAULT_PORTAL_IDS, PORTALS_BY_ID, portal_ids
from quati.security import EncryptedJSONVault

JOB_LEVELS = ("Estágio", "Júnior", "Pleno", "Sênior")
WORK_MODES = ("Presencial", "Híbrido", "Remoto")
_PREFERENCE_SEPARATOR_RE = re.compile(r"[;|,\n]+")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
_PHONE_RE = re.compile(r"^[0-9+().\-\s]{7,100}$")
_MULTILINE_FIELDS = {
    "skills",
    "education",
    "experience",
    "summary",
    "languages",
    "certifications",
    "links",
    "projects",
    "additional",
    "keywords",
}


def _clean_multiline_text(value: str | None, *, max_length: int) -> str:
    """Remove controles sem destruir listas e parágrafos do currículo."""
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKC", value.replace("\r\n", "\n").replace("\r", "\n"))
    normalized = _CONTROL_CHARS_RE.sub(" ", normalized)
    normalized = "".join(
        character
        if character == "\n" or unicodedata.category(character) not in {"Cc", "Cf"}
        else " "
        for character in normalized
    )
    lines: list[str] = []
    previous_blank = False
    for raw_line in normalized.split("\n"):
        line = " ".join(raw_line.split())
        if line:
            lines.append(line)
            previous_blank = False
        elif lines and not previous_blank:
            lines.append("")
            previous_blank = True
    return "\n".join(lines).strip()[:max_length]


def preference_values(value: str) -> tuple[str, ...]:
    return tuple(
        item
        for raw in _PREFERENCE_SEPARATOR_RE.split(value)
        if (item := clean_text(raw, max_length=200))
    )


def _normalized_choices(value: str, allowed: tuple[str, ...]) -> str:
    choices = {normalized_key(item): item for item in allowed}
    normalized: list[str] = []
    for item in preference_values(value):
        canonical = choices.get(normalized_key(item))
        if canonical is None:
            raise ValueError("Preferência de vaga inválida.")
        if canonical not in normalized:
            normalized.append(canonical)
    return "; ".join(normalized)


@dataclass(frozen=True, slots=True)
class CandidateProfile:
    name: str
    email: str
    phone: str
    address: str
    skills: str
    education: str
    experience: str
    headline: str = ""
    summary: str = ""
    languages: str = ""
    certifications: str = ""
    links: str = ""
    target_roles: str = ""
    target_levels: str = ""
    preferred_location: str = ""
    max_distance_km: str = "80"
    work_modes: str = ""
    # Mantido apenas para abrir perfis de versões anteriores. A seleção atual fica na busca.
    job_portals: str = "; ".join(DEFAULT_PORTAL_IDS)
    projects: str = ""
    additional: str = ""
    keywords: str = ""

    def __post_init__(self) -> None:
        limits = {
            "name": 200,
            "email": 320,
            "phone": 100,
            "address": 500,
            "skills": 20_000,
            "education": 20_000,
            "experience": 40_000,
            "headline": 500,
            "summary": 10_000,
            "languages": 5_000,
            "certifications": 10_000,
            "links": 5_000,
            "target_roles": 2_000,
            "target_levels": 200,
            "preferred_location": 300,
            "max_distance_km": 4,
            "work_modes": 200,
            "job_portals": 500,
            "projects": 20_000,
            "additional": 10_000,
            "keywords": 5_000,
        }
        for field, limit in limits.items():
            value = getattr(self, field)
            normalized = (
                _clean_multiline_text(value, max_length=limit)
                if field in _MULTILINE_FIELDS
                else clean_text(value, max_length=limit)
            )
            object.__setattr__(self, field, normalized)
        if not self.name:
            raise ValueError("Informe o nome.")
        if self.email and not _EMAIL_RE.fullmatch(self.email):
            raise ValueError("E-mail inválido.")
        if self.phone and (
            not _PHONE_RE.fullmatch(self.phone)
            or sum(character.isdigit() for character in self.phone) < 7
        ):
            raise ValueError("Telefone inválido.")
        if self.preferred_location:
            city, state = split_brazilian_location(self.preferred_location)
            if not city or not state:
                raise ValueError("Selecione uma cidade-base e o estado correspondente.")
            object.__setattr__(
                self,
                "preferred_location",
                canonical_brazilian_location(city, state),
            )
        try:
            distance = int(self.max_distance_km or "80")
        except ValueError as exc:
            raise ValueError("A distância máxima deve ser um número inteiro.") from exc
        if not 1 <= distance <= 500:
            raise ValueError("A distância máxima deve estar entre 1 e 500 km.")
        object.__setattr__(self, "max_distance_km", str(distance))
        target_roles = preference_values(self.target_roles)
        if len(target_roles) > 5:
            raise ValueError("Cadastre no máximo cinco cargos de interesse.")
        object.__setattr__(self, "target_roles", "; ".join(dict.fromkeys(target_roles)))
        object.__setattr__(
            self, "target_levels", _normalized_choices(self.target_levels, JOB_LEVELS)
        )
        object.__setattr__(self, "work_modes", _normalized_choices(self.work_modes, WORK_MODES))
        selected_portals = portal_ids(self.job_portals)
        raw_portals = tuple(
            item.strip().lower()
            for item in self.job_portals.replace(",", ";").split(";")
            if item.strip()
        )
        if any(item not in PORTALS_BY_ID for item in raw_portals):
            raise ValueError("Portal de vagas inválido.")
        object.__setattr__(self, "job_portals", "; ".join(selected_portals))

    def text(self) -> str:
        return " ".join(
            (
                self.name,
                self.headline,
                self.summary,
                self.skills,
                self.experience,
                self.education,
                self.certifications,
                self.languages,
                self.projects,
                self.additional,
                self.keywords,
            )
        )


class ProfileVault:
    """Perfil cifrado localmente; a senha nunca é armazenada."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._vault = EncryptedJSONVault(path, max_ciphertext_bytes=1_048_576)

    def exists(self) -> bool:
        return self._vault.exists()

    def uses_current_format(self) -> bool:
        return self._vault.uses_current_format()

    def save(self, profile: CandidateProfile, passphrase: str) -> None:
        self._vault.save(asdict(profile), passphrase)

    def load(self, passphrase: str) -> CandidateProfile:
        values = self._vault.load(passphrase)
        profile_fields = {field.name: field for field in fields(CandidateProfile)}
        field_names = set(profile_fields)
        required = {"name", "email", "phone", "address", "skills", "education", "experience"}
        if not isinstance(values, dict) or not required <= set(values) <= field_names:
            raise ValueError("Perfil inválido.")
        if not all(isinstance(value, str) for value in values.values()):
            raise ValueError("Perfil inválido.")
        restored = dict(values)
        for name, field in profile_fields.items():
            if name in restored:
                continue
            restored[name] = field.default if field.default is not MISSING else ""
        return CandidateProfile(**restored)
