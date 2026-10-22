"""Tests for probe config loading and validation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest import TestCase

from probes.loader import Probe, load_probes
from probes.registry import get_factory, known_types, register


class LoaderTests(TestCase):
    def test_default_disk_probe_when_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            probes = load_probes()
        self.assertEqual(len(probes), 2)
        self.assertEqual(probes[0].name, "disk:/")
        self.assertEqual(probes[0].interval, 5.0)

    def test_default_chain_probe_when_no_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.chdir(tmp)
            probes = load_probes()
        self.assertIn("chain", {p.name.split(":")[0] for p in probes})
        chain_probe = next(p for p in probes if p.name.startswith("chain:"))
        self.assertEqual(chain_probe.interval, 30.0)

    def test_load_declared_chain_type(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write('[[probe]]\ntype = "chain"\ninterval = 30\n')
            path = Path(fh.name)
        try:
            probes = load_probes(path)
            self.assertEqual(len(probes), 1)
            self.assertEqual(probes[0].name, "chain:runs/records")
            self.assertEqual(probes[0].interval, 30.0)
            self.assertIsInstance(probes[0], Probe)
        finally:
            path.unlink()

    def test_load_from_toml(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write('[[probe]]\ntype = "disk"\npath = "/tmp"\ninterval = 10.5\n')
            path = Path(fh.name)
        try:
            probes = load_probes(path)
            self.assertEqual(len(probes), 1)
            self.assertEqual(probes[0].name, "disk:/tmp")
            self.assertEqual(probes[0].interval, 10.5)
            self.assertIsInstance(probes[0], Probe)
        finally:
            path.unlink()

    def test_unknown_type_raises_at_load_time(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write('[[probe]]\ntype = "unknown"\n')
            path = Path(fh.name)
        try:
            with self.assertRaises(ValueError) as ctx:
                load_probes(path)
            self.assertIn("Unknown probe type", str(ctx.exception))
        finally:
            path.unlink()

    def test_missing_type_raises_at_load_time(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write('[[probe]]\npath = "/"\n')
            path = Path(fh.name)
        try:
            with self.assertRaises(ValueError) as ctx:
                load_probes(path)
            self.assertIn("type", str(ctx.exception).lower())
        finally:
            path.unlink()

    def test_invalid_interval_raises_at_load_time(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write('[[probe]]\ntype = "disk"\ninterval = "fast"\n')
            path = Path(fh.name)
        try:
            with self.assertRaises(ValueError) as ctx:
                load_probes(path)
            self.assertIn("interval", str(ctx.exception).lower())
        finally:
            path.unlink()

    def test_non_positive_interval_raises_at_load_time(self) -> None:
        with tempfile.NamedTemporaryFile("w", suffix=".toml", delete=False) as fh:
            fh.write('[[probe]]\ntype = "disk"\ninterval = 0\n')
            path = Path(fh.name)
        try:
            with self.assertRaises(ValueError) as ctx:
                load_probes(path)
            self.assertIn("interval", str(ctx.exception).lower())
        finally:
            path.unlink()


class RegistryTests(TestCase):
    def test_known_types_include_builtins(self) -> None:
        self.assertIn("disk", known_types())
        self.assertIn("ping", known_types())

    def test_get_factory_for_unknown_type_raises(self) -> None:
        with self.assertRaises(ValueError):
            get_factory("not-real")

    def test_register_new_factory(self) -> None:
        def fake_factory(params: dict[str, object]) -> tuple[str, object]:
            return "fake", lambda: 1.0

        register("fake", fake_factory)  # type: ignore[arg-type]
        self.assertIn("fake", known_types())
        self.assertIs(get_factory("fake"), fake_factory)
