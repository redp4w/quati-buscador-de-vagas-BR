import ast
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from quati.config import AIConfiguration

ROOT = Path(__file__).resolve().parents[1]


def _start_session(app: AppTest) -> AppTest:
    app.run(timeout=10)
    app.text_input[0].set_value("senha-local-segura")
    next(button for button in app.button if button.label == "Entrar").click()
    return app.run(timeout=10)


def test_dashboard_starts_on_overview_without_errors(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUATI_DB", str(tmp_path / "dashboard.sqlite3"))
    app = _start_session(AppTest.from_file(ROOT / "app.py"))

    assert not app.exception
    assert not app.title
    assert app.subheader[0].value == "Seu ponto de partida"
    assert (ROOT / "src/quati/assets/quati-menu-scan.gif").is_file()
    assert (ROOT / "src/quati/assets/quati-inicio-scan.gif").is_file()


def test_new_profile_page_offers_resume_prefill(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUATI_DB", str(tmp_path / "prefill.sqlite3"))
    app = _start_session(AppTest.from_file(ROOT / "app.py"))
    app.switch_page("app_pages/profile.py").run(timeout=10)

    assert not app.exception
    assert any(item.label == "Currículo PDF ou DOCX" for item in app.file_uploader)
    assert any("não é armazenado" in item.value for item in app.caption)


def test_ai_settings_exposes_gemini_configuration(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUATI_DB", str(tmp_path / "ai-settings.sqlite3"))
    app = _start_session(AppTest.from_file(ROOT / "app.py"))
    app.switch_page("app_pages/ai_settings.py").run(timeout=10)
    app.selectbox[0].select("gemini").run(timeout=10)

    assert not app.exception
    assert any(item.label == "Chave da API" for item in app.text_input)
    assert app.warning


def test_assistant_renders_with_local_configuration(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("QUATI_DB", str(tmp_path / "assistant.sqlite3"))
    app = _start_session(AppTest.from_file(ROOT / "app.py"))
    app.session_state["ai_configuration"] = AIConfiguration(
        "ollama", "llama3.2", "http://127.0.0.1:11434"
    )
    app.switch_page("app_pages/assistant.py").run(timeout=10)

    assert not app.exception
    assert app.chat_input


def test_text_fields_do_not_show_suggestions_or_default_placeholders() -> None:
    paths = [*sorted((ROOT / "app_pages").glob("*.py")), ROOT / "src/quati/ui/context.py"]
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            widget = node.func.attr
            placeholders = [
                keyword.value for keyword in node.keywords if keyword.arg == "placeholder"
            ]
            for placeholder in placeholders:
                assert isinstance(placeholder, ast.Constant) and placeholder.value == ""
            if widget == "multiselect":
                assert placeholders, f"Multiselect sem placeholder vazio: {path.name}:{node.lineno}"
            if widget == "chat_input":
                assert node.args and isinstance(node.args[0], ast.Constant)
                assert node.args[0].value == ""

    role_sources = "\n".join(
        (ROOT / "app_pages" / name).read_text(encoding="utf-8")
        for name in ("profile.py", "jobs.py")
    )
    assert '"Segurança da informação"' not in role_sources
    assert '"Analista de suporte"' not in role_sources


@pytest.mark.parametrize(
    "page",
    [
        "profile.py",
        "resumes.py",
        "ai_settings.py",
        "job_sources.py",
        "assistant.py",
        "jobs.py",
        "applications.py",
        "automation.py",
        "history.py",
        "logs.py",
    ],
)
def test_each_dashboard_page_renders_individually(page: str, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QUATI_DB", str(tmp_path / f"{page}.sqlite3"))
    app = _start_session(AppTest.from_file(ROOT / "app.py"))
    app.switch_page(str(Path("app_pages") / page)).run(timeout=10)

    assert not app.exception
