import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from packaging.macos.build_app import APP_NAME
from packaging.macos.build_dmg import build_dmg


class MacBuildDmgTests(unittest.TestCase):
    def test_build_dmg_reuses_existing_app_bundle(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            dist_dir = root / "dist"
            app_bundle = dist_dir / f"{APP_NAME}.app"
            app_bundle.mkdir(parents=True)

            with (
                patch("packaging.macos.build_dmg.build_app") as build_app,
                patch("packaging.macos.build_dmg.shutil.copytree"),
                patch.object(Path, "symlink_to"),
                patch("packaging.macos.build_dmg.subprocess.run"),
                patch("packaging.macos.build_dmg.read_version", return_value="1.2.3"),
            ):
                dmg_path = build_dmg(dist_dir, app_bundle)

        build_app.assert_not_called()
        self.assertEqual(dmg_path, dist_dir / f"{APP_NAME}-1.2.3.dmg")


if __name__ == "__main__":
    unittest.main()
