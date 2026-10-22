"""Infrastructure probes for inframagotchi.

Each probe follows the contract defined in ``probes.base``: a zero-argument
callable returning either a float in [0, 1] (1 = healthy) or ``None`` (could
not measure). The renderer only ever sees the integer 0..100 returned by
``health()``.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from probes.base import safe_call
from probes.loader import load_probes

if TYPE_CHECKING:
    from probes.loader import Probe

NAMES: tuple[str, ...] = ()
_PROBES: tuple["Probe", ...] = ()


def _reload(path: Path | None = None) -> None:
    """Reload the probe list from *path* or the discovered config file."""
    global NAMES, _PROBES
    probes = load_probes(path)
    NAMES = tuple(p.name for p in probes)
    _PROBES = tuple(probes)


def health() -> int:
    """Aggregate all runnable probes into a 0..100 score — weakest link wins."""
    if not _PROBES:
        return 100
    results = [safe_call(p) for p in _PROBES]
    values = [v for v in results if v is not None]
    if not values:
        return 100
    worst = max(0.0, min(1.0, min(values)))
    return round(worst * 100)


_reload()


__all__ = ["health", "NAMES"]
