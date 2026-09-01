# Compatibility

## Supported baseline

The first public alpha targets Fedora 44 with KDE Plasma 6, systemd user
services, NetworkManager, and a session Freedesktop Secret Service provider.

The source build requires:

- C++20;
- CMake 3.24 or newer;
- Qt 6.8 or newer;
- KDE Frameworks 6;
- Python 3.11 or newer;
- OpenSSL 3;
- `cryptography` 45.0.1 or newer;
- `dbus-fast` 2.20 or newer.

The real backend requires Proton's Fedora packages. The minimum declared VPN
API Core version is 5.5.6.

The supported Fedora package installs both Plasma and project executables below
`/usr`. The hardened System Settings launcher is compiled from that package
prefix; non-`/usr` custom-prefix layouts are not currently an accepted runtime
configuration.

CI runs all 210 isolated backend tests under Python 3.11 with the exact minimum
`cryptography` 45.0.1 and `dbus-fast` 2.20.0 wheels. A separate source-level
contract check downloads and extracts Proton's SHA-256-pinned Fedora 44 API
Core 5.5.6 RPM, then verifies every public class, method, property, and exported
type consumed by the adapter. It does not instantiate Core, read credentials,
or touch networking; live acceptance remains a separate release step.

KeePassXC acceptance also depends on the downstream
`python3-proton-keyring-linux` capability identified below. It contains the
narrow provider-neutral fallback for a missing or stale `default` Secret
Service collection alias and reuses one bounded Secret Service connection. The
unreleased overlay revision also requires a same-user provider and pins all
traffic to its unique owner. Those changes were not present in the assessed
upstream 0.2.3 tag.

The repository now carries the exact patches, upstream archive identity,
focused tests, and Fedora rebuild under
[`packaging/fedora/keyring-overlay`](../packaging/fedora/keyring-overlay/).
Release CI produces that package's source and binary RPMs beside the client,
and the unreleased client RPM requires its explicit
`proton-keyring-secret-service-owner-pinned` capability. The overlay
continues to provide the older provider-agnostic capability for compatibility,
but that weaker capability cannot satisfy the owner-pinned client dependency. This
dependency can be retired after an equivalent upstream build is verified; it
is not a claim that stock Proton 0.2.3 supports KeePassXC correctly.

## Last verified installed stack

On 2026-08-31 the accepted `0.12.0` runtime revision `d2e7a74` used the following
stack. The keyring and client packages were installed together while an existing
VPN tunnel remained connected. The resident agent restarted, the backend
selected the already-running KeePassXC Secret Service provider, and both
services remained active with zero restarts or warning-level journal entries.
The Control Center, Connection Inspector, and normal navigation passed
maintainer acceptance. NetworkManager retained the same Proton profile,
`proton0` tunnel, and leak-protection connection throughout the package
transaction.

| Component | Verified version |
| --- | --- |
| Fedora | 44 |
| Proton VPN API Core | 5.6.10-8.plasmavpn1 repository rebuild |
| Proton keyring adapter | 0.2.3-7.plasmavpn1 repository rebuild |
| Proton VPN daemon | 0.13.8 |
| Plasma client | 0.12.0-0.4.fc44 local candidate |

Downstream package release suffixes are not part of the runtime compatibility
contract.

Earlier `0.11.3` package, reconnect, and suspend/resume evidence remains recorded
in the security assessment. It is historical evidence rather than the current
installed compatibility baseline.

## Compatibility policy

- A new Proton Core version must pass demo tests, backend tests, the packaged
  `%check` battery, and disconnected live startup before it is listed here.
- A new keyring adapter must pass alias, activation, locked-collection,
  connection-reuse, same-user selection/owner replacement, KeePassXC
  read/write/delete, and absent-entry tests before it replaces the downstream
  version listed above.
- Connection testing follows only after startup, account, server-list, and
  settings checks succeed.
- The client must fail with bounded guidance when a required public API is
  absent; it must not guess at networking behavior.
- Optional string-sharing optimizations are detected by behavior and never
  gate VPN functionality. The Fedora Core overlay's separate Protun
  secret-ownership patch is a version-pinned Plasma interoperability fix and
  must pass unsaved-profile, disconnect-cleanup, reconnect, and suspend/resume
  acceptance before release.
- Other distributions are community experiments until their packaging and
  lifecycle behavior have independent acceptance evidence.

Every public artifact must repeat the release procedure from its exact clean,
tagged source. Version bounds describe tested compatibility, not a security-
support promise for Proton's service or packages.
