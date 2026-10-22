"""Base probe contract and scoring helpers used across the probes package."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeAlias

ProbeResult: TypeAlias = float | None
ProbeFn: TypeAlias = Callable[[], ProbeResult]


def clamp(value: float) -> float:
    """Clamp a value to the probe range [0, 1]."""
    return max(0.0, min(1.0, value))


def linear_score(value: float, good: float, bad: float) -> float:
    """Map ``value`` to ``[0, 1]`` with ``1.0`` at ``good`` and ``0.0`` at ``bad``.

    Works in either direction:
    - ``good < bad`` means higher values are worse (load, latency, used fraction).
    - ``good > bad`` means higher values are better (free fraction).

    Values beyond ``good``/``bad`` are clamped. If ``good == bad`` the score is
    1.0 exactly at that point and 0.0 everywhere else.
    """
    if good == bad:
        return 1.0 if value == good else 0.0
    if good < bad:
        if value <= good:
            return 1.0
        if value >= bad:
            return 0.0
        return 1.0 - (value - good) / (bad - good)
    # good > bad: higher is better
    if value >= good:
        return 1.0
    if value <= bad:
        return 0.0
    return (value - bad) / (good - bad)


def safe_call(probe: ProbeFn) -> ProbeResult:
    """Run a probe and enforce the result contract.

    - ``None`` is passed through unchanged (probe could not run).
    - A float is clamped to ``[0, 1]``.
    - Any exception is turned into ``None`` so a failing probe cannot crash the app.
    """
    try:
        result = probe()
    except Exception:
        return None
    if result is None:
        return None
    return clamp(result)
