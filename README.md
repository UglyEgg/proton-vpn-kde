# Proton VPN for KDE Plasma

An experimental native KDE Plasma frontend for Proton VPN.

The GUI is C++/Qt 6 with Kirigami and has no GTK dependency. It talks over a
small, versioned session D-Bus interface to a headless service that reuses
Proton's official Python VPN core. Networking, protocol selection, kill switch,
split tunneling, and persisted connection state remain owned by Proton's core.

## Current milestone

- Native Qt 6/Kirigami overview window
- Plasma system tray integration, using `KStatusNotifierItem` when available
- Versioned D-Bus contract with JSON snapshots
- D-Bus activation and a systemd user service for installed builds
- Safe demo backend for UI development
- Opt-in Proton core adapter for the existing logged-in session
- Fastest, country, and individual-server connection actions
- Native country and server lists with localized country names, load, P2P,
  and streaming metadata
- Native country/server filtering without rebuilding or copying location data
- Provider-agnostic Secret Service initialization that cannot block D-Bus
- Desktop-neutral asyncio reconnection after an unexpected tunnel drop; the
  previous server, protocol, and backend are reused without a GLib main loop
- Plasma connection notifications through `KNotification`
- Persistent Plasma settings through KConfig for reconnection, notifications,
  close-to-tray, and start-minimized behavior

The real backend is intentionally not auto-started from the development tree.
This prevents an unfinished frontend from changing a working VPN session.
Packaged builds install D-Bus and systemd user-service metadata so the backend
is activated automatically when the GUI requests its first state snapshot.

## Build the frontend

```bash
cmake -S . -B build -G Ninja
cmake --build build
cmake --install build
```

The top-level install includes the Qt/Kirigami frontend, Python backend,
desktop entry, icon, D-Bus activation metadata, and systemd user unit. Fedora
packagers can still build `backend/pyproject.toml` as a separate noarch package.

For full Plasma tray integration on Fedora:

```bash
sudo dnf install kf6-kconfig-devel kf6-knotifications-devel \
    kf6-kstatusnotifieritem-devel
```

Kirigami is loaded as a QML runtime dependency. Install
`kf6-kirigami` if it is not already part of the Plasma desktop.

## Run safely in demo mode

Start the backend:

```bash
PYTHONPATH=backend python3 -m proton_vpn_kde_backend --demo
```

Then start the frontend:

```bash
./build/proton-vpn-kde
```

Demo mode never touches NetworkManager, Proton credentials, or the active VPN.

Run the complete local verification with:

```bash
ctest --test-dir build --output-on-failure
PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v
dbus-run-session -- scripts/smoke-demo.sh
```

## Real backend development mode

```bash
PYTHONPATH=backend python3 -m proton_vpn_kde_backend
```

Real mode uses the official installed `python3-proton-vpn-api-core`. It does not
connect automatically, but by default it recovers an unexpectedly dropped
active tunnel. An intentional disconnect always remains disconnected. Until
login and full error handling are implemented, it expects an existing Proton
session created by the official client.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the safety and migration
boundaries and [docs/FEDORA.md](docs/FEDORA.md) for packaging and coexistence
notes.
