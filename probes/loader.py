"""Config discovery, validation, and probe instantiation."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from probes._config import load_config
from probes.base import ProbeFn, ProbeResult, safe_call
from probes.registry import get_factory

DEFAULT_INTERVAL = 5.0


@dataclass(frozen=True, slots=True)
class Probe:
    """A configured probe: a callable wrapped with its metadata."""

    name: str
    fn: ProbeFn
    interval: float

    def __call__(self) -> ProbeResult:
        return safe_call(self.fn)


def _as_float(value: Any, field: str) -> float:
    """Parse a config param as a positive float, with a clear error message."""
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Probe '{field}' must be a number, got {value!r}") from exc
    if result <= 0:
        raise ValueError(f"Probe '{field}' must be positive, got {result}")
    return result


def _validate_spec(spec: Any) -> dict[str, Any]:
    """Ensure a probe entry is a dict with a string ``type``."""
    if not isinstance(spec, dict):
        raise ValueError(f"Probe entry must be a table, got {type(spec).__name__}")
    probe_type = spec.get("type")
    if not isinstance(probe_type, str) or not probe_type:
        raise ValueError("Probe 'type' is required and must be a non-empty string")
    return spec


def load_probes(path: Path | None = None) -> list[Probe]:
    """Read config and instantiate all configured probes.

    Falls back to a single portable disk probe when no config exists or when the
    configured probe list is empty. Raises ``ValueError`` for invalid probe types
    or parameters so the error surfaces during load, not at call time.
    """
    config = load_config(path)
    loaded: list[Probe] = []
    for spec in config.get("probe", []):
        spec = _validate_spec(spec)
        factory = get_factory(spec["type"])
        name, fn = factory(spec)
        interval = _as_float(spec.get("interval", DEFAULT_INTERVAL), "interval")
        loaded.append(Probe(name, fn, interval))

    if not loaded:
        from probes.local import make_disk

        name, fn = make_disk({"path": "/"})
        loaded.append(Probe(name, fn, DEFAULT_INTERVAL))
    return loaded


def build_callables(
    probes: list[Probe],
) -> tuple[tuple[str, ...], tuple[Callable[[], ProbeResult], ...]]:
    """Split a list of probes into names and callable functions."""
    return tuple(p.name for p in probes), tuple(p.fn for p in probes)
