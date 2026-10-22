"""Tests for probe factories and aggregation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from probes import health
from probes._probes import (
    make_backup,
    make_cert,
    make_disk,
    make_ping,
    make_service,
)


class DiskProbeTests(TestCase):
    def test_healthy(self) -> None:
        usage = Mock(free=75, total=100)
        with patch("probes._probes.shutil.disk_usage", return_value=usage):
            _, probe = make_disk({"path": "/"})
            self.assertEqual(probe(), 0.75)

    def test_full(self) -> None:
        usage = Mock(free=0, total=100)
        with patch("probes._probes.shutil.disk_usage", return_value=usage):
            _, probe = make_disk({"path": "/"})
            self.assertEqual(probe(), 0.0)

    def test_unavailable_path_fails_soft(self) -> None:
        with patch("probes._probes.shutil.disk_usage", side_effect=OSError("nope")):
            _, probe = make_disk({"path": "/nonexistent"})
            self.assertEqual(probe(), 1.0)


class ServiceProbeTests(TestCase):
    def test_active(self) -> None:
        result = Mock(returncode=0, stdout="active\n")
        with patch("probes._probes.subprocess.run", return_value=result):
            _, probe = make_service({"unit": "sshd.service"})
            self.assertEqual(probe(), 1.0)

    def test_inactive(self) -> None:
        result = Mock(returncode=3, stdout="inactive\n")
        with patch("probes._probes.subprocess.run", return_value=result):
            _, probe = make_service({"unit": "foo.service"})
            self.assertEqual(probe(), 0.0)

    def test_missing_systemctl_fails_soft(self) -> None:
        with patch("probes._probes.subprocess.run", side_effect=FileNotFoundError()):
            _, probe = make_service({"unit": "foo.service"})
            self.assertEqual(probe(), 1.0)


class CertProbeTests(TestCase):
    def _cert_not_after(self, days: float) -> str:
        expiry = datetime.now(timezone.utc) + timedelta(days=days)
        return expiry.strftime("notAfter=%b %d %H:%M:%S %Y GMT")

    def test_healthy(self) -> None:
        result = Mock(returncode=0, stdout=self._cert_not_after(90))
        with (
            patch("probes._probes.os.path.isfile", return_value=True),
            patch("probes._probes.subprocess.run", return_value=result),
        ):
            _, probe = make_cert({"path": "/tmp/cert.pem"})
            self.assertEqual(probe(), 1.0)

    def test_warning(self) -> None:
        result = Mock(returncode=0, stdout=self._cert_not_after(15))
        with (
            patch("probes._probes.os.path.isfile", return_value=True),
            patch("probes._probes.subprocess.run", return_value=result),
        ):
            _, probe = make_cert({"path": "/tmp/cert.pem", "warn_days": 30, "critical_days": 7})
            score = probe()
            self.assertTrue(0.0 < score < 1.0)

    def test_critical(self) -> None:
        result = Mock(returncode=0, stdout=self._cert_not_after(3))
        with (
            patch("probes._probes.os.path.isfile", return_value=True),
            patch("probes._probes.subprocess.run", return_value=result),
        ):
            _, probe = make_cert({"path": "/tmp/cert.pem"})
            self.assertEqual(probe(), 0.0)

    def test_expired(self) -> None:
        result = Mock(returncode=0, stdout=self._cert_not_after(-1))
        with (
            patch("probes._probes.os.path.isfile", return_value=True),
            patch("probes._probes.subprocess.run", return_value=result),
        ):
            _, probe = make_cert({"path": "/tmp/cert.pem"})
            self.assertEqual(probe(), 0.0)

    def test_missing_file(self) -> None:
        with patch("probes._probes.os.path.isfile", return_value=False):
            _, probe = make_cert({"path": "/tmp/cert.pem"})
            self.assertEqual(probe(), 0.0)

    def test_missing_openssl_fails_soft(self) -> None:
        with (
            patch("probes._probes.os.path.isfile", return_value=True),
            patch("probes._probes.subprocess.run", side_effect=FileNotFoundError()),
        ):
            _, probe = make_cert({"path": "/tmp/cert.pem"})
            self.assertEqual(probe(), 1.0)


class BackupProbeTests(TestCase):
    def test_fresh(self) -> None:
        now = datetime(2026, 6, 19, 12, 0, 0).timestamp()
        with (
            patch("probes._probes.glob.glob", return_value=["/backups/a.gpg"]),
            patch("probes._probes.os.path.getmtime", return_value=now),
            patch("probes._probes.datetime") as mock_dt,
        ):
            mock_dt.now.return_value = datetime(2026, 6, 19, 12, 0, 0)
            mock_dt.side_effect = datetime
            _, probe = make_backup({"pattern": "/backups/*.gpg", "max_age_hours": 24})
            self.assertEqual(probe(), 1.0)

    def test_stale(self) -> None:
        old = datetime.now().timestamp() - 48 * 3600
        with (
            patch("probes._probes.glob.glob", return_value=["/backups/a.gpg"]),
            patch("probes._probes.os.path.getmtime", return_value=old),
        ):
            _, probe = make_backup({"pattern": "/backups/*.gpg", "max_age_hours": 24})
            self.assertEqual(probe(), 0.0)

    def test_no_files(self) -> None:
        with patch("probes._probes.glob.glob", return_value=[]):
            _, probe = make_backup({"pattern": "/backups/*.gpg"})
            self.assertEqual(probe(), 0.0)


class PingProbeTests(TestCase):
    def test_ok(self) -> None:
        result = Mock(returncode=0, stdout="")
        with patch("probes._probes.subprocess.run", return_value=result):
            _, probe = make_ping({"host": "1.1.1.1"})
            self.assertEqual(probe(), 1.0)

    def test_unreachable(self) -> None:
        result = Mock(returncode=1, stdout="")
        with patch("probes._probes.subprocess.run", return_value=result):
            _, probe = make_ping({"host": "192.0.2.1"})
            self.assertEqual(probe(), 0.0)

    def test_missing_ping_fails_soft(self) -> None:
        with patch("probes._probes.subprocess.run", side_effect=FileNotFoundError()):
            _, probe = make_ping({"host": "1.1.1.1"})
            self.assertEqual(probe(), 1.0)


class HealthTests(TestCase):
    def test_aggregate_min(self) -> None:
        with (
            patch("probes._PROBES", [lambda: 1.0, lambda: 0.25]),
            patch("probes.NAMES", ("a", "b")),
        ):
            self.assertEqual(health(), 25)

    def test_clamps_high_and_low(self) -> None:
        with (
            patch("probes._PROBES", [lambda: 2.0, lambda: -1.0]),
            patch("probes.NAMES", ("a", "b")),
        ):
            self.assertEqual(health(), 0)

    def test_exception_returns_healthy(self) -> None:
        with (
            patch("probes._PROBES", [lambda: (_ for _ in ()).throw(RuntimeError("boom"))]),
            patch("probes.NAMES", ("a",)),
        ):
            self.assertEqual(health(), 100)
