"""Probe that scores the most recent job-runner records (JSON files) from disk."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from probes.base import ProbeFn, ProbeResult

_BAD_STATES = {"failed", "needs_human"}
_LIMIT = 8
DEFAULT_DIR = "runs/records"


def make_chain(params: dict[str, Any]) -> tuple[str, ProbeFn]:
    """Job-runner health probe.

    Reads the record directory given by ``params["dir"]`` (default
    ``runs/records``, relative to the working directory), takes the up to eight most recent ``.json``
    files, and returns the fraction of them whose ``state`` field is neither
    ``failed`` nor ``needs_human``. Returns ``None`` if the directory does not
    exist or holds no record files. No exception ever propagates.
    """
    directory = params.get("dir", DEFAULT_DIR)

    def probe() -> ProbeResult:
        try:
            root = Path(directory)
            if not root.is_dir():
                return None
            files = [p for p in root.glob("*.json") if p.is_file()]
            files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            recent = files[:_LIMIT]
            if not recent:
                return None
            good = 0
            for path in recent:
                with open(path) as fh:
                    record = json.load(fh)
                if record.get("state") not in _BAD_STATES:
                    good += 1
            return good / len(recent)
        except Exception:
            return None

    return f"chain:{directory}", probe
