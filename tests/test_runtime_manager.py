import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from packaging.windows.launcher.runtime_manager import (
    create_update_backup,
    current_payload_version,
    current_release_name,
    ensure_runtime_release,
    list_launcher_backups,
    load_launcher_state,
    launch_server,
    persist_selected_port,
    replace_in_place_payload,
    rollback_launcher_backup,
    select_launch_port,
)
from packaging.windows.launcher.layout import LaunchLayout, MODE_RUNTIME


class RuntimeManagerTests(unittest.TestCase):
    def test_ensure_runtime_release_extracts_payload(self):
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            install_dir = base / "install"
            install_dir.mkdir()
            bootstrap = install_dir / "bootstrap"
            bootstrap.mkdir()
            payload = bootstrap / "app-base.zip"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("main.py", "print('ok')\n")

            layout = LaunchLayout(
                install_dir=install_dir,
                storage_root=base / "storage",
                data_root=base / "storage" / "data",
                logs_root=base / "storage" / "logs",
                backups_root=base / "storage" / "backups",
                runtime_root=base / "storage" / "runtime",
                mode=MODE_RUNTIME,
                work_dir=base / "storage" / "runtime" / "v1",
            )

            release = ensure_runtime_release(layout, install_dir, "v1")

            self.assertTrue((release / "main.py").exists())

    def test_current_release_name_falls_back_to_payload_version(self):
        with tempfile.TemporaryDirectory() as tempdir:
            install_dir = Path(tempdir)
            bootstrap = install_dir / "bootstrap"
            bootstrap.mkdir()
            payload = bootstrap / "app-base.zip"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("VERSION", "2026.05.24.1\n")

            self.assertEqual(current_release_name(install_dir), "2026.05.24.1")

    def test_current_payload_version_uses_runtime_version_after_hot_update(self):
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
            (install_dir / "current.txt").write_text("2026.05.24.1\n", encoding="utf-8")
            runtime_release = storage_root / "runtime" / "2026.05.24.1"
            runtime_release.mkdir(parents=True)
            (runtime_release / "VERSION").write_text("2026.05.25.3\n", encoding="utf-8")

            self.assertEqual(current_payload_version(install_dir), "2026.05.25.3")

    def test_launch_server_prefers_packaged_service_executable(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            install_dir = root / "install"
            service_dir = install_dir / "Infinite Canvas Service"
            service_dir.mkdir(parents=True)
            service = service_dir / "Infinite Canvas Service.exe"
            service.write_text("service", encoding="utf-8")
            bootstrap = install_dir / "bootstrap"
            bootstrap.mkdir()
            (bootstrap / "manifest.json").write_text("{}", encoding="utf-8")
            layout = LaunchLayout(
                install_dir=install_dir,
                storage_root=root / "storage",
                data_root=root / "storage" / "data",
                logs_root=root / "storage" / "logs",
                backups_root=root / "storage" / "backups",
                runtime_root=root / "storage" / "runtime",
                mode=MODE_RUNTIME,
                work_dir=root / "runtime" / "v1",
            )

            with mock.patch("packaging.windows.launcher.runtime_manager.subprocess.Popen") as popen:
                launch_server(layout, launcher_exe="launcher.exe", port=3007)

            args, kwargs = popen.call_args
            self.assertEqual(args[0], [str(service)])
            self.assertEqual(kwargs["cwd"], str(layout.work_dir))
            self.assertEqual(kwargs["env"]["INFINITE_CANVAS_PORT"], "3007")

    def test_replace_in_place_payload_preserves_bootstrap_files(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            target = root / "app"
            target.mkdir()
            (target / "launcher.exe").write_text("launcher", encoding="utf-8")
            bootstrap = target / "bootstrap"
            bootstrap.mkdir()
            (bootstrap / "manifest.json").write_text("{}", encoding="utf-8")

            payload = root / "payload.zip"
            with zipfile.ZipFile(payload, "w") as archive:
                archive.writestr("main.py", "print('new')\n")
                archive.writestr("static/index.html", "<html></html>\n")

            replace_in_place_payload(target, payload)

            self.assertTrue((target / "launcher.exe").exists())
            self.assertTrue((target / "bootstrap" / "manifest.json").exists())
            self.assertTrue((target / "main.py").exists())
            self.assertTrue((target / "static" / "index.html").exists())

    def test_in_place_backup_can_be_rolled_back(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            install_dir = root / "app"
            storage_root = root / "storage"
            install_dir.mkdir()
            (install_dir / "bootstrap").mkdir()
            (install_dir / "bootstrap" / "manifest.json").write_text(
                '{"payload_entries":["main.py","VERSION"]}\n',
                encoding="utf-8",
            )
            (install_dir / "install-meta.ini").write_text(
                f"[paths]\nstorage_root={storage_root}\n",
                encoding="utf-8",
            )
            (install_dir / "VERSION").write_text("2026.05.24.1\n", encoding="utf-8")
            (install_dir / "main.py").write_text("print('before')\n", encoding="utf-8")

            backup = create_update_backup(install_dir, "2026.05.25.1")
            (install_dir / "VERSION").write_text("2026.05.25.1\n", encoding="utf-8")
            (install_dir / "main.py").write_text("print('after')\n", encoding="utf-8")

            result = rollback_launcher_backup(install_dir, backup["id"])

            self.assertEqual(result["restored_version"], "2026.05.24.1")
            self.assertEqual((install_dir / "main.py").read_text(encoding="utf-8"), "print('before')\n")
            self.assertEqual((install_dir / "VERSION").read_text(encoding="utf-8"), "2026.05.24.1\n")
            backups = list_launcher_backups(install_dir)
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0]["source_version"], "2026.05.24.1")

    def test_runtime_backup_rolls_pointer_back(self):
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
            (install_dir / "current.txt").write_text("2026.05.24.1\n", encoding="utf-8")
            runtime_release = storage_root / "runtime" / "2026.05.24.1"
            runtime_release.mkdir(parents=True)
            (runtime_release / "main.py").write_text("print('runtime')\n", encoding="utf-8")

            with mock.patch("packaging.windows.launcher.layout.is_directory_writable", return_value=False):
                backup = create_update_backup(install_dir, "2026.05.25.1")
                (install_dir / "current.txt").write_text("2026.05.25.1\n", encoding="utf-8")
                result = rollback_launcher_backup(install_dir, backup["id"])

            self.assertEqual(result["restored_version"], "2026.05.24.1")
            self.assertEqual((install_dir / "current.txt").read_text(encoding="utf-8").strip(), "2026.05.24.1")
            self.assertEqual(result["count"], 1)

    def test_select_launch_port_prefers_requested_port(self):
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            layout = LaunchLayout(
                install_dir=base / "install",
                storage_root=base / "storage",
                data_root=base / "storage" / "data",
                logs_root=base / "storage" / "logs",
                backups_root=base / "storage" / "backups",
                runtime_root=base / "storage" / "runtime",
                mode=MODE_RUNTIME,
                work_dir=base / "storage" / "runtime" / "v1",
            )
            layout.data_root.mkdir(parents=True, exist_ok=True)

            with mock.patch("packaging.windows.launcher.runtime_manager.is_port_available", side_effect=lambda port: port == 3005):
                port, changed = select_launch_port(layout, preferred_port=3005)

            self.assertEqual(port, 3005)
            self.assertFalse(changed)

    def test_select_launch_port_falls_back_and_persists_last_port(self):
        with tempfile.TemporaryDirectory() as tempdir:
            base = Path(tempdir)
            layout = LaunchLayout(
                install_dir=base / "install",
                storage_root=base / "storage",
                data_root=base / "storage" / "data",
                logs_root=base / "storage" / "logs",
                backups_root=base / "storage" / "backups",
                runtime_root=base / "storage" / "runtime",
                mode=MODE_RUNTIME,
                work_dir=base / "storage" / "runtime" / "v1",
            )
            layout.data_root.mkdir(parents=True, exist_ok=True)

            with mock.patch("packaging.windows.launcher.runtime_manager.is_port_available", side_effect=lambda port: port == 3001):
                port, changed = select_launch_port(layout, preferred_port=3000)
            self.assertEqual(port, 3001)
            self.assertTrue(changed)

            persist_selected_port(layout, port)
            state = load_launcher_state(layout)
            self.assertEqual(state["last_port"], 3001)


if __name__ == "__main__":
    unittest.main()
