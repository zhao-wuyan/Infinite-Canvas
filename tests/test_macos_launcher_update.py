import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest import mock

from packaging.macos.launcher.launcher_main import (
    apply_update_result,
    check_for_updates,
    try_auto_update_before_launch,
)
from packaging.macos.launcher.layout import compute_layout


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


if __name__ == "__main__":
    unittest.main()
