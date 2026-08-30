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

CI runs all 130 isolated backend tests under Python 3.11 with the exact minimum
`cryptography` 45.0.1 and `dbus-fast` 2.20.0 wheels. A separate source-level
contract check downloads and extracts Proton's SHA-256-pinned Fedora 44 API
Core 5.5.6 RPM, then verifies every public class, method, property, and exported
type consumed by the adapter. It does not instantiate Core, read credentials,
or touch networking; live acceptance remains a separate release step.

KeePassXC acceptance also depends on the downstream
`python3-proton-keyring-linux` capability identified below. It contains the
narrow provider-neutral fallback for a missing or stale `default` Secret
Service collection alias and reuses one bounded Secret Service connection.
Those changes were not present in the assessed upstream 0.2.3 tag.

The repository now carries the exact patches, upstream archive identity,
focused tests, and Fedora rebuild under
[`packaging/fedora/keyring-overlay`](../packaging/fedora/keyring-overlay/).
Release CI produces that package's source and binary RPMs beside the client,
and the client RPM requires its explicit
`proton-keyring-secret-service-provider-agnostic` capability. This dependency
can be retired after an equivalent upstream build is verified; it is not a
claim that stock Proton 0.2.3 supports KeePassXC correctly.

## Last verified installed stack

On 2026-08-30 the source and packaged trust-boundary checks used the following
stack. Live acceptance covered D-Bus and systemd activation, KeePassXC Secret
Service integration, rejection of an unauthorized mutation, confirmation-gated
KRunner actions, and VPN connection and disconnection.

| Component | Verified version |
| --- | --- |
| Fedora | 44 |
| Proton VPN API Core | 5.6.10 |
| Proton keyring adapter | 0.2.3-4.codex1 downstream build; source-equivalent repository rebuild is 0.2.3-4.plasmavpn1 |
| Proton VPN daemon | 0.13.8 |
| Plasma client | 0.11.2 (`0.11.2-20.fc44` release candidate) |

Downstream package release suffixes are not part of the runtime compatibility
contract.

## Compatibility policy

- A new Proton Core version must pass demo tests, backend tests, the packaged
  `%check` battery, and disconnected live startup before it is listed here.
- A new keyring adapter must pass alias, activation, locked-collection,
  connection-reuse, KeePassXC read/write/delete, and absent-entry tests before
  it replaces the downstream version listed above.
- Connection testing follows only after startup, account, server-list, and
  settings checks succeed.
- The client must fail with bounded guidance when a required public API is
  absent; it must not guess at networking behavior.
- Optional memory optimizations are detected by behavior and never gate VPN
  functionality.
- Other distributions are community experiments until their packaging and
  lifecycle behavior have independent acceptance evidence.

The final public artifact must repeat the release procedure from its exact
clean, tagged source. Version bounds describe tested compatibility, not a
security-support promise for Proton's service or packages.
