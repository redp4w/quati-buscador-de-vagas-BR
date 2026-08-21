import json
from dataclasses import asdict
from pathlib import Path

from streamlit.testing.v1 import AppTest

from quati.config import AIConfiguration, JobSourceConfiguration
from quati.domain import JobInput
from quati.profile import CandidateProfile
from quati.security import EncryptedJSONVault
from quati.storage import SQLiteJobRepository
from quati.ui.context import _repository, get_repository

ROOT = Path(__file__).resolve().parents[1]


def _close_repository() -> None:
    get_repository().close()
    _repository.clear()


def test_app_requests_password_once_and_opens_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUATI_DB", str(tmp_path / "app.sqlite3"))
    app = AppTest.from_file(ROOT / "app.py")

    app.run(timeout=20)
    assert not app.exception
    assert [button.label for button in app.button] == ["Entrar", "Fechar Q.U.A.T.I."]

    app.text_input[0].set_value("senha-local-segura")
    next(button for button in app.button if button.label == "Entrar").click()
    app.run(timeout=20)

    assert not app.exception
    assert any(item.value == "Seu ponto de partida" for item in app.subheader)
    assert all(item.label != "Senha local opcional" for item in app.text_input)
    assert "Encerrar" in {button.label for button in app.button}
    assert all("Sessão iniciada" not in item.value for item in app.success)
    _close_repository()


