"""Tests for the HTTP engine."""

from __future__ import annotations

import json
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from unittest import TestCase, mock

from engine import DEFAULT_HOST, Engine
from probes import _config
from probes.state import HealthState


class EngineTests(TestCase):
    def setUp(self) -> None:
        self.state = HealthState()
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._config_path = Path(self._tmp_dir.name) / "inframagotchi.json"
        self.reloaded: list[str] = []
        self.engine = Engine(
            self.state,
            Path(__file__).parent.parent / "web",
            port=0,
            reload_fn=self._reload,
        )
        self.engine.start()
        # Wait briefly for the server to bind and start accepting.
        deadline = time.monotonic() + 2.0
        while self.engine._server is None and time.monotonic() < deadline:
            time.sleep(0.01)
        port = self.engine._server.server_address[1]
        self.base_url = f"http://{DEFAULT_HOST}:{port}"

    def tearDown(self) -> None:
        self.engine.stop(timeout=2.0)
        self._tmp_dir.cleanup()

    def _reload(self, text: str) -> None:
        # Use the real config writer so invalid configs raise ValueError.
        _config.save_config(text, self._config_path)
        self.reloaded.append(text)

    def _get(self, path: str) -> tuple[int, bytes]:
        with urllib.request.urlopen(f"{self.base_url}{path}", timeout=2.0) as resp:
            return resp.status, resp.read()

    def _post(
        self, path: str, body: bytes, content_type: str = "application/json"
    ) -> tuple[int, bytes]:
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_health_returns_neutral_when_state_empty(self) -> None:
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertIn(b'"health": 100', body)

    def test_health_reflects_aggregate(self) -> None:
        self.state.set("disk", 0.25)
        status, body = self._get("/health")
        self.assertEqual(status, 200)
        self.assertIn(b'"health": 25', body)

    def test_status_returns_snapshot(self) -> None:
        self.state.set("disk", 0.5)
        status, body = self._get("/status")
        self.assertEqual(status, 200)
        self.assertIn(b'"probes"', body)
        self.assertIn(b'"disk"', body)

    def test_static_index_served(self) -> None:
        status, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b'<canvas id="cat"', body)

    def test_static_index_with_query_string_served(self) -> None:
        status, body = self._get("/index.html?x=1")
        self.assertEqual(status, 200)

    def test_missing_static_returns_404(self) -> None:
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            self._get("/does-not-exist")
        self.assertEqual(ctx.exception.code, 404)

    def test_static_avatar_served(self) -> None:
        status, body = self._get("/avatars/dog.html")
        self.assertEqual(status, 200)
        self.assertIn(b"<title>inframagotchi \xe2\x80\x94 dog</title>", body)

    def test_config_get_returns_default_config(self) -> None:
        status, body = self._get("/config")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertIn("probe", data)

    def test_config_post_triggers_reload(self) -> None:
        payload = json.dumps({"text": '{"probe": []}'}).encode()
        status, body = self._post("/config", payload)
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertTrue(data["ok"])
        self.assertEqual(len(self.reloaded), 1)

    def test_config_post_rejects_invalid_json(self) -> None:
        payload = json.dumps({"text": "not json"}).encode()
        status, body = self._post("/config", payload)
        self.assertEqual(status, 400)
        data = json.loads(body)
        self.assertFalse(data["ok"])
        self.assertEqual(len(self.reloaded), 0)

    def _write_record(self, records_dir: Path, run_id: str, state: str,
                       target: str, ended_at: int) -> None:
        record = {"run_id": run_id, "state": state, "target": target,
                  "ended_at": ended_at}
        (records_dir / f"{run_id}.json").write_text(json.dumps(record), encoding="utf-8")

    def test_runs_lists_recent_runs_newest_first(self) -> None:
        records_dir = Path(self._tmp_dir.name) / "records"
        records_dir.mkdir()
        self._write_record(records_dir, "20260901-000000-aaa", "done", "example/one", 1)
        self._write_record(records_dir, "20260902-000000-bbb", "needs_human", "example/two", 3)
        self._write_record(records_dir, "20260903-000000-ccc", "running", "example/three", 2)
        # Malformed files are skipped silently.
        (records_dir / "broken.json").write_text("not json", encoding="utf-8")
        with mock.patch.dict("os.environ", {"INFRAMAGOTCHI_RUNS_DIR": str(records_dir)}):
            status, body = self._get("/runs")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual([run["run_id"] for run in data["runs"]],
                         ["20260903-000000-ccc", "20260902-000000-bbb", "20260901-000000-aaa"])
        first = data["runs"][0]
        self.assertEqual(first["state"], "running")
        self.assertEqual(first["target"], "example/three")
        self.assertEqual(first["ended_at"], 2)

    def test_runs_limits_to_twenty(self) -> None:
        records_dir = Path(self._tmp_dir.name) / "records"
        records_dir.mkdir()
        for i in range(25):
            self._write_record(records_dir, f"run{i:03d}", "done", "example/x", i)
        with mock.patch.dict("os.environ", {"INFRAMAGOTCHI_RUNS_DIR": str(records_dir)}):
            status, body = self._get("/runs")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(len(data["runs"]), 20)

    def test_runs_missing_dir_returns_empty_list(self) -> None:
        with mock.patch.dict("os.environ",
                             {"INFRAMAGOTCHI_RUNS_DIR": str(Path(self._tmp_dir.name) / "nope")}):
            status, body = self._get("/runs")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["runs"], [])

    def test_run_returns_event_stream(self) -> None:
        runs_dir = Path(self._tmp_dir.name) / "state" / "runs"
        runs_dir.mkdir(parents=True)
        lines = [json.dumps({"seq": i, "event": "tick"}) for i in range(600)]
        (runs_dir / "run1.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        with mock.patch.dict("os.environ",
                             {"INFRAMAGOTCHI_RUN_EVENTS_DIR": str(Path(self._tmp_dir.name) / "state")}):
            status, body = self._get("/runs/run1")
        self.assertEqual(status, 200)
        data = json.loads(body)
        events = data["events"]
        self.assertEqual(len(events), 500)
        self.assertEqual(events[0]["seq"], 100)
        self.assertEqual(events[-1]["seq"], 599)

    def test_run_skips_malformed_lines(self) -> None:
        runs_dir = Path(self._tmp_dir.name) / "state" / "runs"
        runs_dir.mkdir(parents=True)
        (runs_dir / "run2.jsonl").write_text(
            '{"seq": 1}\nnot json\n[1, 2]\n{"seq": 2}\n', encoding="utf-8")
        with mock.patch.dict("os.environ",
                             {"INFRAMAGOTCHI_RUN_EVENTS_DIR": str(Path(self._tmp_dir.name) / "state")}):
            status, body = self._get("/runs/run2")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual([e["seq"] for e in data["events"]], [1, 2])

    def test_run_missing_file_returns_empty_list(self) -> None:
        runs_dir = Path(self._tmp_dir.name) / "state" / "runs"
        runs_dir.mkdir(parents=True)
        with mock.patch.dict("os.environ",
                             {"INFRAMAGOTCHI_RUN_EVENTS_DIR": str(Path(self._tmp_dir.name) / "state")}):
            status, body = self._get("/runs/does-not-exist")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["events"], [])

    def test_run_rejects_bad_run_id(self) -> None:
        for bad in ("..%2Fetc", "a%2Fb", "a%20b", "a?b"):
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                self._get(f"/runs/{bad}")
            self.assertEqual(ctx.exception.code, 400)

    def test_engine_stops_cleanly(self) -> None:
        # tearDown already calls stop; just ensure no exception leaks.
        self.engine.stop(timeout=1.0)
