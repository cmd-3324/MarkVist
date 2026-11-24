"""Small JSON preferences file handling."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .theme import APP_NAME


def config_path() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / ".config")
    return Path(base) / APP_NAME / "config.json"


def read_config() -> dict:
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_config(data: dict) -> None:
    try:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass


# -- shadow copies of unsaved untitled notes -------------------------------- #


def shadows_path() -> Path:
    return config_path().parent / "shadows.json"


def read_shadows() -> list[dict]:
    """Unsaved untitled notes written by earlier runs."""
    try:
        data = json.loads(shadows_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    docs = data.get("docs") if isinstance(data, dict) else data
    if not isinstance(docs, list):
        return []
    return [d for d in docs if isinstance(d, dict) and isinstance(d.get("text"), str)]


def write_shadows(docs: list[dict]) -> None:
    path = shadows_path()
    try:
        if not docs:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"docs": docs}, indent=2), encoding="utf-8")
    except OSError:
        pass
