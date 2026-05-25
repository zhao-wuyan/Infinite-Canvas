import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

from packaging.macos.launcher.launcher_main import (
    apply_update_result,
    check_for_updates_and_remember,
    check_for_updates,
    has_management_action,
    launch_in_terminal,
    should_spawn_terminal,
    terminal_script_path,
    write_terminal_launcher_script,
    try_auto_update_before_launch,
)
from packaging.macos.launcher.layout import compute_layout
from packaging.macos.launcher.runtime_manager import load_launcher_state, resolve_runtime_context


def create_app_bundle(root: Path, version: str = "2026.05.24.1") -> tuple[Path, Path]:
    app_bundle = root / "Infinite Canvas.app"
    storage_root = root / "storage"
    bootstrap = app_bundle / "Contents" / "Resources" / "bootstrap"
    bootstrap.mkdir(parents=True)
    (bootstrap / "manifest.json").write_text(
        '{"update_base_url":"https://example.com/releases","payload_endpoint":"app-base.zip"}\n',
        encoding="utf-8",
    )
    with zipfile.ZipFile(bootstrap / "app-base.zip", "w") as archive:
        archive.writestr("VERSION", f"{version}\n")
        archive.writestr("main.py", "print('bootstrap')\n")

    layout = compute_layout(app_bundle, storage_root=storage_root, release_name=version)
    runtime_release = layout.runtime_root / version
    runtime_release.mkdir(parents=True)
    (runtime_release / "VERSION").write_text(f"{version}\n", encoding="utf-8")
    (runtime_release / "main.py").write_text("print('old')\n", encoding="utf-8")
    layout.current_release_file.parent.mkdir(parents=True, exist_ok=True)
    layout.current_release_file.write_text(f"{version}\n", encoding="utf-8")
    return app_bundle, storage_root


