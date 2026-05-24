import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from packaging.macos.publish_release import publish_release


class MacPublishReleaseTests(unittest.TestCase):
    def test_publish_release_builds_static_update_tree(self):
        with tempfile.TemporaryDirectory() as tempdir:
            output_dir = Path(tempdir) / "release"

            result = publish_release(output_dir, update_base_url="https://example.com/macos")

            version = Path("VERSION").read_text(encoding="utf-8").strip().splitlines()[0].strip()
            self.assertEqual(result["version"], version)
            self.assertTrue((output_dir / "VERSION").exists())
            self.assertTrue((output_dir / "manifest.json").exists())
            self.assertTrue((output_dir / "app-base.zip").exists())
            self.assertTrue((output_dir / version / "manifest.json").exists())

            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["platform"], "macos")
            self.assertEqual(manifest["update_base_url"], "https://example.com/macos")
            self.assertNotIn("python/python.exe", manifest["payload_entries"])

            with zipfile.ZipFile(output_dir / "app-base.zip") as archive:
                names = set(archive.namelist())
            self.assertIn("main.py", names)
            self.assertIn("app_runtime.py", names)
            self.assertNotIn("python/python.exe", names)


if __name__ == "__main__":
    unittest.main()
