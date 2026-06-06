# Runtime Paths KeyError Diagnosis

## Summary
The container failed at import time because main.py accessed RUNTIME_PATHS["SHARED_FOLDERS_FILE"], but pp_runtime.resolve_runtime_paths() did not provide that key.

## Root Cause
The pkg merge moved runtime path constants behind pp_runtime.py, but SHARED_FOLDERS_FILE from upstream main.py was not added to the provider module. Existing tests only checked that runtime config variables were assigned; they did not compare every consumer key against provider keys.

## Fix
- Added SHARED_FOLDERS_FILE to esolve_runtime_paths() under the writable data root.
- Reorganized esolve_runtime_paths() to explicitly define all runtime path keys used by main.py.
- Added a regression test that AST-scans main.py for every RUNTIME_PATHS[...] key and asserts each key is provided by pp_runtime.resolve_runtime_paths().

## Verification
- python -m py_compile main.py app_runtime.py
- Runtime key consistency check: 18 used keys, 0 missing
- Runtime/packaging tests: 32 passed
