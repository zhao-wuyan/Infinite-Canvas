from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

from packaging.macos.payload.build_payload import DEFAULT_MANIFEST, DEFAULT_OUTPUT, build_payload


ROOT = Path(__file__).resolve().parents[2]
APP_NAME = "Infinite Canvas"
DEFAULT_DIST_DIR = ROOT / "dist" / "macos"


def run_pyinstaller(entrypoint: Path, name: str, dist_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--onefile",
            "--name",
            name,
            "--distpath",
            str(dist_dir),
            str(entrypoint),
        ],
        cwd=str(ROOT),
        check=True,
    )


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


def build_app(dist_dir: Path) -> Path:
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_bin_dir = dist_dir / "bin"
    build_bin_dir.mkdir(parents=True, exist_ok=True)

    run_pyinstaller(ROOT / "packaging" / "macos" / "launcher" / "launcher_main.py", APP_NAME, build_bin_dir)
    run_pyinstaller(ROOT / "packaging" / "macos" / "service" / "service_main.py", f"{APP_NAME} Service", build_bin_dir)
    run_pyinstaller(ROOT / "packaging" / "macos" / "updater" / "updater_main.py", f"{APP_NAME} Updater", build_bin_dir)

    app_bundle = dist_dir / f"{APP_NAME}.app"
    if app_bundle.exists():
        shutil.rmtree(app_bundle)
    macos_dir = app_bundle / "Contents" / "MacOS"
    resources_dir = app_bundle / "Contents" / "Resources"
    bootstrap_dir = resources_dir / "bootstrap"
    macos_dir.mkdir(parents=True, exist_ok=True)
    bootstrap_dir.mkdir(parents=True, exist_ok=True)

    for binary_name in (APP_NAME, f"{APP_NAME} Service", f"{APP_NAME} Updater"):
        shutil.copy2(build_bin_dir / binary_name, macos_dir / binary_name)
        (macos_dir / binary_name).chmod(0o755)

    build_payload(DEFAULT_OUTPUT)
    shutil.copy2(DEFAULT_OUTPUT, bootstrap_dir / "app-base.zip")
    shutil.copy2(DEFAULT_MANIFEST, bootstrap_dir / "manifest.json")
    write_info_plist(app_bundle, read_version())
    return app_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Build macOS .app bundle for Infinite Canvas.")
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST_DIR)
    args = parser.parse_args()

    app_bundle = build_app(args.dist_dir)
    print(app_bundle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
