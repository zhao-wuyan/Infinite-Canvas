import unittest
from pathlib import Path


class ReleaseWorkflowTests(unittest.TestCase):
    def test_release_workflow_uploads_prefixed_and_legacy_update_assets(self):
        workflow = Path(".github/workflows/release-installers.yml").read_text(encoding="utf-8")

        for asset in (
            "windows-VERSION",
            "windows-manifest.json",
            "windows-app-base.zip",
            "macos-VERSION",
            "macos-manifest.json",
            "macos-app-base.zip",
        ):
            self.assertIn(asset, workflow)

        for legacy_asset in ("VERSION", "manifest.json", "app-base.zip"):
            self.assertIn(f"dist\\release-assets\\{legacy_asset}", workflow)


if __name__ == "__main__":
    unittest.main()
