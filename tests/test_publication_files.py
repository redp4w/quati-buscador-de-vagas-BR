from __future__ import annotations

import re
import struct
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_windows_click_installers_are_local_and_reproducible() -> None:
    installer = _read("scripts/install-windows.ps1")
    launcher = _read("scripts/launch-windows.ps1")
    stopper = _read("scripts/stop-windows.ps1")
    root_launchers = sorted(path.name for path in ROOT.glob("*.cmd"))

    assert root_launchers == ["iniciar.cmd"]
    assert "scripts\\launch-windows.ps1" in _read("iniciar.cmd")
    assert "uv.lock" in _read("README.md")
    assert '"--frozen"' in installer
    assert '"chromium"' in installer
    assert "MessageBoxButtons]::YesNo" in installer
    assert '"127.0.0.1"' in launcher
    assert '"0.0.0.0"' not in launcher
    assert "Test-OwnProcess" in launcher
    assert "Get-ClientConnectionCount" in launcher
    assert "Stop-AppProcessTree" in launcher
    assert "Resolve-OwnProcessId" in launcher
    assert "shutdown.request" in launcher
    assert "quati-watchdog.pid" in launcher
    assert "TotalSeconds -ge 10" in launcher
    assert "Test-OwnProcess" in stopper
    assert "Stop-Process" in stopper


def test_linux_installers_are_local_and_reproducible() -> None:
    installer = _read("install-linux.sh")
    launcher = _read("scripts/launch-linux.sh")
    stopper = _read("scripts/stop-linux.sh")

    assert "--frozen" in installer
    assert "playwright install --with-deps chromium" in installer
    assert "Autoriza a instalação?" in installer
    assert "--server.address 127.0.0.1" in launcher
    assert "0.0.0.0" not in launcher
    assert "is_own_process" in launcher
    assert "has_client_connection" in launcher
    assert "IDLE_TICKS >= 20" in launcher
    assert "trap cleanup_app" in launcher
    assert "shutdown.request" in launcher
    assert "/proc/$APP_PID/cmdline" in stopper


def test_streamlit_theme_separates_sidebar_from_body() -> None:
    config = tomllib.loads(_read(".streamlit/config.toml"))

    assert config["theme"]["backgroundColor"] != config["theme"]["sidebar"][
        "backgroundColor"
    ]
    assert config["theme"]["sidebar"]["primaryColor"] == "#FF1738"
    assert config["theme"]["font"] == "monospace"


def test_public_markdown_relative_links_exist() -> None:
    link_pattern = re.compile(r"\[[^\]]+\]\((?!https?://|mailto:|#)([^)]+)\)")
    for document in ROOT.rglob("*.md"):
        if ".venv" in document.parts or ".agents" in document.parts:
            continue
        for raw_target in link_pattern.findall(document.read_text(encoding="utf-8")):
            target = raw_target.split("#", 1)[0]
            if not target:
                continue
            assert (document.parent / target).resolve().exists(), (
                f"Link ausente em {document.relative_to(ROOT)}: {raw_target}"
            )


def test_brand_raster_assets_have_expected_dimensions() -> None:
    icon = (ROOT / "src/quati/assets/quati-icon.png").read_bytes()
    preview = (ROOT / "docs/assets/github-social-preview.png").read_bytes()
    screenshots = [
        (ROOT / "docs/assets/app-access.png").read_bytes(),
        (ROOT / "docs/assets/app-overview.png").read_bytes(),
        (ROOT / "docs/assets/app-jobs.png").read_bytes(),
        (ROOT / "docs/assets/app-results.png").read_bytes(),
    ]

    assert icon[:8] == b"\x89PNG\r\n\x1a\n"
    assert preview[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", icon[16:24]) == (512, 512)
    assert struct.unpack(">II", preview[16:24]) == (1280, 640)
    assert all(screenshot[:8] == b"\x89PNG\r\n\x1a\n" for screenshot in screenshots)
    assert all(struct.unpack(">II", screenshot[16:24]) == (1280, 720) for screenshot in screenshots)
    assert (ROOT / "src/quati/assets/quati-icon.ico").stat().st_size > 1_000


def test_approved_brand_assets_are_present() -> None:
    for asset in (
        "src/quati/assets/quati-icon-master.png",
        "src/quati/assets/quati-horizontal-master.png",
        "src/quati/assets/quati-mascot-master.png",
        "src/quati/assets/quati-horizontal-white.png",
        "src/quati/assets/quati-mascot.png",
        "src/quati/assets/quati-icon-approved.png",
    ):
        content = (ROOT / asset).read_bytes()
        assert content[:8] == b"\x89PNG\r\n\x1a\n"

    for asset in (
        "src/quati/assets/quati-loading.gif",
        "src/quati/assets/quati-menu-scan.gif",
        "src/quati/assets/quati-inicio-scan.gif",
        "src/quati/assets/quati-solo-scan.gif",
        "src/quati/assets/quati-inicio-master.gif",
        "src/quati/assets/quati-walk-master.gif",
    ):
        content = (ROOT / asset).read_bytes()
        assert content[:6] in {b"GIF87a", b"GIF89a"}


def test_final_brand_gifs_are_animated_and_transparent() -> None:
    expected = {
        "quati-menu-scan.gif": (720, 240, 28),
        "quati-inicio-scan.gif": (480, 460, 32),
        "quati-solo-scan.gif": (640, 420, 28),
        "quati-loading.gif": (360, 250, 8),
    }
    for name, (width, height, minimum_frames) in expected.items():
        with Image.open(ROOT / "src/quati/assets" / name) as image:
            assert image.size == (width, height)
            assert image.n_frames >= minimum_frames
            assert image.info.get("loop") == 0
            assert "transparency" in image.info or "A" in image.getbands()
            if name == "quati-loading.gif":
                poses = []
                durations = []
                for index in range(image.n_frames):
                    image.seek(index)
                    poses.append(image.convert("RGBA").tobytes())
                    durations.append(image.info.get("duration"))
                assert len(set(poses)) == 8
                assert set(durations) == {110}
            image.seek(image.n_frames - 1)
            assert image.convert("RGBA").getchannel("A").getextrema() == (0, 255)


def test_readme_presentation_assets_are_well_formed() -> None:
    readme = _read("README.md")
    workflow = _read("docs/assets/workflow.svg")

    ET.fromstring(workflow)
    assert "## Página inicial" in readme
    assert "conteúdo exclusivamente sintético" in readme
    for asset in (
        "docs/assets/github-social-preview.png",
        "docs/assets/app-access.png",
        "docs/assets/app-overview.png",
        "docs/assets/app-jobs.png",
        "docs/assets/app-results.png",
        "docs/assets/workflow.svg",
    ):
        assert asset in readme
