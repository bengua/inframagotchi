"""Tests for local system probes (load, ram, disk with thresholds)."""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import Mock, mock_open, patch

from probes.local import make_disk, make_load, make_ram


class DiskProbeTests(TestCase):
    def test_healthy_free_fraction(self) -> None:
        usage = Mock(free=75, total=100)
        with patch("probes.local.shutil.disk_usage", return_value=usage):
            _, probe = make_disk({"path": "/"})
            result = probe()
        self.assertEqual(result, 0.75)

    def test_full_disk(self) -> None:
        usage = Mock(free=0, total=100)
        with patch("probes.local.shutil.disk_usage", return_value=usage):
            _, probe = make_disk({"path": "/"})
            result = probe()
        self.assertEqual(result, 0.0)

    def test_unavailable_path_returns_none(self) -> None:
        with patch("probes.local.shutil.disk_usage", side_effect=OSError("nope")):
            _, probe = make_disk({"path": "/nonexistent"})
            self.assertIsNone(probe())

    def test_threshold_healthy(self) -> None:
        # 50% used, warn 80%, critical 95% → healthy
        usage = Mock(free=50, total=100)
        with patch("probes.local.shutil.disk_usage", return_value=usage):
            _, probe = make_disk({"path": "/", "warn": 0.80, "critical": 0.95})
            result = probe()
        self.assertEqual(result, 1.0)

    def test_threshold_warning(self) -> None:
        # 87.5% used → midway between warn (80%) and critical (95%) → ~0.5
        usage = Mock(free=12.5, total=100)
        with patch("probes.local.shutil.disk_usage", return_value=usage):
            _, probe = make_disk({"path": "/", "warn": 0.80, "critical": 0.95})
            result = probe()
        self.assertAlmostEqual(result, 0.5, places=5)

    def test_threshold_critical(self) -> None:
        usage = Mock(free=3, total=100)
        with patch("probes.local.shutil.disk_usage", return_value=usage):
            _, probe = make_disk({"path": "/", "warn": 0.80, "critical": 0.95})
            result = probe()
        self.assertEqual(result, 0.0)


class LoadProbeTests(TestCase):
    def test_healthy(self) -> None:
        with (
            patch("probes.local.os.getloadavg", return_value=(1.0, 2.0, 3.0)),
            patch("probes.local.os.cpu_count", return_value=4),
        ):
            _, probe = make_load({"warn": 2.0, "critical": 4.0})
            result = probe()
        self.assertEqual(result, 1.0)

    def test_critical(self) -> None:
        with (
            patch("probes.local.os.getloadavg", return_value=(5.0, 6.0, 7.0)),
            patch("probes.local.os.cpu_count", return_value=4),
        ):
            _, probe = make_load({"warn": 2.0, "critical": 4.0})
            result = probe()
        self.assertEqual(result, 0.0)

    def test_auto_thresholds(self) -> None:
        with (
            patch("probes.local.os.getloadavg", return_value=(4.0, 5.0, 6.0)),
            patch("probes.local.os.cpu_count", return_value=4),
        ):
            _, probe = make_load({})
            result = probe()
        # warn=4, critical=8 → load=4 is right at warn → 1.0
        self.assertEqual(result, 1.0)

    def test_missing_getloadavg_returns_none(self) -> None:
        with patch("probes.local.os.getloadavg", side_effect=AttributeError()):
            _, probe = make_load({})
            self.assertIsNone(probe())

    def test_os_error_returns_none(self) -> None:
        with patch("probes.local.os.getloadavg", side_effect=OSError()):
            _, probe = make_load({})
            self.assertIsNone(probe())


class RamProbeTests(TestCase):
    def test_healthy(self) -> None:
        meminfo = "MemTotal:       10000000 kB\nMemAvailable:    8000000 kB\n"
        with patch("probes.local.open", mock_open(read_data=meminfo)):
            _, probe = make_ram({"warn": 0.75, "critical": 0.90})
            result = probe()
        # 20% used → healthy
        self.assertEqual(result, 1.0)

    def test_critical(self) -> None:
        meminfo = "MemTotal:       10000000 kB\nMemAvailable:     500000 kB\n"
        with patch("probes.local.open", mock_open(read_data=meminfo)):
            _, probe = make_ram({"warn": 0.75, "critical": 0.90})
            result = probe()
        # 95% used → critical
        self.assertEqual(result, 0.0)

    def test_missing_proc_meminfo_returns_none(self) -> None:
        with patch("probes.local.open", side_effect=FileNotFoundError()):
            _, probe = make_ram({})
            self.assertIsNone(probe())

    def test_default_score_is_available_fraction(self) -> None:
        meminfo = "MemTotal:       10000000 kB\nMemAvailable:    5000000 kB\n"
        with patch("probes.local.open", mock_open(read_data=meminfo)):
            _, probe = make_ram({})
            result = probe()
        # 50% available → 0.5
        self.assertEqual(result, 0.5)
