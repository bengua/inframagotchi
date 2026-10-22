"""Registry mapping probe type names to factory functions."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeAlias

from probes import _probes, chain, local, net
from probes.base import ProbeFn

ProbeFactory: TypeAlias = Callable[[dict[str, Any]], tuple[str, ProbeFn]]

_REGISTRY: dict[str, ProbeFactory] = {
    "disk": local.make_disk,
    "service": _probes.make_service,
    "cert": _probes.make_cert,
    "backup": _probes.make_backup,
    "ping": _probes.make_ping,
    "load": local.make_load,
    "ram": local.make_ram,
    "chain": chain.make_chain,
    "http": net.make_http,
    "ssh": net.make_ssh,
}


def register(name: str, factory: ProbeFactory) -> None:
    """Register a new probe factory under ``name``."""
    if not isinstance(name, str) or not name:
        raise ValueError("Probe type name must be a non-empty string")
    _REGISTRY[name] = factory


def get_factory(name: str) -> ProbeFactory:
    """Return the factory for ``name`` or raise a clear ValueError."""
    factory = _REGISTRY.get(name)
    if factory is None:
        raise ValueError(f"Unknown probe type: {name}")
    return factory


def known_types() -> tuple[str, ...]:
    """Return all currently registered probe type names."""
    return tuple(_REGISTRY.keys())