class MacLauncherUpdateTests(unittest.TestCase):
    def test_has_management_action_detects_control_flags(self):
        args = mock.Mock(check_update=False, apply_update=False, list_backups=True, rollback_backup="")

        self.assertTrue(has_management_action(args))

    def test_should_spawn_terminal_when_not_attached_to_tty(self):
        args = mock.Mock(check_update=False, apply_update=False, list_backups=False, rollback_backup="")

        with mock.patch("packaging.macos.launcher.launcher_main.running_in_terminal", return_value=False), \
            mock.patch.dict("os.environ", {}, clear=False):
            self.assertTrue(should_spawn_terminal(args))

    def test_should_not_spawn_terminal_when_already_attached(self):
        args = mock.Mock(check_update=False, apply_update=False, list_backups=False, rollback_backup="")

        with mock.patch.dict("os.environ", {"INFINITE_CANVAS_TERMINAL_ATTACHED": "1"}, clear=False):
            self.assertFalse(should_spawn_terminal(args))

    def test_write_terminal_launcher_script_exports_terminal_flag(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")

            with mock.patch("packaging.macos.launcher.launcher_main.sys.executable", "/Applications/Infinite Canvas.app/Contents/MacOS/Infinite Canvas"):
                script_path = write_terminal_launcher_script(app_bundle, storage_root=storage_root, no_browser=True)

            content = script_path.read_text(encoding="utf-8")

        self.assertEqual(script_path.name, "Infinite Canvas.command")
        self.assertIn("export INFINITE_CANVAS_TERMINAL_ATTACHED=1", content)
        self.assertIn("printf '\\033]0;Infinite Canvas\\007'", content)
        self.assertIn("请不要关闭此终端窗口", content)
        self.assertIn("--no-browser", content)
        self.assertIn("--app-bundle", content)

    def test_terminal_script_path_uses_app_name_for_terminal_title(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")

            script_path = terminal_script_path(app_bundle, storage_root=storage_root)

        self.assertEqual(script_path.name, "Infinite Canvas.command")

    def test_launch_in_terminal_uses_open_terminal(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")
            fake_script = storage_root / "data" / "Infinite Canvas.command"

            with mock.patch("packaging.macos.launcher.launcher_main.write_terminal_launcher_script", return_value=fake_script), \
                mock.patch("packaging.macos.launcher.launcher_main.subprocess.run") as run:
                run.return_value.returncode = 0
                ok = launch_in_terminal(app_bundle, storage_root=storage_root, no_browser=False)

        self.assertTrue(ok)
        self.assertEqual(run.call_args.args[0], ["open", "-a", "Terminal", str(fake_script)])

    def test_check_for_updates_detects_remote_newer_version(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")

            with mock.patch("packaging.macos.launcher.launcher_main.fetch_text", return_value="2026.05.25.3\n"):
                result = check_for_updates(app_bundle, storage_root=storage_root)

        self.assertTrue(result["ok"])
        self.assertEqual(result["current_version"], "2026.05.24.1")
        self.assertEqual(result["remote_version"], "2026.05.25.3")
        self.assertTrue(result["has_update"])

    def test_check_for_updates_treats_runtime_hot_update_as_current(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")
            runtime_version = storage_root / "runtime" / "2026.05.24.1" / "VERSION"
            runtime_version.write_text("2026.05.25.3\n", encoding="utf-8")

            with mock.patch("packaging.macos.launcher.launcher_main.fetch_text", return_value="2026.05.25.3\n"):
                result = check_for_updates(app_bundle, storage_root=storage_root)

        self.assertEqual(result["current_version"], "2026.05.25.3")
        self.assertFalse(result["has_update"])

    def test_check_for_updates_skips_missing_remote_version(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")
            error = urllib.error.HTTPError("https://example.com/releases/VERSION", 404, "Not Found", {}, None)

            with mock.patch("packaging.macos.launcher.launcher_main.fetch_text", side_effect=error):
                result = check_for_updates(app_bundle, storage_root=storage_root)

        self.assertTrue(result["ok"])
        self.assertTrue(result["skipped"])
        self.assertFalse(result["has_update"])

    def test_check_for_updates_falls_back_to_prefixed_version_asset(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")
            requested_urls: list[str] = []

            def fake_fetch_text(url: str) -> str:
                requested_urls.append(url)
                if url.endswith("/VERSION"):
                    raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
                return "2026.05.25.3\n"

            with mock.patch("packaging.macos.launcher.launcher_main.fetch_text", side_effect=fake_fetch_text):
                result = check_for_updates(app_bundle, storage_root=storage_root)

        self.assertTrue(result["has_update"])
        self.assertEqual(
            requested_urls,
            [
                "https://example.com/releases/VERSION",
                "https://example.com/releases/macos-VERSION",
            ],
        )

    def test_apply_update_downloads_payload_and_invokes_updater(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")
            updater = app_bundle / "Contents" / "MacOS" / "Infinite Canvas Updater"
            updater.parent.mkdir(parents=True, exist_ok=True)
            updater.write_text("updater", encoding="utf-8")
            fake_response = mock.Mock()
            fake_response.__enter__ = mock.Mock(return_value=fake_response)
            fake_response.__exit__ = mock.Mock(return_value=None)
            fake_response.read.return_value = b"payload-bytes"

            with mock.patch("packaging.macos.launcher.launcher_main.fetch_text", return_value="2026.05.25.3\n"), \
                mock.patch("packaging.macos.launcher.launcher_main.urllib.request.urlopen", return_value=fake_response) as urlopen, \
                mock.patch("packaging.macos.launcher.launcher_main.subprocess.run") as run:
                run.return_value.returncode = 0
                result = apply_update_result(app_bundle, storage_root=storage_root)

            self.assertTrue(result["ok"])
            self.assertTrue(result["updated"])
            self.assertTrue(result["backup"]["id"])
            self.assertEqual(urlopen.call_args.args[0], "https://example.com/releases/app-base.zip")
            command = run.call_args.args[0]
            self.assertEqual(Path(command[0]).resolve(), updater.resolve())
            self.assertIn("--release-name", command)
            self.assertIn("2026.05.25.3", command)

    def test_apply_update_falls_back_to_prefixed_payload_asset(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")
            updater = app_bundle / "Contents" / "MacOS" / "Infinite Canvas Updater"
            updater.parent.mkdir(parents=True, exist_ok=True)
            updater.write_text("updater", encoding="utf-8")
            fake_response = mock.Mock()
            fake_response.__enter__ = mock.Mock(return_value=fake_response)
            fake_response.__exit__ = mock.Mock(return_value=None)
            fake_response.read.return_value = b"payload-bytes"
            requested_urls: list[str] = []

            def fake_urlopen(url: str, timeout: int = 0):
                requested_urls.append(url)
                if url.endswith("/app-base.zip"):
                    raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
                return fake_response

            with mock.patch("packaging.macos.launcher.launcher_main.fetch_text", return_value="2026.05.25.3\n"), \
                mock.patch("packaging.macos.launcher.launcher_main.urllib.request.urlopen", side_effect=fake_urlopen), \
                mock.patch("packaging.macos.launcher.launcher_main.subprocess.run") as run:
                run.return_value.returncode = 0
                result = apply_update_result(app_bundle, storage_root=storage_root)

        self.assertTrue(result["updated"])
        self.assertEqual(
            requested_urls,
            [
                "https://example.com/releases/app-base.zip",
                "https://example.com/releases/macos-app-base.zip",
            ],
        )

    def test_auto_update_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")

            with mock.patch.dict("os.environ", {"INFINITE_CANVAS_AUTO_UPDATE": "0"}), \
                mock.patch("packaging.macos.launcher.launcher_main.apply_update_result") as apply_update:
                result = try_auto_update_before_launch(app_bundle, storage_root=storage_root)

        self.assertTrue(result["ok"])
        self.assertTrue(result["skipped"])
        apply_update.assert_not_called()

    def test_auto_update_does_not_check_network_without_pending_update(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")

            with mock.patch("packaging.macos.launcher.launcher_main.apply_update_result") as apply_update:
                result = try_auto_update_before_launch(app_bundle, storage_root=storage_root)

        self.assertTrue(result["ok"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["detail"], "no pending update")
        apply_update.assert_not_called()

    def test_check_for_updates_records_pending_update_for_next_launch(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")

            with mock.patch("packaging.macos.launcher.launcher_main.fetch_text", return_value="2026.05.25.3\n"):
                result = check_for_updates_and_remember(app_bundle, storage_root=storage_root)
            state = load_launcher_state(resolve_runtime_context(app_bundle, storage_root=storage_root))

        self.assertTrue(result["has_update"])
        self.assertTrue(result["pending_update"])
        self.assertEqual(state["pending_update"]["remote_version"], "2026.05.25.3")

    def test_auto_update_applies_pending_update_on_next_launch(self):
        with tempfile.TemporaryDirectory() as tempdir:
            app_bundle, storage_root = create_app_bundle(Path(tempdir), "2026.05.24.1")
            with mock.patch("packaging.macos.launcher.launcher_main.fetch_text", return_value="2026.05.25.3\n"):
                check_for_updates_and_remember(app_bundle, storage_root=storage_root)

            with mock.patch("packaging.macos.launcher.launcher_main.apply_update_result", return_value={"ok": True, "updated": True}) as apply_update:
                result = try_auto_update_before_launch(app_bundle, storage_root=storage_root)

        self.assertTrue(result["updated"])
        apply_update.assert_called_once_with(app_bundle, storage_root=storage_root)


if __name__ == "__main__":
    unittest.main()
