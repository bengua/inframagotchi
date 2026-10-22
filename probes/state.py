"""Thread-safe cache for the latest probe values and aggregate health."""

from __future__ import annotations

import time
from threading import Lock
from typing import Any


class HealthState:
    """Holds the most recent value of every probe.

    The scheduler writes into this cache from worker threads while the HTTP
    engine (or pump) reads ``aggregate()`` from the main thread. All access is
    guarded by a single lock so readers never block on slow probes.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        # name -> (value|None, monotonic_timestamp)
        self._values: dict[str, tuple[float | None, float]] = {}

    def set(self, name: str, value: float | None) -> None:
        """Store the latest result for *name* together with a timestamp."""
        with self._lock:
            self._values[name] = (value, time.monotonic())

    def clear(self) -> None:
        """Drop all cached values. Used during a live config reload."""
        with self._lock:
            self._values.clear()

    def snapshot(self) -> dict[str, dict[str, Any]]:
        """Return a copy of every probe's latest value and timestamp."""
        with self._lock:
            return {
                name: {"value": value, "last_updated": ts}
                for name, (value, ts) in self._values.items()
            }

    def aggregate(self) -> int:
        """Return the weakest-link health score as 0..100.

        Probes that returned ``None`` (could not run) are ignored. If every
        probe is ``None`` the result is ``100`` (neutral).
        """
        with self._lock:
            values = [v for (v, _) in self._values.values() if v is not None]
        if not values:
            return 100
        worst = max(0.0, min(1.0, min(values)))
        return round(worst * 100)
