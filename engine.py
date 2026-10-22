"""HTTP engine that exposes health/state/config and serves the static frontend."""

from __future__ import annotations

import json
import mimetypes
import os
import re
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlsplit
from pathlib import Path
from threading import Thread
from typing import Any, Callable

from probes import _config
from probes.state import HealthState

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
# Optional job-runner integration (off by default): when these environment
# variables point at directories, /runs lists JSON run records and /runs/<id>
# streams the matching JSONL event log. Unset, both endpoints return empty lists.
RUNS_DIR_ENV = "INFRAMAGOTCHI_RUNS_DIR"
RUN_EVENTS_DIR_ENV = "INFRAMAGOTCHI_RUN_EVENTS_DIR"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")

ReloadFn = Callable[[str], None]


class EngineHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler: /health, /status, /config and static files from web/."""

    def __init__(
        self,
        state: HealthState,
        web_root: Path,
        reload_fn: ReloadFn | None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        self._state = state
        self._web_root = web_root
        self._reload_fn = reload_fn
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json_response({"health": self._state.aggregate()})
            return
        if self.path == "/status":
            self._json_response({"probes": self._state.snapshot()})
            return
        if self.path == "/config":
            self._serve_config()
            return
        if self.path == "/runs":
            self._serve_runs()
            return
        if self.path.startswith("/runs/"):
            self._serve_run(self.path[len("/runs/") :])
            return
        self._serve_static()

    def do_POST(self) -> None:
        if self.path == "/config":
            self._save_config()
            return
        self._send_error(404, "Not found")

    def _serve_config(self) -> None:
        """Return the raw active config text, or the default JSON config."""
        text = _config.active_config_text()
        if not text:
            text = json.dumps(_config.DEFAULT_CONFIG, indent=2) + "\n"
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _save_config(self) -> None:
        """Validate, persist, and reload the posted config."""
        if self._reload_fn is None:
            self._json_response({"ok": False, "error": "Config editing disabled"}, 405)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            self._json_response({"ok": False, "error": "Empty body"}, 400)
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            text = body.get("text")
            if text is None or not isinstance(text, str):
                raise ValueError("Request body must include a 'text' string field.")
            self._reload_fn(text)
            self._json_response({"ok": True})
        except (json.JSONDecodeError, ValueError) as exc:
            self._json_response({"ok": False, "error": str(exc)}, 400)
        except Exception as exc:
            self._json_response({"ok": False, "error": str(exc)}, 500)

    def _runs_dir(self) -> Path | None:
        value = os.environ.get(RUNS_DIR_ENV)
        return Path(value) if value else None

    def _state_dir(self) -> Path | None:
        value = os.environ.get(RUN_EVENTS_DIR_ENV)
        return Path(value) if value else None

    def _serve_runs(self) -> None:
        """List the recent job-runner records, newest first, at most 20."""
        records_dir = self._runs_dir()
        runs: list[dict[str, Any]] = []
        if records_dir is not None and records_dir.is_dir():
            for path in records_dir.glob("*.json"):
                try:
                    record = json.loads(path.read_text("utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if not isinstance(record, dict):
                    continue
                runs.append(
                    {
                        "run_id": record.get("run_id"),
                        "state": record.get("state"),
                        "target": record.get("target"),
                        "ended_at": record.get("ended_at"),
                    }
                )
        runs.sort(key=lambda r: r.get("started_at") or 0, reverse=True)
        self._json_response({"runs": runs[:20]})

    def _serve_run(self, run_id: str) -> None:
        """Return the event stream of one run as a JSON list, last 500 lines."""
        run_id = unquote(run_id)
        if not RUN_ID_RE.match(run_id):
            self._send_error(400, "Invalid run id")
            return
        state_dir = self._state_dir()
        events: list[dict[str, Any]] = []
        path = state_dir / "runs" / f"{run_id}.jsonl" if state_dir is not None else None
        if path is not None and path.is_file():
            with path.open("r", encoding="utf-8") as handle:
                for line in deque(handle, maxlen=500):
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(event, dict):
                        events.append(event)
        self._json_response({"events": events})

    def _serve_static(self) -> None:
        target = self._web_root / urlsplit(self.path).path.lstrip("/")
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            self._send_error(404, "Not found")
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_response(self, payload: dict[str, Any], code: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, message: str) -> None:
        body = message.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # Keep logs quiet; the engine is a background concern.
        pass


class Engine:
    """Runs the HTTP server in a background thread."""

    def __init__(
        self,
        state: HealthState,
        web_root: Path,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        reload_fn: ReloadFn | None = None,
    ) -> None:
        self.state = state
        self.web_root = Path(web_root)
        self.host = host
        self.port = port
        self._reload_fn = reload_fn
        self._server: ThreadingHTTPServer | None = None
        self._thread: Thread | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        """Start the server in a daemon thread."""
        reload_fn = self._reload_fn

        def handler(*args: Any, **kwargs: Any) -> EngineHandler:
            return EngineHandler(self.state, self.web_root, reload_fn, *args, **kwargs)

        self._server = ThreadingHTTPServer((self.host, self.port), handler)
        self._thread = Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self, timeout: float | None = None) -> None:
        """Signal the server to stop and wait for the thread."""
        if self._server is not None:
            self._server.shutdown()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
