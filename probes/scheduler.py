"""Background scheduler that runs every probe at its own cadence."""

from __future__ import annotations

import time
from threading import Event, Thread
from typing import TYPE_CHECKING

from probes.base import safe_call

if TYPE_CHECKING:
    from probes.loader import Probe
    from probes.state import HealthState


class ProbeScheduler:
    """Run each probe in its own daemon thread on a configurable interval.

    The scheduler never blocks callers: it writes results into a ``HealthState``
    cache and the render/HTTP layer reads from that cache. Probes run once
    immediately at startup so valid data is available as soon as possible.
    """

    def __init__(self, state: "HealthState", probes: list["Probe"]) -> None:
        self._state = state
        self._probes = list(probes)
        self._stop = Event()
        self._threads: list[Thread] = []

    def start(self) -> None:
        """Start one daemon thread per probe."""
        self._stop.clear()
        self._threads = []
        for probe in self._probes:
            thread = Thread(target=self._loop, args=(probe,), daemon=True)
            thread.start()
            self._threads.append(thread)

    def _loop(self, probe: "Probe") -> None:
        """Run *probe* immediately, then wait for its interval or stop."""
        self._state.set(probe.name, safe_call(probe))
        while not self._stop.wait(probe.interval):
            self._state.set(probe.name, safe_call(probe))

    def stop(self, timeout: float = 5.0) -> None:
        """Signal all worker threads to stop and wait briefly for them."""
        self._stop.set()
        deadline = time.monotonic() + timeout
        for thread in self._threads:
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(timeout=remaining)
