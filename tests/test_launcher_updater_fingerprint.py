import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from packaging.macos.updater import updater_main as macos_updater
from packaging.windows.updater import updater_main as windows_updater
from packaging.windows.launcher.runtime_manager import PAYLOAD_FINGERPRINT_FILE, payload_fingerprint


class LauncherUpdaterFingerprintTests(unittest.TestCase):
    def test_windows_runtime_update_writes_payload_fingerprint(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            install_dir = root / "app"
            storage_root = root / "storage"
            install_dir.mkdir()
            (install_dir / "bootstrap").mkdir()
            (install_dir / "bootstrap" / "manifest.json").write_text("{}", encoding="utf-8")
            (install_dir / "install-meta.ini").write_text(
                f"[paths]\nstorage_root={storage_root}\n",
                encoding="utf-8",
            )
            payload = root / "payload.zip"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("VERSION", "2026.05.30\n")
                archive.writestr("main.py", "print('updated')\n")

            with mock.patch("sys.argv", [
                "updater",
                "--install-dir",
                str(install_dir),
                "--payload",
                str(payload),
                "--release-name",
                "2026.05.30",
            ]), mock.patch("packaging.windows.launcher.layout.is_directory_writable", return_value=False):
                self.assertEqual(windows_updater.main(), 0)

            release = storage_root / "runtime" / "2026.05.30"
            self.assertEqual(
                (release / PAYLOAD_FINGERPRINT_FILE).read_text(encoding="utf-8").strip(),
                payload_fingerprint(payload),
            )

    def test_macos_runtime_update_writes_payload_fingerprint(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            app_bundle = root / "Infinite Canvas.app"
            storage_root = root / "storage"
            payload = root / "payload.zip"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("VERSION", "2026.05.30\n")
                archive.writestr("main.py", "print('updated')\n")

            with mock.patch("sys.argv", [
                "updater",
                "--app-bundle",
                str(app_bundle),
                "--storage-root",
                str(storage_root),
                "--payload",
                str(payload),
                "--release-name",
                "2026.05.30",
            ]):
                self.assertEqual(macos_updater.main(), 0)

            release = storage_root / "runtime" / "2026.05.30"
            self.assertEqual(
                (release / PAYLOAD_FINGERPRINT_FILE).read_text(encoding="utf-8").strip(),
                payload_fingerprint(payload),
            )
