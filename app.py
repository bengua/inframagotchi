"""inframagotchi — native runtime.

Drives a manga stray cat in a window whose health reflects the homelab.
The app can run in three modes:

- desktop (default): start the HTTP engine and open a local pywebview window on it.
- server (--serve): start only the HTTP engine, no window.
- client (--connect URL): open only the pywebview window on a remote engine.

See README.md for system deps (pywebview needs system GTK/WebKit).
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import webview

from engine import DEFAULT_HOST, DEFAULT_PORT, Engine
from probes._config import active_config_path, load_config, save_config
from probes.loader import load_probes
from probes.scheduler import ProbeScheduler
from probes.state import HealthState

HERE = Path(__file__).resolve().parent
WEB_ROOT = HERE / "web"
PET_SIZE_DEFAULT = 240


class App:
    """Owns the scheduler, state cache, and HTTP engine lifetime.

    The engine can call back into ``reload_config`` when the frontend posts a
    new config. The scheduler is stopped and rebuilt atomically during reload.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        config_path: Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self._config_path = config_path or active_config_path()
        self._avatar = (load_config(self._config_path).get("avatar") or "").lstrip("/")
        self.state = HealthState()
        self.engine = Engine(
            self.state,
            WEB_ROOT,
            host=host,
            port=port,
            reload_fn=self.reload_config,
        )
        self.scheduler: ProbeScheduler | None = None
        self._start_or_reload_scheduler()

    def _start_or_reload_scheduler(self, text: str | None = None) -> None:
        """Build probes, stop any previous scheduler, start a new one."""
        if text is not None:
            self._config_path = save_config(text, self._config_path)
        probes = load_probes(self._config_path)
        if self.scheduler is not None:
            self.scheduler.stop(timeout=10.0)
        self.state.clear()
        self.scheduler = ProbeScheduler(self.state, probes)
        self.scheduler.start()

    def reload_config(self, text: str) -> None:
        """Validate, save, and reload the active config from *text*."""
        self._start_or_reload_scheduler(text)

    def _open_window(self, url: str) -> None:
        """Open the cat window on the given engine URL and block until closed."""
        webview.create_window(
            "inframagotchi",
            url=url,
            width=480,
            height=600,
            background_color="#0a0a0e",
            resizable=True,
        )
        webview.start()

    def run(self, serve: bool = False) -> None:
        """Start the engine and enter the requested run mode."""
        self.engine.start()
        try:
            if serve:
                # Server mode: block forever; engine thread does the work.
                while True:
                    time.sleep(1)
            else:
                # Desktop mode: local engine + local window.
                url = self.engine.url
                if self._avatar:
                    url = f"{self.engine.url}/{self._avatar}"
                self._open_window(url)
        finally:
            self.engine.stop(timeout=5.0)
            if self.scheduler is not None:
                self.scheduler.stop(timeout=5.0)


def _window_kwargs(url: str, pet: bool, pet_size: int) -> dict:
    """Build the ``create_window`` kwargs for the requested window style.

    Pet mode opens a square, frameless, transparent, always-on-top window that
    follows the cursor; otherwise the standard opaque 480x600 window.
    """
    if pet:
        return {
            "url": url,
            "width": pet_size,
            "height": pet_size,
            "frameless": True,
            "transparent": True,
            "on_top": True,
            "easy_drag": True,
            "resizable": False,
        }
    return {
        "url": url,
        "width": 480,
        "height": 600,
        "background_color": "#0a0a0e",
        "resizable": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="inframagotchi — infra tamagotchi")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run the HTTP engine only, without a window.",
    )
    parser.add_argument(
        "--connect",
        metavar="URL",
        help="Open a client window on a remote engine (no local engine).",
    )
    parser.add_argument(
        "--pet",
        action="store_true",
        help="Open a square, frameless, transparent, always-on-top pet window.",
    )
    parser.add_argument(
        "--pet-size",
        type=int,
        default=PET_SIZE_DEFAULT,
        help=f"Side of the square pet window in pixels (default: {PET_SIZE_DEFAULT}).",
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Engine bind address (default: {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Engine port (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to the inframagotchi config file.",
    )
    args = parser.parse_args()

    if args.connect:
        # Client mode: no local engine, no scheduler; just the window.
        webview.create_window(
            "inframagotchi",
            **_window_kwargs(args.connect, args.pet, args.pet_size),
        )
        webview.start()
        return

    app = App(host=args.host, port=args.port, config_path=args.config)
    app.run(serve=args.serve)


if __name__ == "__main__":
    main()
