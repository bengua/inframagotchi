"""Probe factories. Every factory returns a zero-arg callable () -> float."""

from __future__ import annotations

import glob
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any


def _clamp(value: float) -> float:
    """Clamp a health value to [0, 1]."""
    return max(0.0, min(1.0, value))


def _unable() -> float:
    """Neutral/healthy result when a probe cannot run on this host."""
    return 1.0


def make_disk(params: dict[str, Any]) -> tuple[str, Any]:
    """Disk usage probe.

    1.0 = empty disk, 0.0 = full disk. Unavailable paths are treated as healthy
    so a portable config does not crash the app.
    """
    path = params.get("path", "/")

    def probe() -> float:
        try:
            usage = shutil.disk_usage(path)
        except OSError:
            return _unable()
        if not usage.total:
            return _unable()
        return _clamp(usage.free / usage.total)

    return "disk", probe


def make_service(params: dict[str, Any]) -> tuple[str, Any]:
    """systemd service active-state probe.

    Requires ``systemctl``. If it is missing, the probe fails soft and returns
    healthy. This keeps the app portable off Linux or inside minimal containers.
    """
    unit = params.get("unit", "sshd.service")

    def probe() -> float:
        try:
            result = subprocess.run(
                ["systemctl", "is-active", unit],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return _unable()
        active = result.stdout.strip().lower() == "active"
        return 1.0 if active else 0.0

    return f"service:{unit}", probe


def make_cert(params: dict[str, Any]) -> tuple[str, Any]:
    """TLS certificate expiry probe using openssl.

    Returns 1.0 when the certificate is far from expiry, 0.0 when it has
    expired or is missing. Falls back to healthy if openssl is not available.
    """
    path = params.get("path", "")
    warn_days = int(params.get("warn_days", 30))
    critical_days = int(params.get("critical_days", 7))

    def probe() -> float:
        if not path or not os.path.isfile(path):
            return 0.0
        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", path, "-noout", "-enddate"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            return _unable()
        if result.returncode != 0:
            return 0.0
        # notAfter=Nov  7 12:00:00 2024 GMT
        match = re.search(r"notAfter=(.+)", result.stdout)
        if not match:
            return 0.0
        expiry_text = match.group(1).strip()
        try:
            expiry = datetime.strptime(expiry_text, "%b %d %H:%M:%S %Y %Z")
        except ValueError:
            return 0.0
        expiry = expiry.replace(tzinfo=timezone.utc)
        remaining = (expiry - datetime.now(timezone.utc)).total_seconds() / 86400
        if remaining <= critical_days:
            return 0.0
        if remaining >= warn_days:
            return 1.0
        return _clamp((remaining - critical_days) / (warn_days - critical_days))

    return f"cert:{path}", probe


def make_backup(params: dict[str, Any]) -> tuple[str, Any]:
    """Backup freshness probe.

    Looks at the most recently modified file matching *pattern* and returns a
    linear score from 1.0 (just created) to 0.0 (older than *max_age_hours*).
    Returns 0.0 if no file matches.
    """
    pattern = params.get("pattern", "")
    max_age_hours = float(params.get("max_age_hours", 24))
    max_age_seconds = max_age_hours * 3600

    def probe() -> float:
        if not pattern:
            return 0.0
        try:
            files = glob.glob(pattern)
        except OSError:
            return _unable()
        if not files:
            return 0.0
        try:
            newest = max(os.path.getmtime(f) for f in files)
        except OSError:
            return _unable()
        age = max(0.0, datetime.now().timestamp() - newest)
        return _clamp(1.0 - age / max_age_seconds)

    return f"backup:{pattern}", probe


def make_ping(params: dict[str, Any]) -> tuple[str, Any]:
    """Host reachability probe using ping.

    Returns 1.0 if the host answers, 0.0 otherwise. Fails soft (healthy) if
    the ping binary is unavailable so non-Linux hosts do not crash.
    """
    host = params.get("host", "")
    count = int(params.get("count", 1))
    timeout = int(params.get("timeout", 5))

    def probe() -> float:
        if not host:
            return 0.0
        try:
            result = subprocess.run(
                ["ping", "-c", str(count), "-W", str(timeout), host],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout + 2,
            )
        except (OSError, subprocess.TimeoutExpired):
            return _unable()
        return 1.0 if result.returncode == 0 else 0.0

    return f"ping:{host}", probe


_PROBE_FACTORIES: dict[str, Any] = {
    "disk": make_disk,
    "service": make_service,
    "cert": make_cert,
    "backup": make_backup,
    "ping": make_ping,
}


def build_probe(spec: dict[str, Any]) -> tuple[str, Any]:
    """Build a named probe from a config table."""
    probe_type = spec.get("type")
    if not isinstance(probe_type, str):
        raise ValueError("Probe 'type' is required and must be a string")
    factory = _PROBE_FACTORIES.get(probe_type)
    if factory is None:
        raise ValueError(f"Unknown probe type: {probe_type}")
    return factory(spec)
