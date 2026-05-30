# Desktop Version Badge Shows v-

## Symptom

Desktop frontend version badge stays at `v-` instead of showing the concrete app version.

## Root Cause

`static/index.html` calls `checkForUpdates()` on `DOMContentLoaded`. The function reads `updateCheckInFlight` before any declaration existed, causing a browser `ReferenceError` at function entry. Because the exception happens before `/api/app-info` is fetched, `appInfo.version` remains the initial empty string and `versionLabel('')` renders `v-`.

Evidence:
- `static/index.html`: `appInfo` default is `version:''`.
- `static/index.html`: `versionLabel('')` returns `v-`.
- `static/index.html`: `checkForUpdates()` referenced missing `updateCheckInFlight`, and launcher recheck helpers also referenced missing launcher recheck state.

## Fix

Defined the update-check state variables before any update functions run:
- `updateCheckInFlight`
- `launcherUpdateRecheckTimer`
- `launcherUpdateRecheckCount`
- `LAUNCHER_UPDATE_RECHECK_LIMIT`
- `LAUNCHER_UPDATE_RECHECK_INTERVAL_MS`

## Verification

Pending pytest run: `python -m pytest tests/test_update_check_state.py tests/test_launcher_update_modal.py tests/test_launcher_env.py`.
