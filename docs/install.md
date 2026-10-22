# Installation guide

Choose the setup that matches how you want to run inframagotchi.

- [Desktop (all-in-one)](#desktop-all-in-one) — probes, engine, and window on the same machine.
- [Server + client](#server--client) — engine on a headless box, window on your daily desktop.

Both assume a Linux host (Arch packages are shown; adapt names for Debian, Fedora, etc.).

> **Shortcut — Qt backend.** If you prefer not to depend on the system GTK/WebKit stack,
> install the `qt` extra instead: `uv sync --extra qt` (or `pip install ".[qt]"`).
> pywebview then renders through PyQt6 + Qt WebEngine, installed from PyPI, and the
> `--system-site-packages` venv below is not needed.

## Common prerequisites

pywebview renders through the **system** GTK/WebKit stack, so the Python environment must see the system bindings.

```sh
# 1. system deps (Arch) — names may vary
sudo pacman -S --needed webkit2gtk-4.1 python-gobject python-cairo

# 2. create a venv that can see them
uv venv --system-site-packages
uv sync
```

If the window stays blank or you see a `gi` / WebKit import error, recreate the venv with `--system-site-packages` and make sure WebKitGTK is installed. Do **not** pip-install GTK packages into the venv.

## Desktop (all-in-one)

Everything runs on one machine. This is the simplest setup and the default mode.

### Install

```sh
git clone https://github.com/bengua/inframagotchi
cd inframagotchi
uv venv --system-site-packages
uv sync
```

### Run

```sh
uv run python app.py
```

The engine starts on `127.0.0.1:8080` and the window opens on it. Probes run locally.

### Make it survive reboots (systemd user service)

```sh
uv pip install -e .
mkdir -p ~/.config/systemd/user
cp contrib/inframagotchi.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now inframagotchi
```

The default unit binds the engine to `127.0.0.1:8080`. No firewall rule is needed on a single machine, but you cannot connect a remote client unless you change the bind address (use the server setup below for that).

## Server + client

This is the common homelab split: one engine running on a small server or VM, and a client window on your daily desktop.

### Server install (headless)

```sh
git clone https://github.com/bengua/inframagotchi
cd inframagotchi
uv venv --system-site-packages
uv sync

# copy the example config and adapt it
cp inframagotchi.json ~/.config/inframagotchi/inframagotchi.json
$EDITOR ~/.config/inframagotchi/inframagotchi.json
```

Run the engine on all interfaces so the client can reach it:

```sh
uv run python app.py --serve --host 0.0.0.0 --port 8080
```

Put the server behind your LAN firewall / VPN. The default `--host 127.0.0.1` is safer but unreachable from another host.

### Run server as a service

```sh
uv pip install -e .
mkdir -p ~/.config/systemd/user
cp contrib/inframagotchi.service ~/.config/systemd/user/
# edit ExecStart if you want --host 0.0.0.0
systemctl --user daemon-reload
systemctl --user enable --now inframagotchi
```

### Client install (window only)

The client machine needs only the project files and the same GTK/WebKit system packages; no probes run locally.

```sh
git clone https://github.com/bengua/inframagotchi
cd inframagotchi
uv venv --system-site-packages
uv sync
```

### Run client

```sh
uv run python app.py --connect http://<server-ip>:8080
```

No config file is required on the client; the cat renders the health number it receives from the engine.

## Configuration

Probes are declared in `inframagotchi.json`. The file is searched in this order:

1. `$INFRAMAGOTCHI_CONFIG`
2. `./inframagotchi.json`
3. `$XDG_CONFIG_HOME/inframagotchi/inframagotchi.json`
4. `~/.config/inframagotchi/inframagotchi.json`

Missing or invalid config falls back to a single portable disk probe on `/`.

Example config:

```json
{
  "avatar": "avatars/dog.html",
  "probe": [
    { "type": "disk", "path": "/", "warn": 0.8, "critical": 0.95 },
    { "type": "service", "unit": "sshd.service" },
    { "type": "ping", "host": "1.1.1.1", "count": 1, "timeout": 5 }
  ]
}
```

See `README.md` for the full probe catalog.

## Updating

```sh
cd inframagotchi
git pull
uv sync
systemctl --user restart inframagotchi
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Blank window / `gi` import error | venv cannot see GTK/WebKit | Recreate with `uv venv --system-site-packages` |
| Cannot connect from client | Engine bound to `127.0.0.1` | Start server with `--host 0.0.0.0` and firewall it |
| `POST /config` from network | Engine exposed, no auth | Restrict with firewall or VPN; bind to LAN only |
| Probe crashes on non-Linux host | Linux-only tool missing | All platform-specific probes already fail soft; just ignore |
