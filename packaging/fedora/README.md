# Fedora packaging

Fedora 44 with KDE Plasma 6 is the first supported package target. The RPM is
coexistence-safe: it neither conflicts with nor obsoletes Proton's GTK client,
and it reuses the installed official `python3-proton-vpn-api-core` networking
stack. The KDE package must not directly require GTK, PyGObject, Gio, GNOME
Keyring, or the Proton GTK application.

Proton's current Fedora API Core package itself requires
`NetworkManager-openvpn-gnome`, which brings GTK libraries into the installed
dependency graph. The Plasma frontend does not use that editor component. This
project retains the dependency because it belongs to Proton's supported Core
package contract; removing it requires separate upstream runtime evidence.

The spec is the authoritative build and runtime dependency list. The principal
native dependencies are Qt 6, KDE Frameworks 6, Kirigami, OpenSSL 3, and the
system Python interpreter. Runtime integration additionally uses
`python3-dbus-fast`, `python3-cryptography`, `python3-fido2`, and Proton VPN API
Core 5.5.6 or newer. Session storage reaches Freedesktop Secret Service through
Proton's separately packaged keyring adapter. Until the provider-neutral fixes
are upstream, this repository builds a reviewable downstream adapter from
Proton's pinned source and requires its explicit RPM capability. The verified
KeePassXC stack and retirement policy are recorded in
[Compatibility](../../docs/COMPATIBILITY.md); the client RPM never overwrites
an installed Python file outside package ownership.

## Build

Create the source archive from the exact clean release tag:

```bash
git archive \
    --format=tar.gz \
    --prefix=proton-vpn-kde-0.11.2/ \
    --output="${HOME}/rpmbuild/SOURCES/proton-vpn-kde-0.11.2.tar.gz" \
    v0.11.2
```

Build with the direct Plasma status-notifier integration:

```bash
rpmbuild -ba packaging/fedora/proton-vpn-kde.spec
```

For a development machine without `kf6-kstatusnotifieritem-devel`, the Qt
system-tray fallback can be packaged explicitly:

```bash
rpmbuild -ba --without kstatusnotifier packaging/fedora/proton-vpn-kde.spec
```

The fallback remains a Qt/Plasma application and does not introduce GTK or
GNOME dependencies. Fedora package builds must set the libexec directory
explicitly through the spec; otherwise CMake may choose a layout that does not
match the installed D-Bus and systemd launchers.

The spec enables the full CTest suite in `%check` and disables direct Proton
support-report and crash-report submission. A package is not releasable when
`%check` is skipped or fails.

The dedicated `RPM Package` CI workflow performs the same source and binary RPM
build for every pushed commit and pull request. It first builds and tests the
provider-neutral keyring RPM from the pinned Proton source, then builds the
client, validates both packages, and retains both source and binary artifacts
for review. Proton VPN API Core is intentionally a runtime rather than build
dependency of the client: the isolated client test suite does not import or
modify the installed Core, while the finished package cannot be installed
without compatible official Core and keyring packages.

The keyring rebuild has its own manifest, patch hashes, `%check`, and
instructions in [keyring-overlay](keyring-overlay/README.md). It is a separate
RPM because the patched files remain Proton-owned code and should remain
independently reviewable and replaceable by an upstream release.

## Installed integration

The package installs:

- the Control Center, resident agent, and isolated Python launcher;
- systemd user units and matching D-Bus activation services;
- the KRunner plugin and Plasma System Settings module;
- notification metadata, translations, and color/light/dark SVG marks; and
- public documentation, licenses, and third-party notices.

The backend is an unprivileged on-demand user service. Its absolute launcher,
`NoNewPrivileges`, and interpreter/loader/plugin environment cleanup are part
of the installed trust boundary. Do not add mount-namespace hardening without
retesting procfs-based peer verification under Fedora SELinux; the rationale is
documented in [Backend service hardening](../../docs/HARDENING.md).

The installed services use the system Python so they resolve Fedora's packaged
Proton modules rather than a user virtual environment. Normal RPM installation
must leave installed payloads root-owned with standard SELinux labels; no
setuid component or custom SELinux policy is expected.

## Plasma runtime notes

- The KRunner module is installed under the KF6 plugin path. Restart KRunner
  after an upgrade if the new plugin is not discovered immediately.
- The System Settings module appears in the Network category and stores only
  Plasma integration preferences.
- `KGlobalAccel` actions are unbound by default. Plasma owns user assignments
  and conflict handling.
- The package uses KService for split-tunneling application discovery rather
  than loading Gio or parsing desktop files itself.
- The resident agent can remain active while the disconnected Python backend
  exits. An active tunnel or packet capture keeps the backend alive.

The official GTK package may remain installed during migration, but users
should not run both frontends concurrently against the same Proton session.
Competing refreshers, reconnection services, or connection operations are not
a supported configuration.

## Package verification

In addition to `%check`, inspect the built RPM for generated dependencies,
file ownership and modes, systemd and D-Bus paths, feature gates, and native
binary hardening. Install it into a clean Fedora Plasma environment and repeat
the live checklist in the [release procedure](../../docs/RELEASING.md).
