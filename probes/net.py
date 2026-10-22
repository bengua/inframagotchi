"""Network probes: HTTP endpoint health and remote SSH command checks."""

from __future__ import annotations

import re
import subprocess
import time
import urllib.request
from typing import Any

from probes.base import ProbeFn, ProbeResult, linear_score


def make_http(params: dict[str, Any]) -> tuple[str, ProbeFn]:
    """HTTP endpoint health probe (stdlib only).

    Returns ``0.0`` for connection errors, timeouts, or non-success status codes
    — those mean the endpoint is actually down. Latency is scored between
    ``warn_ms`` and ``critical_ms``.
    """
    url = params.get("url", "")
    warn_ms = float(params.get("warn_ms", 500))
    critical_ms = float(params.get("critical_ms", 2000))
    timeout = float(params.get("timeout", 5))
    codes = params.get("success_codes")

    def probe() -> ProbeResult:
        if not url:
            return 0.0
        start = time.perf_counter()
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                elapsed_ms = (time.perf_counter() - start) * 1000
                status = getattr(resp, "status", None) or getattr(resp, "code", 0)
        except Exception:
            return 0.0
        allowed: set[int] | None = None
        if isinstance(codes, list) and codes:
            allowed = {int(c) for c in codes}
        if allowed is not None and int(status) not in allowed:
            return 0.0
        if allowed is None and not (200 <= int(status) < 300):
            return 0.0
        return linear_score(elapsed_ms, warn_ms, critical_ms)

    return f"http:{url}", probe


def make_ssh(params: dict[str, Any]) -> tuple[str, ProbeFn]:
    """Remote command probe over SSH.

    Uses the local ``ssh`` binary with key-based auth (``BatchMode=yes``).
    Auth failures, missing ``ssh``, connection problems, or timeouts return
    ``None`` — these are transport issues, not infra failures. A non-zero exit
    code or a missing ``expected`` regex match returns ``0.0``.
    """
    host = params.get("host", "")
    user = params.get("user", "")
    command = params.get("command", "")
    timeout = int(params.get("timeout", 10))
    expected = params.get("expected")
    if not host or not command:
        raise ValueError("SSH probe requires 'host' and 'command'")

    target = f"{user}@{host}" if user else host
    name = f"ssh:{host}:{command}"

    def probe() -> ProbeResult:
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    f"ConnectTimeout={min(timeout, 5)}",
                    target,
                    command,
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return 0.0
        if isinstance(expected, str) and expected:
            if re.search(expected, result.stdout) is None:
                return 0.0
        return 1.0

    return name, probe
