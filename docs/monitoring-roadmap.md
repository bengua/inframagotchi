# Monitoring roadmap

This file tracks the big architectural milestones and the likely next steps for
inframagotchi. It is **not a release schedule** — it is context for anyone
picking up the project.

## Shipped

### 1. Foundations — project skeleton and probe contract
- `probes/` package with a typed contract: each probe returns `float | None` in
  `[0, 1]` (`1` = healthy); `None` means "cannot run here" and is treated as
  neutral.
- Registry + factory pattern so new probes plug in without touching the engine or
  the frontend.
- Portable disk probe as the default fallback.

### 2. Local probes
- `disk` with optional `warn`/`critical` thresholds.
- `ram`, `load` (Linux-only, fail-soft off Linux).

### 3. Network and external probes
- `http` endpoint latency probe.
- `ssh` remote-command probe (key-based, BatchMode).
- `service`, `cert`, `backup`, `ping`.

### 4. Scheduler and state
- `HealthState` thread-safe aggregate store.
- `ProbeScheduler` runs one thread per probe on its own interval.
- Aggregate health = weakest non-`None` probe.

### 5. HTTP engine and frontend polling
- `engine.py` serves the cat and exposes `/health`, `/status`.
- Static `web/` frontend is unchanged from the browser version and polls the
  engine.
- Runtime modes: desktop, server (`--serve`), client (`--connect`).

### 6. Hamburger panel
- Slide-in diagnostics panel showing aggregate health, weakest link, and the
  per-probe score table.
- Add reduced-motion support and keyboard/Escape handling.

### 7. Live config editing
- Config format moved to JSON (stdlib read/write); TOML still readable.
- `GET /config` and `POST /config` for retrieval, validation, atomic write, and
  hot reload.
- UI tab with textarea + save button.
- `app.py` wired as a reloadable `App` class.

## Likely next

### Packaging and install experience
- systemd user service template and instructions.
- Release workflow (version bump, git tag, sdist/wheel).
- Console script entry point already exists; verify it in a clean venv.

### Headless / remote operation
- Better discoverability for the `--connect` mode.
- Optional authentication or localhost-only guidance for `POST /config` when
  exposed to a network.

### New probes (only if they stay fail-soft and asset-free)
- `docker` container health.
- `zfs` pool health / `smartctl` disk checks.
- `wireguard` / `tailscale` interface checks.

### UI quality of life
- Minimize to system tray so the cat can run in the background.
- Keep the renderer decoupled: it still only ever receives one health number.
