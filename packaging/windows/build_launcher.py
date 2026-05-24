from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import venv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_NAME = "Infinite Canvas"
WINDOWS_SERVICE_HIDDEN_IMPORTS = [
    "fastapi.staticfiles",
    "fastapi.responses",
    "fastapi.middleware.cors",
    "fastapi.exceptions",
    "pydantic",
    "pydantic_core",
    "PIL.Image",
    "requests",
    "httpx",
    "uvicorn",
]


def run_pyinstaller(
    python_exe: Path,
    entrypoint: Path,
    name: str,
    dist_dir: Path,
    *,
    onefile: bool = True,
    hidden_imports: list[str] | None = None,
) -> None:
    command = [
        str(python_exe),
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--name",
        name,
        "--distpath",
        str(dist_dir),
    ]
    command.append("--onefile" if onefile else "--onedir")
    for item in hidden_imports or []:
        if item:
            command.extend(["--hidden-import", item])
    command.append(str(entrypoint))
    subprocess.run(command, cwd=str(ROOT), check=True)


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / "Scripts" / "python.exe"


def prepare_build_venv(venv_dir: Path) -> Path:
    python_exe = venv_python(venv_dir)
    if not python_exe.exists():
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
    subprocess.run(
        [str(python_exe), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt"), "PyInstaller"],
        cwd=str(ROOT),
        check=True,
    )
    return python_exe


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Windows launcher and updater executables.")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist" / "windows")
    parser.add_argument("--venv-dir", type=Path, default=ROOT / "build" / "windows-packaging-venv")
    args = parser.parse_args()

    args.dist_dir.mkdir(parents=True, exist_ok=True)
    service_dir = args.dist_dir / f"{APP_NAME} Service"
    if service_dir.exists():
        shutil.rmtree(service_dir)

    python_exe = prepare_build_venv(args.venv_dir)
    run_pyinstaller(python_exe, ROOT / "packaging" / "windows" / "launcher" / "launcher_main.py", APP_NAME, args.dist_dir)
    run_pyinstaller(
        python_exe,
        ROOT / "packaging" / "windows" / "service" / "service_main.py",
        f"{APP_NAME} Service",
        args.dist_dir,
        onefile=False,
        hidden_imports=WINDOWS_SERVICE_HIDDEN_IMPORTS,
    )
    run_pyinstaller(python_exe, ROOT / "packaging" / "windows" / "updater" / "updater_main.py", f"{APP_NAME} Updater", args.dist_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
