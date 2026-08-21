import pytest

from quati.portals import DEFAULT_PORTAL_IDS
from quati.profile import CandidateProfile, ProfileVault


def test_profile_is_encrypted_and_requires_the_same_passphrase(tmp_path) -> None:
    vault = ProfileVault(tmp_path / "profile.enc")
    profile = CandidateProfile("Ana", "ana@example.com", "", "", "Python", "", "")
    vault.save(profile, "senha-local-segura")

    assert vault.load("senha-local-segura").skills == "Python"
    assert b"Ana" not in (tmp_path / "profile.enc").read_bytes()
    with pytest.raises(ValueError):
        vault.load("senha-incorreta")


def test_old_profile_receives_safe_preference_defaults(tmp_path) -> None:
    vault = ProfileVault(tmp_path / "profile.enc")
    vault._vault.save(  # noqa: SLF001 - simula o formato anterior persistido
        {
            "name": "Ana",
            "email": "",
            "phone": "",
            "address": "",
            "skills": "Python",
            "education": "",
            "experience": "",
        },
        "senha-local-segura",
    )

    profile = vault.load("senha-local-segura")

    assert profile.target_roles == ""
    assert profile.max_distance_km == "80"
    assert profile.job_portals == "; ".join(DEFAULT_PORTAL_IDS)


def test_profile_rejects_unknown_job_portal() -> None:
    with pytest.raises(ValueError, match="Portal"):
        CandidateProfile("Ana", "", "", "", "", "", "", job_portals="site-interno")


def test_profile_preserves_safe_multiline_resume_structure() -> None:
    profile = CandidateProfile(
        "Ana",
        "",
        "",
        "",
        "Python\nLinux\n\nSegurança",
        "Curso A\nCurso B",
        "Empresa A\n- Atividade 1\n- Atividade 2",
    )

    assert profile.skills == "Python\nLinux\n\nSegurança"
    assert profile.education == "Curso A\nCurso B"
    assert profile.experience == "Empresa A\n- Atividade 1\n- Atividade 2"


def test_profile_controls_do_not_join_words() -> None:
    profile = CandidateProfile("Ana", "", "", "", "Python\x00SQL", "", "")

    assert profile.skills == "Python SQL"


def test_profile_validates_contact_and_base_city() -> None:
    profile = CandidateProfile(
        "Ana",
        "ana@example.com",
        "+55 (11) 99999-9999",
        "",
        "Python",
        "",
        "",
        preferred_location="sorocaba / sp",
    )

    assert profile.preferred_location == "Sorocaba, SP"
    with pytest.raises(ValueError, match="E-mail"):
        CandidateProfile("Ana", "ana@localhost", "", "", "", "", "")
    with pytest.raises(ValueError, match="Telefone"):
        CandidateProfile("Ana", "", "executar()", "", "", "", "")
