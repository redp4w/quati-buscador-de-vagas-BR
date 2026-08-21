import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_ROOTS = (ROOT / "app.py", ROOT / "app_pages", ROOT / "src")
BLOCKED_IMPORTS = {"marshal", "pickle", "subprocess"}
BLOCKED_CALLS = {"eval", "exec", "compile", "__import__"}


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in CODE_ROOTS:
        files.extend([root] if root.is_file() else root.rglob("*.py"))
    return files


def test_application_has_no_dynamic_code_or_process_execution() -> None:
    findings: list[str] = []
    for path in _python_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                modules = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                if any(module.split(".", 1)[0] in BLOCKED_IMPORTS for module in modules):
                    findings.append(f"{path.name}:{node.lineno}: importação bloqueada")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in BLOCKED_CALLS
            ):
                findings.append(f"{path.name}:{node.lineno}: chamada {node.func.id}")
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "os"
                and node.func.attr in {"popen", "system"}
            ):
                findings.append(f"{path.name}:{node.lineno}: execução de processo")
    assert not findings, findings


def test_default_services_are_local_and_optional_workers_are_opt_in() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert '"127.0.0.1:8501:8501"' in compose
    assert 'profiles: ["automation"]' in compose
    assert 'profiles: ["ai"]' in compose
    assert 'address = "127.0.0.1"' in config
    assert "enableXsrfProtection = true" in config
    assert "maxUploadSize = 10" in config
    assert "USER pwuser" in dockerfile
