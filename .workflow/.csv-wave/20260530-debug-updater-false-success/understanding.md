# Updater False Success Debug Report

## Summary

- Symptom: `--apply-update` returned `ok: true, updated: true`, but installed `VERSION` remained `2026.05.29`.
- Root cause 1: launcher trusted the updater process exit code and never verified either the downloaded payload's internal `VERSION` or the installed version after updater completion.
- Root cause 2: Windows in-place updater replaced installed files but did not replace `bootstrap/app-base.zip`. It then wrote `.payload-ready` using the old bootstrap zip fingerprint, so the next launcher startup could extract the old bootstrap payload over the updated install.
- Confirmed hypotheses: H1, H3, and bootstrap payload stale-after-update.
- Refuted hypothesis: downloaded payload missing. The payload was present, but it was not promoted into `bootstrap/app-base.zip` for in-place installs.

## Evidence

- `packaging/windows/launcher/launcher_main.py` previously downloaded `windows-app-base.zip`, invoked the updater, cleared pending state, and returned success solely from `returncode == 0`.
- `packaging/macos/launcher/launcher_main.py` had the same control flow.
- Existing tests used raw `payload-bytes` and mocked updater success, so they could not catch payload version mismatch or no-op updater success.
- `packaging/windows/updater/updater_main.py` in-place branch previously called `replace_in_place_payload(target_dir, args.payload.resolve())`, then wrote `.payload-ready` from `payload_ready_marker(layout.install_dir)`. Because `bootstrap/app-base.zip` remained old, that marker represented the old payload.
- `packaging/windows/launcher/runtime_manager.py::copy_payload_for_in_place()` compares `.payload-ready` against `bootstrap/app-base.zip` and extracts that zip when installed files do not match. With a stale bootstrap zip, this restores the old version on the next launch.

## Fix

- Added `read_update_payload_version()` to Windows and macOS launchers.
- Reject update payloads whose embedded `VERSION` is empty/unreadable or lower than `remote_version`.
- After updater exit code 0, re-read `current_payload_version()` and fail if the installed version is still lower than `remote_version`.
- On verified success, return the post-update `current_version`, `has_update: false`, and `payload_version`.
- Fixed failure response dict ordering so `check["ok"] == true` cannot overwrite an intended `ok: false`.
- Windows in-place updater now copies the downloaded payload into `bootstrap/app-base.zip` before writing `.payload-ready`, so the ready marker and bootstrap payload both represent the updated version.
- Added a startup fallback in `copy_payload_for_in_place()`: when `bootstrap/app-base.zip` has a lower `VERSION` than the installed `VERSION`, launcher skips extraction instead of rolling the install back.
- Bootstrap payload refresh failure in the Windows in-place updater is non-blocking. The updater logs a warning to stderr and preserves the installed file update; the startup fallback prevents the stale bootstrap zip from being extracted later.

## Verification

- `python -m pytest tests/test_windows_launcher_update.py -q` passed.
- `python -m pytest tests/test_macos_launcher_update.py -q` passed.
- `python -m pytest tests/test_runtime_manager.py tests/test_macos_runtime_manager.py tests/test_publish_release.py tests/test_macos_publish_release.py tests/test_release_workflow.py -q` passed.
- `python -m pytest tests/test_launcher_updater_fingerprint.py -q` passed.
- `python -m pytest tests/test_windows_launcher_update.py tests/test_macos_launcher_update.py tests/test_runtime_manager.py -q` passed.
- `python -m pytest tests/test_macos_runtime_manager.py tests/test_publish_release.py tests/test_macos_publish_release.py tests/test_release_workflow.py -q` passed.
- `python -m pytest tests/test_runtime_manager.py tests/test_launcher_updater_fingerprint.py -q` passed.
- `python -m pytest tests/test_launcher_updater_fingerprint.py tests/test_windows_launcher_update.py tests/test_macos_launcher_update.py tests/test_runtime_manager.py tests/test_macos_runtime_manager.py tests/test_publish_release.py tests/test_macos_publish_release.py tests/test_release_workflow.py -q` passed.

## Confidence

- Evidence depth: high.
- Evidence strength: high.
- Coverage breadth: high for launcher update paths.
- Reproduction: confirmed against the observed installed state and covered by regression tests.
- Fix confidence: high.
