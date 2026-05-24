from __future__ import annotations

import os
from typing import Dict, Optional


DEFAULT_APP_HOST = "0.0.0.0"
DEFAULT_APP_PORT = 3000


def resolve_runtime_paths(base_dir: str, data_root: Optional[str] = None) -> Dict[str, str]:
    app_dir = os.path.abspath(base_dir)
    writable_root = os.path.abspath(data_root) if data_root else app_dir

    paths = {
        "APP_DIR": app_dir,
        "APP_DATA_ROOT": writable_root,
        "WORKFLOW_DIR": os.path.join(app_dir, "workflows"),
        "WORKFLOW_PATH": os.path.join(app_dir, "workflows", "Z-Image.json"),
        "STATIC_DIR": os.path.join(app_dir, "static"),
        "OUTPUT_DIR": os.path.join(writable_root, "output"),
        "ASSETS_DIR": os.path.join(writable_root, "assets"),
        "HISTORY_FILE": os.path.join(writable_root, "history.json"),
        "API_ENV_FILE": os.path.join(writable_root, "API", ".env"),
        "DATA_DIR": os.path.join(writable_root, "data"),
        "GLOBAL_CONFIG_FILE": os.path.join(writable_root, "global_config.json"),
    }
    paths["OUTPUT_INPUT_DIR"] = os.path.join(paths["ASSETS_DIR"], "input")
    paths["OUTPUT_OUTPUT_DIR"] = os.path.join(paths["ASSETS_DIR"], "output")
    paths["ASSET_LIBRARY_DIR"] = os.path.join(paths["ASSETS_DIR"], "library")
    paths["CONVERSATION_DIR"] = os.path.join(paths["DATA_DIR"], "conversations")
    paths["CANVAS_DIR"] = os.path.join(paths["DATA_DIR"], "canvases")
    paths["ASSET_LIBRARY_PATH"] = os.path.join(paths["DATA_DIR"], "asset_library.json")
    paths["API_PROVIDERS_FILE"] = os.path.join(paths["DATA_DIR"], "api_providers.json")
    return paths


def resolve_app_port(port_value: Optional[str | int], default_port: int = DEFAULT_APP_PORT) -> int:
    try:
        port = int(str(port_value).strip())
    except (TypeError, ValueError):
        return default_port
    if 1 <= port <= 65535:
        return port
    return default_port


def app_base_url(port: int, host: str = "127.0.0.1") -> str:
    resolved = resolve_app_port(port)
    return f"http://{host}:{resolved}"
