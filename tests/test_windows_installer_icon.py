from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_inno_installer_uses_generated_logo_icon():
    script = (ROOT / "packaging" / "windows" / "installer" / "infinite-canvas.iss").read_text(encoding="utf-8")

    assert '#define MyAppIcon "..\\..\\..\\build\\icons\\infinite-canvas.ico"' in script
    assert "SetupIconFile={#MyAppIcon}" in script
