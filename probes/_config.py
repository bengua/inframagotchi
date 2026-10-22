"""Config discovery, parsing, and persistence for inframagotchi probes."""

from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "probe": [
        {"type": "disk", "path": "/", "interval": 5},
        {"type": "chain", "interval": 30},
    ],
}

CONFIG_FILENAMES = ("inframagotchi.json", "inframagotchi.toml")

_active_path: Path | None = None
_active_text: str = ""


def _config_dirs() -> list[Path]:
    """Return candidate config directories in precedence order."""
    dirs: list[Path] = []
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        dirs.append(Path(xdg_config))
    else:
        dirs.append(Path.home() / ".config")
    return dirs


def find_config() -> Path | None:
    """Locate the active config file, or None if none exists."""
    env_override = os.environ.get("INFRAMAGOTCHI_CONFIG")
    if env_override:
        return Path(env_override)

    candidates: list[Path] = [Path.cwd() / name for name in CONFIG_FILENAMES]
    for base in _config_dirs():
        for name in CONFIG_FILENAMES:
            candidates.append(base / "inframagotchi" / name)

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _record_active(target: Path | None, text: str = "") -> None:
    """Cache the path and raw text of the active config file."""
    global _active_path, _active_text
    _active_path = target
    _active_text = text


def _parse(text: str, suffix: str) -> dict[str, Any]:
    """Parse JSON or TOML depending on the file suffix."""
    if suffix == ".toml":
        return tomllib.loads(text)
    return json.loads(text)


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config from *path*, or discover it. Falls back to defaults.

    Supports ``.json`` (preferred) and ``.toml`` (legacy/read-only).
    Invalid config emits a warning and returns the default config.
    """
    target = path or find_config()
    if target is None:
        _record_active(None)
        return DEFAULT_CONFIG.copy()

    try:
        text = target.read_text(encoding="utf-8")
        data = _parse(text, target.suffix.lower())
    except (OSError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        import warnings

        warnings.warn(f"Invalid config in {target}: {exc}. Using default config.")
        _record_active(target, text if "text" in dir() else "")
        return DEFAULT_CONFIG.copy()

    probes = data.get("probe")
    if probes is None:
        _record_active(target, text)
        return DEFAULT_CONFIG.copy()
    if isinstance(probes, dict):
        probes = [probes]
    if not isinstance(probes, list):
        import warnings

        warnings.warn("Config 'probe' must be a table or array. Using default config.")
        _record_active(target, text)
        return DEFAULT_CONFIG.copy()

    _record_active(target, text)
    data["probe"] = probes
    return data


def active_config_path() -> Path | None:
    """Return the path of the most recently loaded config, if any."""
    return _active_path


def active_config_text() -> str:
    """Return the raw text of the most recently loaded config."""
    return _active_text


def save_config(text: str, path: Path | None = None) -> Path:
    """Validate and atomically write *text* to the given or default config file.

    Raises ``ValueError`` if the text is not valid JSON/TOML or contains a
    non-table/array ``probe`` key. The write is done via a temporary file and
    ``os.replace()``. When no path is given, the default is
    ``./inframagotchi.json``.
    """
    global _active_path, _active_text

    target = path if path is not None else Path.cwd() / "inframagotchi.json"

    try:
        data = _parse(text, target.suffix.lower())
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"Invalid config: {exc}") from exc

    probes = data.get("probe")
    if probes is not None and not isinstance(probes, (dict, list)):
        raise ValueError("Config 'probe' must be a table or array.")

    avatar = data.get("avatar")
    if avatar is not None and not isinstance(avatar, str):
        raise ValueError("Config 'avatar' must be a string.")

    tmp = target.with_suffix(".tmp")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, target)

    _active_path = target
    _active_text = text
    return target
