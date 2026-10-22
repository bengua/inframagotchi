"""Fast, local system probes that don't leave the host."""

from __future__ import annotations

import os
import shutil
from typing import Any

from probes.base import ProbeFn, ProbeResult, linear_score


def make_disk(params: dict[str, Any]) -> tuple[str, ProbeFn]:
    """Disk usage probe.

    Without ``warn``/``critical`` the score is ``free / total`` for backward
    compatibility. With thresholds (used fractions, e.g. 0.80 / 0.95) the score
    is 1.0 below ``warn``, 0.0 above ``critical``, and linear in between.
    Unavailable paths return ``None`` so a portable config does not crash.
    """
    path = params.get("path", "/")
    warn = params.get("warn")
    critical = params.get("critical")

    def probe() -> ProbeResult:
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            return None
        if not usage.total:
            return None
        used = 1.0 - (usage.free / usage.total)
        if warn is None or critical is None:
            return usage.free / usage.total
        return linear_score(used, float(warn), float(critical))

    return f"disk:{path}", probe


def make_load(params: dict[str, Any]) -> tuple[str, ProbeFn]:
    """System load-average probe (Unix only).

    Uses the 1-minute load average. ``warn`` defaults to the CPU count and
    ``critical`` defaults to twice the CPU count when omitted or zero. Fails soft
    on non-Unix hosts or missing ``os.getloadavg``.
    """
    warn = float(params.get("warn", 0.0))
    critical = float(params.get("critical", 0.0))

    def probe() -> ProbeResult:
        try:
            load1, _, _ = os.getloadavg()
        except (OSError, AttributeError):
            return None
        cores = os.cpu_count() or 1
        local_warn = warn if warn > 0 else cores
        local_critical = critical if critical > 0 else cores * 2
        if local_critical <= local_warn:
            local_critical = local_warn * 2
        return linear_score(load1, local_warn, local_critical)

    return "load", probe


def make_ram(params: dict[str, Any]) -> tuple[str, ProbeFn]:
    """RAM usage probe (Linux only).

    Reads ``/proc/meminfo`` and computes the used fraction as
    ``1 - MemAvailable / MemTotal``. ``warn`` and ``critical`` are used fractions
    (e.g. 0.75 / 0.90). Returns ``None`` on non-Linux hosts.
    """
    warn = float(params.get("warn", 0.0))
    critical = float(params.get("critical", 0.0))

    def probe() -> ProbeResult:
        try:
            with open("/proc/meminfo") as fh:
                meminfo = fh.read()
        except OSError:
            return None
        total_kib: int | None = None
        available_kib: int | None = None
        for line in meminfo.splitlines():
            if line.startswith("MemTotal:"):
                total_kib = int(line.split()[1])
            elif line.startswith("MemAvailable:"):
                available_kib = int(line.split()[1])
        if total_kib is None or available_kib is None or total_kib == 0:
            return None
        used = 1.0 - (available_kib / total_kib)
        if warn <= 0 or critical <= 0:
            return 1.0 - used
        return linear_score(used, warn, critical)

    return "ram", probe
