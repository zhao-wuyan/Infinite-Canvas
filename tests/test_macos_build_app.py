import unittest
from pathlib import Path
from unittest.mock import patch

from packaging.macos.build_app import APP_NAME, run_pyinstaller


class MacBuildAppTests(unittest.TestCase):
    def test_run_pyinstaller_accepts_hidden_imports(self):
        dist_dir = Path("/tmp/dist")
        entrypoint = Path("/tmp/service_main.py")
        hidden = ["fastapi.staticfiles", "PIL.Image"]

        with patch("packaging.macos.build_app.subprocess.run") as mocked_run:
            run_pyinstaller(entrypoint, f"{APP_NAME} Service", dist_dir, hidden_imports=hidden)

        self.assertEqual(mocked_run.call_count, 1)
        args = mocked_run.call_args.args[0]
        self.assertIn("--hidden-import", args)
        self.assertIn("fastapi.staticfiles", args)
        self.assertIn("PIL.Image", args)


if __name__ == "__main__":
    unittest.main()
