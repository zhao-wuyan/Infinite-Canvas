import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from packaging.windows.build_launcher import APP_NAME, prepare_app_icon, run_pyinstaller


class WindowsBuildLauncherTests(unittest.TestCase):
    def test_run_pyinstaller_accepts_icon_path(self):
        python_exe = Path("C:/venv/Scripts/python.exe")
        entrypoint = Path("C:/project/launcher_main.py")
        dist_dir = Path("C:/project/dist")
        icon_path = Path("C:/project/build/icons/infinite-canvas.ico")

        with patch("packaging.windows.build_launcher.subprocess.run") as mocked_run:
            run_pyinstaller(python_exe, entrypoint, APP_NAME, dist_dir, icon_path=icon_path)

        args = mocked_run.call_args.args[0]
        self.assertIn("--icon", args)
        self.assertIn(str(icon_path), args)

    def test_prepare_app_icon_generates_ico_from_png(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            source = root / "logo.png"
            output = root / "infinite-canvas.ico"
            python_exe = root / "venv" / "Scripts" / "python.exe"
            source.write_bytes(b"png")

            with patch("packaging.windows.build_launcher.subprocess.run") as mocked_run:
                resolved = prepare_app_icon(python_exe, source, output)

            self.assertEqual(resolved, output)
            command = mocked_run.call_args.args[0]
            self.assertEqual(command[0], str(python_exe))
            self.assertIn(str(source), command)
            self.assertIn(str(output), command)
            self.assertTrue(output.parent.exists())


if __name__ == "__main__":
    unittest.main()
