from __future__ import annotations

import re
from dataclasses import dataclass

from quati.domain import JobRecord
from quati.domain.job import clean_text, normalized_key
from quati.location import distance_km, resolve_brazilian_city
from quati.profile import CandidateProfile, preference_values

_WORD_RE = re.compile(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9+.#/-]{1,}")
_STOP_WORDS = frozenset(
    {
        "para",
        "com",
        "que",
        "uma",
        "dos",
        "das",
        "por",
        "mais",
        "como",
        "sua",
        "seu",
        "não",
        "the",
        "and",
        "comercial",
    }
)


@dataclass(frozen=True, slots=True)
class AIAnalysis:
    compatibility_score: int
    summary: str
    requirements: tuple[str, ...]
    missing_keywords: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RankedJob:
    job: JobRecord
    analysis: AIAnalysis


@dataclass(frozen=True, slots=True)
class CompatibilityAnalysis:
    compatibility_score: int
    role_score: int | None
    location_score: int | None
    seniority_score: int | None
    skills_score: int | None
    seniority: str
    work_mode: str
    distance_km: float | None
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RankedProfileJob:
    job: JobRecord
    compatibility: CompatibilityAnalysis


def _keywords(text: str) -> set[str]:
    words = (
        word.lower().rstrip(".,;:!?/–—-")
        for word in _WORD_RE.findall(clean_text(text, max_length=50_000))
    )
    return {word for word in words if len(word) >= 3 and word not in _STOP_WORDS}


def _requirements(description: str) -> tuple[str, ...]:
    sentences = re.split(r"(?<=[.!;])\s+", clean_text(description, max_length=20_000))
    candidates = [
        sentence
        for sentence in sentences
        if re.search(r"requis|necess|experiên|conhec|essencial|habilidade", sentence, re.I)
    ]
    return tuple(candidates[:12])


def analyze_locally(job: JobRecord, resume_text: str) -> AIAnalysis:
    """Análise determinística: não transmite currículo ou vaga a terceiros."""
    job_text = " ".join((job.title, job.description, job.location))
    job_keywords = _keywords(job_text)
    resume_keywords = _keywords(resume_text)
    matched = job_keywords & resume_keywords
    score = round(100 * len(matched) / max(min(len(job_keywords), 40), 1))
    missing = sorted(job_keywords - resume_keywords)[:20]
    summary = clean_text(job.description, max_length=600) or f"{job.title} em {job.company}."
    return AIAnalysis(
        compatibility_score=min(score, 100),
        summary=summary,
        requirements=_requirements(job.description),
        missing_keywords=tuple(missing),
    )


def rank_jobs_locally(jobs: list[JobRecord], resume_text: str) -> list[RankedJob]:
    ranked = [RankedJob(job, analyze_locally(job, resume_text)) for job in jobs]
    ranked.sort(
        key=lambda item: (item.analysis.compatibility_score, item.job.last_seen_at),
        reverse=True,
    )
    return ranked


_GENERIC_ROLE_WORDS = frozenset(
    {"de", "da", "do", "das", "dos", "em", "para", "e", "vaga", "pessoa"}
)
_GENERIC_SKILL_WORDS = frozenset(
    {
        "analista",
        "anos",
        "area",
        "atividades",
        "competencias",
        "conhecimento",
        "conhecimentos",
        "desejavel",
        "empresa",
        "experiencia",
        "formacao",
        "habilidades",
        "nivel",
        "profissional",
        "requisitos",
        "responsabilidades",
        "trabalho",
        "vivencia",
    }
)
_SENIORITY_WORDS = frozenset(
    {
        "estagio",
        "estagiario",
        "intern",
        "junior",
        "jr",
        "pleno",
        "pl",
        "senior",
        "sr",
        "especialista",
        "lead",
    }
)
_SENIORITY_RANK = {"Estágio": 0, "Júnior": 1, "Pleno": 2, "Sênior": 3}
_ROLE_AREAS = (
    frozenset(
        {
            "seguranca",
            "ciberseguranca",
            "cyber",
            "cybersecurity",
            "infosec",
            "soc",
            "siem",
            "iam",
            "pentest",
            "vulnerabilidade",
            "vulnerabilidades",
            "grc",
            "governanca",
            "riscos",
            "lgpd",
        }
    ),
    frozenset(
        {
            "suporte",
            "helpdesk",
            "service",
            "desk",
            "infraestrutura",
            "redes",
            "atendimento",
        }
    ),
    frozenset({"dados", "data", "bi", "analytics", "etl"}),
    frozenset({"desenvolvedor", "desenvolvimento", "software", "backend", "frontend", "devops"}),
    frozenset(
        {
            "administracao",
            "administrativo",
            "secretariado",
            "recepcao",
            "office",
        }
    ),
    frozenset({"civil", "obras", "construcao", "edificacoes"}),
    frozenset({"mecanica", "mecanico", "manutencao", "solidworks"}),
    frozenset({"eletrica", "eletrico", "eletrotecnica", "energia"}),
    frozenset({"producao", "processos", "qualidade", "industrial"}),
    frozenset(
        {
            "nutricao",
            "nutricionista",
            "dietetica",
            "uan",
            "cardapio",
            "alimentacao",
        }
    ),
    frozenset({"contabilidade", "contabil", "financeiro", "fiscal", "tesouraria"}),
    frozenset({"rh", "recursos", "humanos", "recrutamento", "departamento", "pessoal"}),
)
_TOKEN_ALIASES = {
    "administrativa": "administracao",
    "administrativo": "administracao",
    "nutricionista": "nutricao",
    "nutricional": "nutricao",
    "engenheiro": "engenharia",
    "engenheira": "engenharia",
    "contabil": "contabilidade",
    "mecanico": "mecanica",
    "eletrico": "eletrica",
}


def _normalized_tokens(text: str) -> set[str]:
    return {
        _TOKEN_ALIASES.get(token, token)
        for token in normalized_key(clean_text(text, max_length=50_000)).split()
        if len(token) >= 2 and token not in _GENERIC_ROLE_WORDS
    }


def detect_seniority(job: JobRecord) -> str:
    title = normalized_key(job.title)
    text = normalized_key(f"{job.title} {job.description[:2_000]}")
    if re.search(r"\b(estagi(?:o|ario|aria)|intern(?:ship)?)\b", text):
        return "Estágio"
    if re.search(r"\b(junior|jr)\b", title) or re.search(r"\bnivel\s+i\b", title):
        return "Júnior"
    if re.search(r"\b(pleno|mid(?:dle)?|pl)\b", title) or re.search(r"\bnivel\s+ii\b", title):
        return "Pleno"
    if re.search(r"\b(senior|sr|especialista|lead)\b", title) or re.search(
        r"\bnivel\s+iii\b", title
    ):
        return "Sênior"
    return "Não informado"


def detect_work_mode(job: JobRecord) -> str:
    text = normalized_key(f"{job.location} {job.title} {job.description[:2_000]}")
    if re.search(r"\b(remoto|remote|home office|teletrabalho)\b", text):
        return "Remoto"
    if re.search(r"\b(hibrido|hybrid)\b", text):
        return "Híbrido"
    if re.search(r"\b(presencial|on site|onsite)\b", text):
        return "Presencial"
    return "Não informado"


def _role_score(job: JobRecord, targets: tuple[str, ...]) -> tuple[int, str]:
    title_key = normalized_key(job.title)
    title_tokens = _normalized_tokens(job.title) - _SENIORITY_WORDS
    best = 0.0
    matched_target = ""
    for target in targets:
        target_key = normalized_key(target)
        target_tokens = _normalized_tokens(target) - _SENIORITY_WORDS
        if not target_tokens:
            continue
        if target_key and target_key in title_key:
            score = 1.0
        else:
            overlap = title_tokens & target_tokens
            coverage = len(overlap) / len(target_tokens)
            union = title_tokens | target_tokens
            jaccard = len(overlap) / len(union) if union else 0.0
            score = 0.8 * coverage + 0.2 * jaccard
            for area in _ROLE_AREAS:
                canonical_area = {_TOKEN_ALIASES.get(token, token) for token in area}
                if target_tokens & canonical_area and title_tokens & canonical_area:
                    score = max(score, 0.85)
        if score > best:
            best = score
            matched_target = target
    return round(best * 100), matched_target


def _location_score(
    job: JobRecord, profile: CandidateProfile, work_mode: str
) -> tuple[int, float | None, str]:
    preferred = profile.preferred_location
    accepted_modes = preference_values(profile.work_modes)
    parts: list[tuple[float, float]] = []
    distance: float | None = None
    reason = ""

    if preferred:
        if work_mode == "Remoto" and "Remoto" in accepted_modes:
            distance_score = 1.0
            reason = "vaga remota aceita"
        else:
            origin = resolve_brazilian_city(preferred)
            destination = resolve_brazilian_city(job.location)
            if origin and destination:
                distance = distance_km(origin, destination)
                radius = int(profile.max_distance_km)
                if distance <= radius:
                    distance_score = 1.0 - 0.2 * (distance / radius)
                elif distance <= radius * 2:
                    distance_score = 0.8 - 0.6 * ((distance - radius) / radius)
                else:
                    distance_score = 0.0
                reason = f"{distance:.0f} km de {origin.name}"
            elif normalized_key(preferred) in normalized_key(job.location):
                distance_score = 1.0
                reason = "localização exata"
            else:
                distance_score = 0.5
                reason = "distância não identificada"
        parts.append((distance_score, 0.8 if accepted_modes else 1.0))

    if accepted_modes:
        if work_mode in accepted_modes:
            mode_score = 1.0
        elif work_mode == "Não informado":
            mode_score = 0.6
        else:
            mode_score = 0.1
        parts.append((mode_score, 0.2 if preferred else 1.0))

    total_weight = sum(weight for _, weight in parts)
    score = sum(value * weight for value, weight in parts) / total_weight
    return round(score * 100), distance, reason


def _skills_score(job: JobRecord, profile: CandidateProfile) -> tuple[int, int]:
    profile_text = " ".join(
        (
            profile.skills,
            profile.experience,
            profile.summary,
            profile.education,
            profile.certifications,
        )
    )
    profile_tokens = _normalized_tokens(profile_text) - _GENERIC_SKILL_WORDS
    if not profile_tokens:
        return 0, 0
    if not job.description:
        title_tokens = _normalized_tokens(job.title) - _SENIORITY_WORDS - _GENERIC_SKILL_WORDS
        matched = title_tokens & profile_tokens
        denominator = max(len(title_tokens), 1)
        return min(round(100 * len(matched) / denominator), 100), len(matched)
    job_tokens = (
        _normalized_tokens(f"{job.title} {job.description}")
        - _SENIORITY_WORDS
        - _GENERIC_SKILL_WORDS
    )
    matched = job_tokens & profile_tokens
    denominator = max(min(len(job_tokens), 25), 1)
    return min(round(100 * len(matched) / denominator), 100), len(matched)


def _seniority_fit(seniority: str, selected_levels: tuple[str, ...]) -> tuple[int, int, str]:
    """Retorna nota, teto do resultado e uma justificativa legível."""
    if seniority == "Não informado":
        return 50, 85, "nível não informado; compatibilidade limitada a 85%"

    job_rank = _SENIORITY_RANK[seniority]
    target_ranks = tuple(
        _SENIORITY_RANK[level] for level in selected_levels if level in _SENIORITY_RANK
    )
    if not target_ranks or job_rank in target_ranks:
        return 100, 100, f"nível {seniority.lower()} compatível"

    difference = min(
        (job_rank - target for target in target_ranks),
        key=lambda value: (abs(value), value > 0),
    )
    if difference == 1:
        return 35, 70, "vaga um nível acima; compatibilidade limitada a 70%"
    if difference >= 2:
        return 0, 45, f"vaga {difference} níveis acima; compatibilidade limitada a 45%"
    if difference == -1:
        return 70, 85, "vaga um nível abaixo; compatibilidade limitada a 85%"
    return 45, 70, (f"vaga {abs(difference)} níveis abaixo; compatibilidade limitada a 70%")


def analyze_for_profile(job: JobRecord, profile: CandidateProfile) -> CompatibilityAnalysis:
    """Score local, ponderado e explicável; nenhum dado é enviado a terceiros."""
    targets = preference_values(profile.target_roles)
    selected_levels = preference_values(profile.target_levels)
    work_mode = detect_work_mode(job)
    seniority = detect_seniority(job)
    components: list[tuple[int, int]] = []
    reasons: list[str] = []
    score_cap = 100

    role_score: int | None = None
    if targets:
        role_score, matched_target = _role_score(job, targets)
        components.append((role_score, 35))
        reasons.append(
            f"cargo próximo de {matched_target}" if matched_target else "cargo fora dos alvos"
        )
        if role_score < 25:
            score_cap = min(score_cap, 40)
            reasons.append("cargo pouco relacionado; compatibilidade limitada a 40%")
        elif role_score < 55:
            score_cap = min(score_cap, 65)
            reasons.append("cargo parcialmente relacionado; compatibilidade limitada a 65%")
    else:
        score_cap = min(score_cap, 75)
        reasons.append("cargos não definidos no Perfil; compatibilidade limitada a 75%")

    location_score: int | None = None
    distance: float | None = None
    if profile.preferred_location or profile.work_modes:
        location_score, distance, location_reason = _location_score(job, profile, work_mode)
        components.append((location_score, 15))
        if location_reason:
            reasons.append(location_reason)

    seniority_score: int | None = None
    if selected_levels:
        seniority_score, seniority_cap, seniority_reason = _seniority_fit(
            seniority, selected_levels
        )
        score_cap = min(score_cap, seniority_cap)
        components.append((seniority_score, 25))
        reasons.append(seniority_reason)
    elif seniority != "Não informado":
        score_cap = min(score_cap, 75)
        reasons.append("níveis não definidos no Perfil; compatibilidade limitada a 75%")

    skills_score: int | None = None
    profile_has_skills = any(
        (
            profile.skills,
            profile.experience,
            profile.summary,
            profile.education,
            profile.certifications,
        )
    )
    if profile_has_skills:
        skills_score, matched_skills = _skills_score(job, profile)
        components.append((skills_score, 25))
        reasons.append(f"{matched_skills} termo(s) profissional(is) em comum")
        if not job.description:
            reasons.append("descrição indisponível; competências estimadas pelo título")

    if components:
        total_weight = sum(weight for _, weight in components)
        score = round(sum(value * weight for value, weight in components) / total_weight)
    else:
        score = analyze_locally(job, profile.text()).compatibility_score

    return CompatibilityAnalysis(
        compatibility_score=min(max(score, 0), score_cap),
        role_score=role_score,
        location_score=location_score,
        seniority_score=seniority_score,
        skills_score=skills_score,
        seniority=seniority,
        work_mode=work_mode,
        distance_km=distance,
        reasons=tuple(reasons),
    )


def profile_search_requirements(profile: CandidateProfile | None) -> tuple[str, ...]:
    """Campos mínimos para uma busca de compatibilidade confiável e explicável."""
    if profile is None:
        return ("Perfil salvo",)
    missing: list[str] = []
    if not preference_values(profile.target_roles):
        missing.append("cargos de interesse")
    if not preference_values(profile.target_levels):
        missing.append("níveis desejados")
    if not any(
        (
            profile.skills,
            profile.experience,
            profile.summary,
            profile.education,
            profile.certifications,
        )
    ):
        missing.append("competências ou experiência")
    work_modes = preference_values(profile.work_modes)
    if not work_modes:
        missing.append("modalidades de trabalho")
    if work_modes != ("Remoto",) and not profile.preferred_location:
        missing.append("cidade-base")
    return tuple(missing)


def rank_jobs_for_profile(
    jobs: list[JobRecord], profile: CandidateProfile
) -> list[RankedProfileJob]:
    ranked = [RankedProfileJob(job, analyze_for_profile(job, profile)) for job in jobs]
    ranked.sort(
        key=lambda item: (item.compatibility.compatibility_score, item.job.last_seen_at),
        reverse=True,
    )
    return ranked


def tailor_resume(resume_text: str, job: JobRecord, analysis: AIAnalysis) -> str:
    """No modo determinístico, preserva o conteúdo real durante a adaptação."""
    return resume_text.replace("\x00", "").strip()[:20_000]
