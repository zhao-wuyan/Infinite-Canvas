from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packaging.macos.build_app import APP_NAME, DEFAULT_DIST_DIR, build_app, read_version


def build_dmg(dist_dir: Path) -> Path:
    app_bundle = build_app(dist_dir)
    version = read_version()
    dmg_path = dist_dir / f"{APP_NAME}-{version}.dmg"
    staging_dir = dist_dir / "dmg-root"
    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    staging_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app_bundle, staging_dir / app_bundle.name)
    applications_link = staging_dir / "Applications"
    if not applications_link.exists():
        applications_link.symlink_to("/Applications")
    if dmg_path.exists():
        dmg_path.unlink()
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(staging_dir),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ],
        cwd=str(ROOT),
        check=True,
    )
    return dmg_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build macOS DMG for Infinite Canvas.")
    parser.add_argument("--dist-dir", type=Path, default=DEFAULT_DIST_DIR)
    args = parser.parse_args()

    dmg_path = build_dmg(args.dist_dir)
    print(dmg_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
