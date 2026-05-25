import unittest
from pathlib import Path
from unittest.mock import patch

from packaging.macos.build_app import APP_NAME, prepare_build_venv, run_pyinstaller, venv_python


class MacBuildAppTests(unittest.TestCase):
    def test_run_pyinstaller_accepts_hidden_imports(self):
        dist_dir = Path("/tmp/dist")
        entrypoint = Path("/tmp/service_main.py")
        hidden = ["fastapi.staticfiles", "PIL.Image"]
        python_exe = Path("/tmp/venv/bin/python")

        with patch("packaging.macos.build_app.subprocess.run") as mocked_run:
            run_pyinstaller(python_exe, entrypoint, f"{APP_NAME} Service", dist_dir, hidden_imports=hidden)

        self.assertEqual(mocked_run.call_count, 1)
        args = mocked_run.call_args.args[0]
        self.assertEqual(args[0], str(python_exe))
        self.assertIn("--hidden-import", args)
        self.assertIn("fastapi.staticfiles", args)
        self.assertIn("PIL.Image", args)

    def test_run_pyinstaller_accepts_windowed_mode(self):
        dist_dir = Path("/tmp/dist")
        entrypoint = Path("/tmp/launcher_main.py")
        python_exe = Path("/tmp/venv/bin/python")

        with patch("packaging.macos.build_app.subprocess.run") as mocked_run:
            run_pyinstaller(python_exe, entrypoint, APP_NAME, dist_dir, windowed=True)

        args = mocked_run.call_args.args[0]
        self.assertIn("--windowed", args)

    def test_run_pyinstaller_skips_windowed_flag_by_default(self):
        dist_dir = Path("/tmp/dist")
        entrypoint = Path("/tmp/launcher_main.py")
        python_exe = Path("/tmp/venv/bin/python")

        with patch("packaging.macos.build_app.subprocess.run") as mocked_run:
            run_pyinstaller(python_exe, entrypoint, APP_NAME, dist_dir)

        args = mocked_run.call_args.args[0]
        self.assertNotIn("--windowed", args)

    def test_venv_python_uses_bin_python(self):
        self.assertEqual(venv_python(Path("/tmp/build-venv")), Path("/tmp/build-venv/bin/python"))

    def test_prepare_build_venv_creates_missing_venv_and_installs_dependencies(self):
        venv_dir = Path("/tmp/build-venv")
        python_exe = venv_python(venv_dir)

        with (
            patch.object(Path, "exists", return_value=False),
            patch("packaging.macos.build_app.venv.EnvBuilder") as env_builder,
            patch("packaging.macos.build_app.subprocess.run") as mocked_run,
        ):
            resolved = prepare_build_venv(venv_dir)

        env_builder.assert_called_once_with(with_pip=True, clear=True)
        env_builder.return_value.create.assert_called_once_with(venv_dir)
        mocked_run.assert_called_once()
        pip_command = mocked_run.call_args.args[0]
        self.assertEqual(pip_command[:4], [str(python_exe), "-m", "pip", "install"])
        self.assertEqual(resolved, python_exe)


if __name__ == "__main__":
    unittest.main()
