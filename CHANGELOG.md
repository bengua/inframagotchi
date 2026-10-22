# Changelog

## Unreleased

### Added
- Optional `qt` extra (`pip install ".[qt]"`): pywebview's Qt backend (PyQt6 + Qt WebEngine), no system GTK/WebKit needed.
- Optional job-runner integration: `/runs` and `/runs/<id>` read `INFRAMAGOTCHI_RUNS_DIR` / `INFRAMAGOTCHI_RUN_EVENTS_DIR` and stay empty when unset.
- GitHub Actions CI (ruff + pytest, Qt offscreen).

### Changed
- The `chain` probe defaults to `runs/records` (relative) instead of a host-specific path.
- Replaced the canvas cat renderer with the improved animated cat template, including CPU/load slider and richer emotes.

## 0.2.1 — 2026-06-19

### Fixed
- Desktop and client window startup crash with pywebview 6 (`webview.start` API change).

## 0.2.0 — 2026-06-19

### Added
- Full config editing flow: `GET /config` and `POST /config` endpoints, atomic JSON writes, and a live config tab in the hamburger panel.
- JSON config format (`inframagotchi.json`) with legacy TOML read support (`inframagotchi.toml`).
- Example config covering disk, ram, load, service, cert, backup, ping, http, and ssh probes.
- systemd user service template in `contrib/inframagotchi.service`.

### Changed
- README rewritten for the current feature set: runtime modes, all probe types, endpoints, and fail-soft behaviour.

## 0.1.0 — 2026-06-19

### Added
- Initial release: pywebview runtime, canvas cat renderer, HTTP engine, probe scheduler, and local/network probes.
