# Fedora and Plasma packaging notes

## Build requirements

The native frontend currently needs:

- CMake, Ninja, and a C++20 compiler
- Qt 6 Core, DBus, Gui, QML, Quick, Quick Controls, and Widgets development files
- Extra CMake Modules
- `kf6-kconfig-devel`
- `kf6-kcoreaddons-devel`
- `kf6-kglobalaccel-devel`
- `kf6-knotifications-devel`
- `kf6-kservice-devel`
- `openssl-devel`
- the system Python 3 interpreter

`kf6-kstatusnotifieritem-devel` is recommended for direct Plasma status-notifier
integration. The build remains usable without it and falls back to Qt's native
system-tray interface.

Configure RPM builds with `-DCMAKE_INSTALL_PREFIX=/usr`. The CMake project
prefers `/usr/bin/python3` so the installed service sees Fedora's packaged
Proton modules instead of a user virtual environment.

## Runtime requirements

- `kf6-kirigami`
- `kf6-kconfig`
- `kf6-kcoreaddons`
- `kf6-kglobalaccel`
- `kf6-knotifications`
- `kf6-kservice`
- `python3-dbus-fast`
- `python3-cryptography`
- `python3-fido2`
- `python3-proton-vpn-api-core`
- Proton's existing protocol, NetworkManager, kill-switch, and
split-tunneling packages pulled in by the core

`KService` provides the application catalog used by the split-tunneling
chooser. The frontend does not load Gio or parse desktop-entry files itself.
`KGlobalAccel` registers optional Plasma-wide connection and window actions.
No shortcut is assigned by the package; users choose keys in System Settings,
and their assignments are preserved by Plasma.

Add `kf6-kstatusnotifieritem` when the frontend was built with its development
component; otherwise the Qt tray fallback has no KF6 StatusNotifierItem runtime
dependency.

The KDE package must not require `proton-vpn-gtk-app`, PyGObject, GTK, or
GNOME Keyring. Authentication storage remains the official core's Freedesktop
Secret Service integration, so KeePassXC, KWallet, or another conforming
provider can supply it.

## Coexistence during development

Do not obsolete or conflict with the official GTK package yet. Both clients
can be installed, but only one frontend/backend pair should actively own the
Proton core session at a time. The official GTK client currently also owns its
reconnection service and data refresher, so simultaneous live testing could
produce duplicate refreshers or competing connection operations.

The KDE backend uses a session-bus service and an unprivileged systemd user
unit. It does not replace the existing privileged split-tunneling daemon.
Normal RPM installation restores the expected SELinux labels for all installed
paths; no custom policy or setuid component should be necessary. Install the
notification metadata under `/usr/share/knotifications6` and leave the user
configuration in the standard KConfig path as `proton-vpn-kderc`.

Authentication secret transport uses OpenSSL 3 for ephemeral X25519,
HKDF-SHA256, and AES-256-GCM; Python's `cryptography` package implements the
matching backend. Ciphertext is carried with Linux `memfd_create`, file seals,
and D-Bus Unix file-descriptor passing. These are available on supported Fedora
releases and require no filesystem storage, privileged helper, or custom SELinux
rule.

The optional Beta access control is shown only when either Proton's
`protonvpn-stable-release` or `protonvpn-beta-release` repository package is
installed and both `pkexec` and `dnf` are available. It swaps only those exact
repository packages after an interactive Polkit authorization. It deliberately
does not reinstall `proton-vpn-gnome-desktop`, replace this KDE package, or run a
general system upgrade; the user applies offered package updates afterward in
Discover or with `dnf`.

## Suggested package checks

```bash
ruff check backend
PYTHONPATH=backend /usr/bin/python3 -m unittest discover -s backend/tests -v
cmake --build %{__cmake_builddir}
ctest --test-dir %{__cmake_builddir} --output-on-failure
dbus-run-session -- scripts/smoke-demo.sh
dbus-run-session -- scripts/smoke-auth-demo.sh
```

The smoke test always uses the deterministic demo adapter and cannot touch a
Proton account, NetworkManager, or an active VPN connection.
