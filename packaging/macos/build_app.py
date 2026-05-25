from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packaging.macos.payload.build_payload import DEFAULT_MANIFEST, DEFAULT_OUTPUT, build_payload


APP_NAME = "Infinite Canvas"
DEFAULT_DIST_DIR = ROOT / "dist" / "macos"
DEFAULT_VENV_DIR = ROOT / "build" / "macos-packaging-venv"
MAC_SERVICE_HIDDEN_IMPORTS = [
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
    onefile: bool = False,
    hidden_imports: list[str] | None = None,
    windowed: bool = False,
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
    if windowed:
        command.append("--windowed")
    for item in hidden_imports or []:
        if item:
            command.extend(["--hidden-import", item])
    command.append(str(entrypoint))
    subprocess.run(command, cwd=str(ROOT), check=True)


def venv_python(venv_dir: Path) -> Path:
    return venv_dir / "bin" / "python"


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


def read_version() -> str:
    lines = (ROOT / "VERSION").read_text(encoding="utf-8").strip().splitlines()
    version = lines[0].strip() if lines else ""
    return version or "0.0.0"


def write_info_plist(app_bundle: Path, version: str) -> None:
    plist = {
        "CFBundleDevelopmentRegion": "zh_CN",
        "CFBundleDisplayName": APP_NAME,
        "CFBundleExecutable": APP_NAME,
        "CFBundleIdentifier": "com.infinitecanvas.app",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": APP_NAME,
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "LSMinimumSystemVersion": "10.14",
        "NSHighResolutionCapable": True,
    }
    plist_path = app_bundle / "Contents" / "Info.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as fh:
        plistlib.dump(plist, fh)


def remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
        return
    if path.exists():
        path.unlink()


def appdir_name(binary_name: str) -> str:
    return f"{binary_name}.appdir"


def write_appdir_wrapper(
    wrapper_path: Path,
    binary_name: str,
    *,
    pass_app_bundle: bool = False,
) -> None:
    appdir = appdir_name(binary_name)
    command = f'exec "$SCRIPT_DIR/{appdir}/{binary_name}"'
    if pass_app_bundle:
        command += ' --app-bundle "$SCRIPT_DIR/../.."'
    command += ' "$@"'
    script = (
        "#!/bin/sh\n"
        'SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
        f"{command}\n"
    )
    wrapper_path.write_text(script, encoding="utf-8")
    wrapper_path.chmod(0o755)


def install_pyinstaller_output(
    build_bin_dir: Path,
    macos_dir: Path,
    binary_name: str,
    *,
    onefile: bool = False,
    pass_app_bundle: bool = False,
) -> None:
    source = build_bin_dir / binary_name
    target = macos_dir / binary_name
    if onefile:
        if not source.is_file():
            raise FileNotFoundError(f"Missing PyInstaller onefile output: {source}")
        shutil.copy2(source, target)
        target.chmod(0o755)
        return

    if not source.is_dir():
        raise FileNotFoundError(f"Missing PyInstaller onedir output: {source}")
    target_dir = macos_dir / appdir_name(binary_name)
    remove_path(target_dir)
    shutil.copytree(source, target_dir)
    executable = target_dir / binary_name
    if not executable.is_file():
        raise FileNotFoundError(f"Missing PyInstaller onedir executable: {executable}")
    executable.chmod(0o755)
    write_appdir_wrapper(target, binary_name, pass_app_bundle=pass_app_bundle)


def build_pyinstaller_target(
    python_exe: Path,
    entrypoint: Path,
    name: str,
    dist_dir: Path,
    *,
    onefile: bool = False,
    hidden_imports: list[str] | None = None,
    windowed: bool = False,
) -> None:
    remove_path(dist_dir / name)
    run_pyinstaller(
        python_exe,
        entrypoint,
        name,
        dist_dir,
        onefile=onefile,
        hidden_imports=hidden_imports,
        windowed=windowed,
    )


def sign_app_bundle(app_bundle: Path) -> None:
    if not shutil.which("codesign"):
        return
    subprocess.run(
        [
            "codesign",
            "--force",
            "--deep",
            "--sign",
            "-",
            str(app_bundle),
        ],
        cwd=str(ROOT),
        check=True,
    )


def build_app(dist_dir: Path, venv_dir: Path = DEFAULT_VENV_DIR) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_bin_dir = dist_dir / "bin"
    build_bin_dir.mkdir(parents=True, exist_ok=True)
    python_exe = prepare_build_venv(venv_dir)

    build_pyinstaller_target(
        python_exe,
        ROOT / "packaging" / "macos" / "launcher" / "launcher_main.py",
        APP_NAME,
        build_bin_dir,
    )
    build_pyinstaller_target(
        python_exe,
        ROOT / "packaging" / "macos" / "service" / "service_main.py",
        f"{APP_NAME} Service",
        build_bin_dir,
        hidden_imports=MAC_SERVICE_HIDDEN_IMPORTS,
    )
    build_pyinstaller_target(
        python_exe,
        ROOT / "packaging" / "macos" / "updater" / "updater_main.py",
        f"{APP_NAME} Updater",
        build_bin_dir,
    )

    app_bundle = dist_dir / f"{APP_NAME}.app"
    if app_bundle.exists():
        shutil.rmtree(app_bundle)
    macos_dir = app_bundle / "Contents" / "MacOS"
    resources_dir = app_bundle / "Contents" / "Resources"
    bootstrap_dir = resources_dir / "bootstrap"
    macos_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_dir.mkdir(parents=True, exist_ok=True)

    for binary_name in (APP_NAME, f"{APP_NAME} Service", f"{APP_NAME} Updater"):
        install_pyinstaller_output(
            build_bin_dir,
            macos_dir,
            binary_name,
            pass_app_bundle=binary_name == APP_NAME,
        )

    build_payload(DEFAULT_OUTPUT)
    shutil.copy2(DEFAULT_OUTPUT, bootstrap_dir / "app-base.zip")
    shutil.copy2(DEFAULT_MANIFEST, bootstrap_dir / "manifest.json")
    write_info_plist(app_bundle, read_version())
    sign_app_bundle(app_bundle)
    return app_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Build macOS .app bundle for Infinite Canvas.")
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST_DIR)
    parser.add_argument("--venv-dir", type=Path, default=DEFAULT_VENV_DIR)
    args = parser.parse_args()

    app_bundle = build_app(args.dist_dir, args.venv_dir)
    print(app_bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
