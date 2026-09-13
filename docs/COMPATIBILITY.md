# Compatibility

## Supported release baseline

Plasma VPN 0.13.0 supports the following tested stack:

| Component | Supported baseline |
| --- | --- |
| Distribution | Fedora 44 x86_64 |
| Desktop | KDE Plasma 6 with systemd user services |
| Qt / KDE | Qt 6.8 or newer; KDE Frameworks 6 |
| Python | 3.11 or newer with `os.pidfd_open` |
| Proton VPN API Core | 5.6.10 API floor; release overlay 5.6.20-3.plasmavpn1 |
| Proton keyring adapter | Release overlay 0.2.3-9.plasmavpn1 |
| Secret Service | Freedesktop Secret Service; KeePassXC verified |
| Network control | NetworkManager through Proton Core |

Required source dependencies include C++20, CMake 3.24, OpenSSL 3,
`cryptography` 50.0.0, and `dbus-fast` 2.20. The Fedora install prefix is
`/usr`; custom-prefix runtime layouts are not supported.

The client RPM requires both explicit downstream capabilities:

```text
proton-vpn-api-core-plasma-protun-secret >= 1
proton-keyring-secret-service-owner-pinned >= 1
```

Those requirements prevent a stock Proton package upgrade from silently
removing behavior required by the Plasma client.

## API-Core overlay

The release overlay reconstructs Proton's signed Fedora
`python3-proton-vpn-api-core-5.6.20-1.fc44` package as
`5.6.20-3.plasmavpn1.fc44`. Manifest schema 2 distinguishes the signed Fedora
package version from Proton's latest public source reference, `v5.6.10` at
commit `f1d13b71c506bbd5f47351a9e4392572e21d0169`. Proton did not publish a
public `v5.6.20` source tag at the verification date.

The five patches apply with zero fuzz. Exact-tree policy permits changes only
to six Python source files and twelve derived bytecode files. The overlay:

- shares repeated server strings without changing server behavior;
- removes a deprecated FIDO2 capability query;
- keeps Protun's transient key in Core's existing unsaved NetworkManager
  profile;
- preserves queued connection targets during reconnect; and
- explicitly activates reusable validated protection profiles.

Release revision 3 has the same runtime source and bytecode hashes as installed
revision 2; it corrects provenance and source-package metadata. Verification
includes 14 protection-activation cases, seven hash-checked actual-Core
lifecycle cases, the complete backend suite, exact changed-path policy, and
two-build RPM/SRPM reproducibility.

The 5.5.6 compatibility fixture is static public-API lint only. It extracts a
SHA-256-pinned RPM but never imports Core, reads credentials, or touches
networking. Behavioral claims use 5.6.20 or installed UAT, not 5.5.6.

## Keyring overlay

The release keyring package reconstructs Proton's 0.2.3 source with three
manifested patches:

- provider-neutral handling for absent or stale `default` collection aliases;
- reuse of one bounded Secret Service connection for a logical operation; and
- same-user provider selection with unique-owner pinning.

It supports an already-running provider without a D-Bus activation file and
fails closed on owner replacement. The implementation contains no KeePassXC-
specific branch. Its focused suite covers aliases, activation, locked
collections, connection reuse, same-user selection, replacement, and
read/write/delete behavior.

## Authentication limitations

Core 5.6.20 exposes cancellation for FIDO2 assertion work but not for multi-key
selection. Plasma VPN therefore does not advertise the security-key flow on
that version. Authenticator and recovery codes remain supported. FIDO2 can be
enabled only after Core exposes and passes a complete cancellable-selection
contract.

Account replacement requires Linux pidfds. A Python build without
`os.pidfd_open` receives a blocked-recovery diagnostic rather than assuming
the old backend process is dead.

## Acceptance evidence

| Evidence | Version / result |
| --- | --- |
| Maintainer client UAT | `0.13.0-0.9.fc44`; authentication, browsing, settings, connection, disconnection, tray, and presentation accepted |
| START-01 cold launch | Installed direct KDE launch passed inherited Qt-path normalization and backend authorization |
| START-02 recovery | Installed Core revision 12 reused and activated one retained protection profile without duplicates or backend restarts |
| Core 5.6.20 install | Runtime-equivalent overlay revision 2 installed; revision 3 verified as provenance-only |
| Clean package builds | Client and both overlay package pairs pass policy, transaction, and reproducibility checks |

The release client revision changes package metadata, documentation, screenshots,
and CI policy after the installed `0.9` build; it does not change client runtime
code. Core overlay revision 3 is runtime-identical to installed revision 2.

## Compatibility policy

- A new Core version must pass public-API checks, hash-checked lifecycle
  conformance, overlay policy, backend tests, clean package builds, and live
  disconnected startup before it is listed.
- A new keyring version must pass the complete focused provider suite before it
  can satisfy the owner-pinned capability.
- Connection testing follows successful startup, account restoration, topology,
  and settings validation.
- Missing required Core behavior fails with bounded guidance; the adapter does
  not infer networking semantics from private implementation details.
- Optional memory optimizations never gate VPN behavior.
- Other distributions remain community experiments until their packaging,
  activation, and live lifecycle receive independent acceptance evidence.

Version bounds describe tested compatibility, not a security-support promise
for Proton's services or future packages.
