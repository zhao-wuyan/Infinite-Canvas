from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

from app_runtime import DEFAULT_APP_PORT, app_base_url
from packaging.macos.launcher.layout import app_bundle_from_executable
from packaging.macos.launcher.runtime_manager import (
    compare_versions,
    create_update_backup,
    current_payload_version,
    launch_server,
    list_launcher_backups,
    load_launcher_state,
    persist_selected_port,
    read_manifest,
    resolve_runtime_context,
    rollback_launcher_backup,
    save_launcher_state,
    select_launch_port,
    wait_for_server,
)


AUTO_UPDATE_ENV = "INFINITE_CANVAS_AUTO_UPDATE"
UPDATE_ASSET_PREFIX = "macos"
PENDING_UPDATE_KEY = "pending_update"


def default_app_bundle() -> Path:
    return app_bundle_from_executable(Path(sys.executable))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Infinite Canvas macOS launcher")
    parser.add_argument("--app-bundle", type=Path, default=default_app_bundle())
    parser.add_argument("--storage-root", type=Path, default=None)
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


def update_endpoint_candidates(endpoint: str) -> list[str]:
    endpoint = str(endpoint or "").strip()
    if not endpoint:
        return []
    candidates = [endpoint]
    if "/" not in endpoint and not endpoint.startswith(f"{UPDATE_ASSET_PREFIX}-"):
        candidates.append(f"{UPDATE_ASSET_PREFIX}-{endpoint}")
    return candidates


def fetch_remote_version(base_url: str, endpoint: str) -> str | None:
    text = None
    for candidate in update_endpoint_candidates(endpoint):
        try:
            text = fetch_text(join_update_url(base_url, candidate))
            break
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
    if text is None:
        return None
    lines = text.strip().splitlines()
    return lines[0].strip() if lines else ""


def download_update_payload(base_url: str, endpoint: str, output_path: Path) -> str | None:
    for candidate in update_endpoint_candidates(endpoint):
        payload_url = join_update_url(base_url, candidate)
        try:
            with urllib.request.urlopen(payload_url, timeout=60) as response:
                output_path.write_bytes(response.read())
            return payload_url
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            raise
    return None


def check_for_updates(app_bundle: Path, storage_root: Path | None = None) -> dict[str, str | bool]:
    layout = resolve_runtime_context(app_bundle, storage_root=storage_root)
    manifest = read_manifest(layout)
    base_url = str(manifest.get("update_base_url") or "").strip()
    if not base_url:
        return {"ok": False, "detail": "未配置 update_base_url。"}
    current = current_payload_version(app_bundle, storage_root=layout.storage_root)
    remote = fetch_remote_version(base_url, str(manifest.get("version_endpoint") or "VERSION"))
    if remote is None:
        return {
            "ok": True,
            "current_version": current,
            "has_update": False,
            "skipped": True,
            "detail": "远端 VERSION 不存在，跳过自动更新。",
        }
    if not remote:
        return {"ok": False, "current_version": current, "detail": "远端 VERSION 为空。"}
    return {
        "ok": True,
        "current_version": current,
        "remote_version": remote,
        "has_update": compare_versions(remote, current) > 0,
    }


def pending_update_from_state(app_bundle: Path, storage_root: Path | None = None) -> dict[str, object] | None:
    layout = resolve_runtime_context(app_bundle, storage_root=storage_root)
    state = load_launcher_state(layout)
    pending = state.get(PENDING_UPDATE_KEY)
    if not isinstance(pending, dict):
        return None
    remote = str(pending.get("remote_version") or "").strip()
    current = current_payload_version(app_bundle, storage_root=layout.storage_root)
    if remote and compare_versions(remote, current) > 0:
        return {
            "ok": True,
            "current_version": current,
            "remote_version": remote,
            "has_update": True,
            "pending_update": True,
        }
    if pending:
        state.pop(PENDING_UPDATE_KEY, None)
        save_launcher_state(layout, state)
    return None


def remember_update_check(app_bundle: Path, check: dict[str, Any], storage_root: Path | None = None) -> dict[str, Any]:
    if not check.get("ok"):
        return check
    layout = resolve_runtime_context(app_bundle, storage_root=storage_root)
    state = load_launcher_state(layout)
    if check.get("has_update"):
        state[PENDING_UPDATE_KEY] = {
            "current_version": str(check.get("current_version") or "").strip(),
            "remote_version": str(check.get("remote_version") or "").strip(),
            "detected_at": int(time.time()),
        }
        save_launcher_state(layout, state)
        return {**check, "pending_update": True}
    state.pop(PENDING_UPDATE_KEY, None)
    save_launcher_state(layout, state)
    return {**check, "pending_update": False}


def clear_pending_update(app_bundle: Path, storage_root: Path | None = None) -> None:
    layout = resolve_runtime_context(app_bundle, storage_root=storage_root)
    state = load_launcher_state(layout)
    if PENDING_UPDATE_KEY in state:
        state.pop(PENDING_UPDATE_KEY, None)
        save_launcher_state(layout, state)


def check_for_updates_and_remember(app_bundle: Path, storage_root: Path | None = None) -> dict[str, Any]:
    pending = pending_update_from_state(app_bundle, storage_root=storage_root)
    if pending:
        return pending
    return remember_update_check(app_bundle, dict(check_for_updates(app_bundle, storage_root=storage_root)), storage_root=storage_root)


