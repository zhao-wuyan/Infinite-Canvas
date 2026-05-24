from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Windows launcher and updater executables.")
    parser.add_argument("--dist-dir", type=Path, default=ROOT / "dist" / "windows")
    args = parser.parse_args()

    args.dist_dir.mkdir(parents=True, exist_ok=True)
    run_pyinstaller(ROOT / "packaging" / "windows" / "launcher" / "launcher_main.py", "Infinite Canvas", args.dist_dir)
    run_pyinstaller(ROOT / "packaging" / "windows" / "updater" / "updater_main.py", "Infinite Canvas Updater", args.dist_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