def test_legacy_private_vault_is_rewritten_after_login(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "legacy-login.sqlite3"
    profile_path = tmp_path / "candidate-profile.enc"
    profile = CandidateProfile("Ana", "", "", "", "Python", "", "")
    vault = EncryptedJSONVault(profile_path)
    salt = bytes(range(16))
    payload = json.dumps(asdict(profile)).encode("utf-8")
    profile_path.write_bytes(
        salt + vault._legacy_fernet("x", salt).encrypt(payload)
    )
    monkeypatch.setenv("QUATI_DB", str(database_path))
    app = AppTest.from_file(ROOT / "app.py")

    app.run(timeout=20)
    app.text_input[0].set_value("x")
    next(button for button in app.button if button.label == "Entrar").click()
    app.run(timeout=20)

    assert not app.exception
    assert profile_path.read_bytes().startswith(b"QUATI\x00\x02\x00")
    _close_repository()


def test_profile_and_jobs_pages_render_with_preferences(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "pages.sqlite3"
    monkeypatch.setenv("QUATI_DB", str(database_path))
    repository = SQLiteJobRepository(database_path)
    repository.upsert(
        JobInput(
            "linkedin",
            "1",
            "Analista de suporte júnior",
            "Acme",
            "Sorocaba, SP",
            "https://www.linkedin.com/jobs/view/1",
        )
    )
    repository.upsert(
        JobInput(
            "linkedin",
            "2",
            "Analista de suporte sênior",
            "Acme",
            "Sorocaba, SP",
            "https://www.linkedin.com/jobs/view/2",
            description="Windows, redes e suporte técnico",
        )
    )
    repository.close()
    profile = CandidateProfile(
        "Ana",
        "",
        "",
        "Itu, SP",
        "Windows e redes",
        "",
        "Suporte técnico",
        target_roles="Analista de suporte; Segurança da informação",
        target_levels="Júnior",
        preferred_location="Itu, SP",
        work_modes="Presencial; Híbrido",
    )

    profile_page = AppTest.from_file(ROOT / "app_pages/profile.py")
    profile_page.session_state["candidate_profile"] = profile
    profile_page.session_state["vault_passphrases"] = {"profile": "senha-local-segura"}
    profile_page.session_state["local_session_started"] = True
    profile_page.run(timeout=20)
    assert not profile_page.exception
    assert "Apagar dados locais" in {button.label for button in profile_page.button}

    jobs_page = AppTest.from_file(ROOT / "app_pages/jobs.py")
    jobs_page.session_state["candidate_profile"] = profile
    jobs_page.session_state["resume_library"] = []
    jobs_page.session_state["job_search_levels"] = ["Sênior"]
    jobs_page.run(timeout=20)
    assert not jobs_page.exception
    assert any(header.value == "Buscar vagas" for header in jobs_page.header)
    assert "Somente vagas explicitamente indicadas para PCD" in {
        checkbox.label for checkbox in jobs_page.checkbox
    }
    keyword_input = next(
        item for item in jobs_page.text_input if item.label == "Palavras adicionais (opcional)"
    )
    assert keyword_input.value == ""
    assert list(jobs_page.dataframe[-1].value.columns) == [
        "Anúncio",
        "Currículo",
        "Vaga",
        "Compatibilidade",
        "Empresa",
        "Local",
    ]
    frame = jobs_page.dataframe[-1].value
    senior_row = frame[frame["Vaga"].str.contains("sênior")].iloc[0]
    assert senior_row["Compatibilidade"] <= 45

    next(
        item for item in jobs_page.get("button_group") if item.key == "job_search_mode"
    ).set_value("Compatíveis com o Perfil")
    jobs_page.run(timeout=20)
    assert not jobs_page.exception
    assert any(button.label == "Buscar vagas compatíveis" for button in jobs_page.button)
    assert all(
        item.label != "Palavras adicionais (opcional)" for item in jobs_page.text_input
    )
    assert any("compatibilidade mínima de 70%" in item.value for item in jobs_page.success)
    _close_repository()


def test_apply_page_uses_simplified_flow(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "apply.sqlite3"
    monkeypatch.setenv("QUATI_DB", str(database_path))
    repository = SQLiteJobRepository(database_path)
    outcome = repository.upsert_with_result(
        JobInput(
            "gupy",
            "10",
            "Analista de Segurança Júnior",
            "Acme",
            "Itu, SP",
            "https://acme.gupy.io/jobs/10",
        )
    )
    repository.save_application(outcome.job_id, resume_id="profile", strategy="standard")
    repository.close()
    profile = CandidateProfile("Ana", "", "", "Itu, SP", "SIEM", "", "Experiência em SOC")

    apply_page = AppTest.from_file(ROOT / "app_pages/applications.py")
    apply_page.session_state["candidate_profile"] = profile
    apply_page.session_state["resume_library"] = []
    apply_page.session_state["application_bundle"] = None
    apply_page.run(timeout=20)
    assert not apply_page.exception
    assert any(
        item.value == "Ajuste o currículo para a vaga escolhida"
        for item in apply_page.subheader
    )
    next(button for button in apply_page.button if button.label == "Analisar e preparar").click()
    apply_page.run(timeout=30)
    assert not apply_page.exception
    next(button for button in apply_page.button if button.label == "Gerar HTML, PDF e DOCX").click()
    apply_page.run(timeout=30)
    assert not apply_page.exception
    assert {button.label for button in apply_page.get("download_button")} >= {
        "Baixar PDF",
        "Baixar DOCX",
        "Baixar HTML",
        "Baixar prompt",
    }
    _close_repository()


def test_ai_preferences_are_configured_outside_the_assistant() -> None:
    page = AppTest.from_file(ROOT / "app_pages/ai_settings.py")
    page.session_state["ai_configuration"] = AIConfiguration(
        "gemini",
        "gemini-3.5-flash-lite",
        api_key="test-key",
        include_profile_context=True,
        external_consent=True,
    )

    page.run(timeout=20)

    assert not page.exception
    checkboxes = {checkbox.label: checkbox.value for checkbox in page.checkbox}
    assert checkboxes == {
        "Autorizar envio ao provedor externo": True,
    }


def test_jobs_search_accepts_location_without_profile(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "public-search.sqlite3"
    monkeypatch.setenv("QUATI_DB", str(database_path))
    page = AppTest.from_file(ROOT / "app_pages/jobs.py")
    page.session_state["candidate_profile"] = None
    page.session_state["resume_library"] = []

    page.run(timeout=20)
    next(item for item in page.selectbox if item.label == "Estado").set_value("SP")
    page.run(timeout=20)
    next(item for item in page.selectbox if item.label == "Cidade").set_value("Itu")
    page.run(timeout=20)

    assert not page.exception
    assert any(item.value == "Buscar vagas públicas" for item in page.subheader)
    _close_repository()


def test_adzuna_only_enters_automatic_sources_after_local_configuration(
    tmp_path, monkeypatch
) -> None:
    database_path = tmp_path / "adzuna-ui.sqlite3"
    monkeypatch.setenv("QUATI_DB", str(database_path))

    page = AppTest.from_file(ROOT / "app_pages/jobs.py")
    page.session_state["candidate_profile"] = None
    page.session_state["resume_library"] = []
    page.run(timeout=20)
    automatic = next(item for item in page.multiselect if item.label == "Coleta automática")
    assert "Adzuna" not in automatic.options
    assert "Sólides Vagas" in automatic.options

    configured_page = AppTest.from_file(ROOT / "app_pages/jobs.py")
    configured_page.session_state["candidate_profile"] = None
    configured_page.session_state["resume_library"] = []
    configured_page.session_state["job_source_configuration"] = JobSourceConfiguration(
        "app-id", "app-key"
    )
    configured_page.run(timeout=20)
    configured_automatic = next(
        item for item in configured_page.multiselect if item.label == "Coleta automática"
    )
    assert "Adzuna" in configured_automatic.options
    _close_repository()


def test_linkedin_search_is_prepared_without_starting_a_collector(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "linkedin-assisted.sqlite3"
    monkeypatch.setenv("QUATI_DB", str(database_path))
    page = AppTest.from_file(ROOT / "app_pages/jobs.py")
    page.session_state["candidate_profile"] = None
    page.session_state["resume_library"] = []

    page.run(timeout=20)
    next(
        item for item in page.text_input if item.label == "Palavras adicionais (opcional)"
    ).set_value("analista administrativo")
    next(item for item in page.selectbox if item.label == "Estado").set_value("SP")
    page.run(timeout=20)
    next(item for item in page.selectbox if item.label == "Cidade").set_value("Sorocaba")
    # LinkedIn agora é automático, então teste com uma fonte assistida como jobbol
    next(item for item in page.multiselect if item.label == "Coleta automática").set_value([])
    next(
        item for item in page.multiselect if item.label == "Busca assistida ou por link"
    ).set_value(["jobbol"])
    next(button for button in page.button if button.label == "Buscar vagas").click()
    page.run(timeout=20)

    assert not page.exception
    assert any(item.value == "Continuar nos portais" for item in page.subheader)
    assert any(
        button.label == "Jobbol · analista administrativo" for button in page.get("link_button")
    )
    _close_repository()