def apply_update_result(app_bundle: Path, storage_root: Path | None = None) -> dict[str, object]:
    layout = resolve_runtime_context(app_bundle, storage_root=storage_root)
    manifest = read_manifest(layout)
    base_url = str(manifest.get("update_base_url") or "").strip()
    if not base_url:
        return {"ok": False, "detail": "未配置 update_base_url。"}
    check = check_for_updates(app_bundle, storage_root=layout.storage_root)
    if not check.get("ok"):
        return dict(check)
    if not check.get("has_update"):
        clear_pending_update(app_bundle, storage_root=layout.storage_root)
        return {"ok": True, "updated": False, **check}

    updater = layout.contents_dir / "MacOS" / "Infinite Canvas Updater"
    if not updater.exists():
        return {"ok": False, "detail": "缺少更新器可执行文件。", **check}

    with tempfile.TemporaryDirectory() as tempdir:
        payload_file = Path(tempdir) / "app-base.zip"
        payload_url = download_update_payload(base_url, str(manifest.get("payload_endpoint") or "app-base.zip"), payload_file)
        if not payload_url:
            return {"ok": False, "detail": "远端 payload 不存在。", **check}
        backup = create_update_backup(app_bundle, str(check["remote_version"]), storage_root=layout.storage_root)
        result = subprocess.run(
            [
                str(updater),
                "--app-bundle",
                str(app_bundle),
                "--storage-root",
                str(layout.storage_root),
                "--payload",
                str(payload_file),
                "--release-name",
                str(check["remote_version"]),
            ],
            check=False,
        )
        if result.returncode != 0:
            return {"ok": False, "detail": f"更新器退出码 {result.returncode}", "returncode": result.returncode, **check}
    clear_pending_update(app_bundle, storage_root=layout.storage_root)
    return {"ok": True, "updated": True, "backup": backup, **check}


def apply_update(app_bundle: Path, storage_root: Path | None = None) -> int:
    result = apply_update_result(app_bundle, storage_root=storage_root)
    print(json.dumps(result, ensure_ascii=False))
    if result.get("ok"):
        return 0
    return int(result.get("returncode") or 1)


def auto_update_enabled() -> bool:
    value = str(os.environ.get(AUTO_UPDATE_ENV, "1")).strip().lower()
    return value not in {"0", "false", "no", "off"}


def try_auto_update_before_launch(app_bundle: Path, storage_root: Path | None = None) -> dict[str, object]:
    if not auto_update_enabled():
        return {"ok": True, "updated": False, "skipped": True, "detail": "auto update disabled"}
    pending = pending_update_from_state(app_bundle, storage_root=storage_root)
    if not pending:
        return {"ok": True, "updated": False, "skipped": True, "detail": "no pending update"}
    try:
        return apply_update_result(app_bundle, storage_root=storage_root)
    except Exception as exc:
        return {"ok": False, "updated": False, "detail": f"自动更新检查失败：{exc}"}


def check_for_updates_in_background(app_bundle: Path, storage_root: Path | None = None) -> None:
    if not auto_update_enabled():
        return

    def worker() -> None:
        try:
            result = check_for_updates_and_remember(app_bundle, storage_root=storage_root)
        except Exception as exc:
            print(json.dumps({"auto_update": {"ok": False, "updated": False, "detail": f"异步更新检查失败：{exc}"}}, ensure_ascii=False), flush=True)
            return
        if result.get("has_update"):
            print(json.dumps({"auto_update": result}, ensure_ascii=False), flush=True)

    threading.Thread(target=worker, name="infinite-canvas-update-check", daemon=True).start()


def list_backups(app_bundle: Path, storage_root: Path | None = None) -> int:
    backups = list_launcher_backups(app_bundle, storage_root=storage_root)
    print(json.dumps({"ok": True, "backups": backups}, ensure_ascii=False))
    return 0


def rollback_backup(app_bundle: Path, backup_id: str, storage_root: Path | None = None) -> int:
    if not backup_id:
        print(json.dumps({"ok": False, "detail": "缺少 backup_id。"}, ensure_ascii=False))
        return 1
    try:
        result = rollback_launcher_backup(app_bundle, backup_id, storage_root=storage_root)
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
    app_bundle = args.app_bundle.resolve()
    storage_root = args.storage_root.resolve() if args.storage_root else None
    if args.check_update:
        print(json.dumps(check_for_updates_and_remember(app_bundle, storage_root=storage_root), ensure_ascii=False))
        return 0
    if args.apply_update:
        return apply_update(app_bundle, storage_root=storage_root)
    if args.list_backups:
        return list_backups(app_bundle, storage_root=storage_root)
    if args.rollback_backup:
        return rollback_backup(app_bundle, str(args.rollback_backup).strip(), storage_root=storage_root)

    update_result = try_auto_update_before_launch(app_bundle, storage_root=storage_root)
    if update_result.get("updated") or not update_result.get("ok", True):
        print(json.dumps({"auto_update": update_result}, ensure_ascii=False))
    layout = resolve_runtime_context(app_bundle, storage_root=storage_root)
    launcher_exe = str(layout.contents_dir / "MacOS" / "Infinite Canvas")
    selected_port, port_changed = select_launch_port(layout)
    persist_selected_port(layout, selected_port)
    process = launch_server(layout, launcher_exe=launcher_exe, port=selected_port)
    check_for_updates_in_background(app_bundle, storage_root=storage_root)
    ok = wait_for_server(selected_port)
    if ok and not args.no_browser:
        webbrowser.open(app_base_url(selected_port) + "/")
    if not ok:
        process.terminate()
        return 1

    shutdown_requested = {"value": False}

    def handle_shutdown(_signum: int, _frame: object) -> None:
        shutdown_requested["value"] = True
        if process.poll() is None:
            process.terminate()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
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
    exit_code = process.wait()
    if shutdown_requested["value"]:
        return 0
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
