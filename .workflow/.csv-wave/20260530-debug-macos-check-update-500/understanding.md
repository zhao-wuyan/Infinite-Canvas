# macOS check-update 500 diagnosis

## Symptom

The running backend logs:

```text
INFO:     127.0.0.1:63031 - "GET /api/launcher/check-update HTTP/1.1" 500 Internal Server Error
```

Local reproduction:

```text
GET http://127.0.0.1:3000/api/launcher/check-update
HTTP/1.1 500 Internal Server Error
{"detail":"launcher command failed"}
```

## Root Cause

The actual local failure is in the packaged macOS launcher, not in FastAPI itself.

Directly running the launcher command used by the API:

```text
/Applications/Infinite Canvas.app/Contents/MacOS/Infinite Canvas --check-update
```

failed with:

```text
ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate
urllib.error.URLError: <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] ...>
[PYI-34887:ERROR] Failed to execute script 'launcher_main' due to unhandled exception!
```

Code path:

- `static/index.html` calls `/api/launcher/check-update` during page update checks when `appInfo.managed_by_launcher` is true.
- `main.py:1708-1712` handles the route by calling `call_launcher_command("--check-update")`.
- `main.py:1553-1575` launches the macOS launcher subprocess and maps any non-zero exit code to HTTP 500.
- `packaging/macos/launcher/launcher_main.py:151-161` uses `urllib.request.urlopen`; it only treats HTTP 404 as a skip and re-raises other network/HTTP errors.
- `packaging/macos/launcher/launcher_main.py:189-196` calls that fetch path without a top-level management-action catch.
- `packaging/macos/launcher/launcher_main.py:410-412` returns 0 only if `check_for_updates_and_remember()` completes successfully.

The host machine can fetch the same release assets with `curl` and received HTTP 200 for `macos-VERSION`, `macos-manifest.json`, and `macos-app-base.zip`. That points to the PyInstaller-packaged launcher SSL trust store, not missing GitHub release assets.

## Secondary 500 Paths

These are real code paths but not the observed local root cause:

- If `INFINITE_CANVAS_LAUNCHER_EXE` is empty or invalid, `main.py:1550-1556` returns HTTP 500 with detail `launcher executable missing`.
- If the macOS bundle has a missing/corrupt `bootstrap/manifest.json` or `bootstrap/app-base.zip`, runtime setup can throw before network probing and be mapped to HTTP 500.

## Confidence

High. The failure was reproduced locally against the running backend and then isolated by executing the exact packaged launcher command, which produced the SSL traceback.
