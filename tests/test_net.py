"""Tests for network probes (http and ssh)."""

from __future__ import annotations

import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread
from unittest import TestCase
from unittest.mock import Mock, patch

from probes.net import make_http, make_ssh


class MockHTTPHandler(BaseHTTPRequestHandler):
    """Tiny handler that sleeps on /slow, 404s on /missing, 200 otherwise."""

    def do_GET(self) -> None:
        if self.path == "/missing":
            self.send_response(404)
            self.end_headers()
            return
        if self.path == "/slow":
            time.sleep(0.2)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, format: str, *args: object) -> None:
        pass


class HttpProbeTests(TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = HTTPServer(("127.0.0.1", 0), MockHTTPHandler)
        cls.port = cls.server.server_address[1]
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()

    def test_healthy_fast_endpoint(self) -> None:
        _, probe = make_http(
            {"url": f"http://127.0.0.1:{self.port}/", "warn_ms": 1000, "critical_ms": 2000}
        )
        self.assertEqual(probe(), 1.0)

    def test_slow_endpoint_returns_warning_score(self) -> None:
        _, probe = make_http(
            {"url": f"http://127.0.0.1:{self.port}/slow", "warn_ms": 50, "critical_ms": 500}
        )
        score = probe()
        self.assertTrue(0.0 < score < 1.0)

    def test_unreachable_returns_zero(self) -> None:
        _, probe = make_http({"url": "http://127.0.0.1:1/", "timeout": 1})
        self.assertEqual(probe(), 0.0)

    def test_bad_status_returns_zero(self) -> None:
        _, probe = make_http({"url": f"http://127.0.0.1:{self.port}/missing", "timeout": 1})
        self.assertEqual(probe(), 0.0)

    def test_missing_url_returns_zero(self) -> None:
        _, probe = make_http({})
        self.assertEqual(probe(), 0.0)


class SshProbeTests(TestCase):
    def test_success_returns_one(self) -> None:
        result = Mock(returncode=0, stdout="active\n")
        with patch("probes.net.subprocess.run", return_value=result):
            _, probe = make_ssh(
                {"host": "hypervisor.homelab.local", "user": "root", "command": "systemctl is-active pvedaemon"}
            )
            self.assertEqual(probe(), 1.0)

    def test_expected_regex_match(self) -> None:
        result = Mock(returncode=0, stdout="VM 101 running\n")
        with patch("probes.net.subprocess.run", return_value=result):
            _, probe = make_ssh(
                {"host": "hypervisor.homelab.local", "user": "root", "command": "qm list", "expected": "running"}
            )
            self.assertEqual(probe(), 1.0)

    def test_expected_regex_no_match_returns_zero(self) -> None:
        result = Mock(returncode=0, stdout="VM 101 stopped\n")
        with patch("probes.net.subprocess.run", return_value=result):
            _, probe = make_ssh(
                {"host": "hypervisor.homelab.local", "user": "root", "command": "qm list", "expected": "running"}
            )
            self.assertEqual(probe(), 0.0)

    def test_nonzero_exit_returns_zero(self) -> None:
        result = Mock(returncode=1, stdout="")
        with patch("probes.net.subprocess.run", return_value=result):
            _, probe = make_ssh({"host": "hypervisor.homelab.local", "command": "true"})
            self.assertEqual(probe(), 0.0)

    def test_missing_ssh_binary_returns_none(self) -> None:
        with patch("probes.net.subprocess.run", side_effect=FileNotFoundError()):
            _, probe = make_ssh({"host": "hypervisor.homelab.local", "command": "true"})
            self.assertIsNone(probe())

    def test_timeout_returns_none(self) -> None:
        import subprocess

        with patch("probes.net.subprocess.run", side_effect=subprocess.TimeoutExpired("ssh", 10)):
            _, probe = make_ssh({"host": "hypervisor.homelab.local", "command": "true"})
            self.assertIsNone(probe())
