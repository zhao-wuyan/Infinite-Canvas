from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import urllib.request
import webbrowser
from pathlib import Path

from app_runtime import DEFAULT_APP_PORT, app_base_url
from packaging.windows.launcher.runtime_manager import (
    compare_versions,
    create_update_backup,
    current_release_name,
    launch_server,
    list_launcher_backups,
    read_manifest,
    rollback_launcher_backup,
    select_launch_port,
    persist_selected_port,
    resolve_runtime_context,
    wait_for_server,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Infinite Canvas Windows launcher")
    parser.add_argument("--install-dir", type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--check-update", action="store_true")
    parser.add_argument("--apply-update", action="store_true")
    parser.add_argument("--list-backups", action="store_true")
    parser.add_argument("--rollback-backup", default="")
    return parser.parse_args()


def join_update_url(base_url: str, endpoint: str) -> str:
    return base_url.rstrip("/") + "/" + endpoint.lstrip("/")


def fetch_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


def check_for_updates(install_dir: Path) -> dict[str, str | bool]:
    manifest = read_manifest(install_dir)
    base_url = str(manifest.get("update_base_url") or "").strip()
    if not base_url:
        return {"ok": False, "detail": "未配置 update_base_url。"}
    current = current_release_name(install_dir)
    remote = fetch_text(join_update_url(base_url, str(manifest.get("version_endpoint") or "VERSION"))).strip().splitlines()[0].strip()
    return {
        "ok": True,
        "current_version": current,
        "remote_version": remote,
        "has_update": compare_versions(remote, current) > 0,
    }


def launcher_runtime_status(install_dir: Path) -> dict[str, str | bool]:
    layout = resolve_runtime_context(install_dir)
    selected_port, port_changed = select_launch_port(layout)
    return {
        "ok": True,
        "port": selected_port,
        "port_changed": port_changed,
        "default_port": DEFAULT_APP_PORT,
        "local_url": app_base_url(selected_port) + "/",
        "mode": layout.mode,
    }


def apply_update(install_dir: Path) -> int:
    manifest = read_manifest(install_dir)
    base_url = str(manifest.get("update_base_url") or "").strip()
    if not base_url:
        print(json.dumps({"ok": False, "detail": "未配置 update_base_url。"}, ensure_ascii=False))
        return 1
    check = check_for_updates(install_dir)
    if not check.get("ok"):
        print(json.dumps(check, ensure_ascii=False))
        return 1
    if not check.get("has_update"):
        print(json.dumps({"ok": True, "updated": False, **check}, ensure_ascii=False))
        return 0

    payload_url = join_update_url(base_url, str(manifest.get("payload_endpoint") or "app-base.zip"))
    with tempfile.TemporaryDirectory() as tempdir:
        payload_file = Path(tempdir) / "app-base.zip"
        with urllib.request.urlopen(payload_url, timeout=60) as response:
            payload_file.write_bytes(response.read())
        backup = create_update_backup(install_dir, str(check["remote_version"]))
        updater = install_dir / "Infinite Canvas Updater.exe"
        if not updater.exists():
            print(json.dumps({"ok": False, "detail": "缺少更新器可执行文件。"}, ensure_ascii=False))
            return 1
        result = subprocess.run(
            [
                str(updater),
                "--install-dir",
                str(install_dir),
                "--payload",
                str(payload_file),
                "--release-name",
                str(check["remote_version"]),
            ],
            check=False,
        )
        if result.returncode != 0:
            print(json.dumps({"ok": False, "detail": f"更新器退出码 {result.returncode}"}, ensure_ascii=False))
            return result.returncode
    print(json.dumps({"ok": True, "updated": True, "backup": backup, **check}, ensure_ascii=False))
    return 0


def list_backups(install_dir: Path) -> int:
    print(json.dumps({"ok": True, "backups": list_launcher_backups(install_dir)}, ensure_ascii=False))
    return 0


def rollback_backup(install_dir: Path, backup_id: str) -> int:
    if not backup_id:
        print(json.dumps({"ok": False, "detail": "缺少 backup_id。"}, ensure_ascii=False))
        return 1
    try:
        result = rollback_launcher_backup(install_dir, backup_id)
    except FileNotFoundError:
        print(json.dumps({"ok": False, "detail": "备份不存在。"}, ensure_ascii=False))
        return 1
    except ValueError as exc:
        print(json.dumps({"ok": False, "detail": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


def main() -> int:
    args = parse_args()
    if args.check_update:
        print(json.dumps(check_for_updates(args.install_dir.resolve()), ensure_ascii=False))
        return 0
    if args.apply_update:
        return apply_update(args.install_dir.resolve())
    if args.list_backups:
        return list_backups(args.install_dir.resolve())
    if args.rollback_backup:
        return rollback_backup(args.install_dir.resolve(), str(args.rollback_backup).strip())
    layout = resolve_runtime_context(args.install_dir.resolve())
    launcher_exe = str(args.install_dir.resolve() / "Infinite Canvas.exe")
    selected_port, port_changed = select_launch_port(layout)
    persist_selected_port(layout, selected_port)
    process = launch_server(layout, launcher_exe=launcher_exe, port=selected_port)
    ok = wait_for_server(selected_port)
    if ok and not args.no_browser:
        webbrowser.open(app_base_url(selected_port) + "/")
    if not ok:
        process.terminate()
        return 1
    if port_changed:
        print(
            json.dumps(
                {
                    "ok": True,
                    "detail": f"端口 {DEFAULT_APP_PORT} 不可用，已自动切换到 {selected_port}。",
                    "port": selected_port,
                },
                ensure_ascii=False,
            )
        )
    return process.wait()


if __name__ == "__main__":
    raise SystemExit(main())
