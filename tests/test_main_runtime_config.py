import ast
from pathlib import Path


def test_main_defines_packaged_runtime_config_before_server_start():
    tree = ast.parse(Path("main.py").read_text(encoding="utf-8"))
    assigned_names = set()
    imported_from_app_runtime = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    assigned_names.add(target.id)
        if isinstance(node, ast.ImportFrom) and node.module == "app_runtime":
            imported_from_app_runtime.update(alias.name for alias in node.names)

    assert {"APP_DATA_ROOT", "LAUNCHER_MANAGED", "APP_PORT", "APP_HOST", "RUNTIME_PATHS"} <= assigned_names
    assert {"DEFAULT_APP_HOST", "DEFAULT_APP_PORT", "resolve_app_port", "resolve_runtime_paths"} <= imported_from_app_runtime
