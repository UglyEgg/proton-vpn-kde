# Compatibility

## Supported release baseline

Plasma VPN 0.14.1 is the current public package release. Fedora targets Proton
API Core 5.7.0, while Ubuntu retains its package-validated 5.6.10 baseline. The
Fedora stack passed installed maintainer UAT on the corrected 0.14.1 package.
Ubuntu 26.04 remains package-validated rather than live-supported until
community Plasma field reports establish its live lifecycle.

| Component | Fedora 44 | Ubuntu 26.04 package-validated |
| --- | --- | --- |
| Architecture | x86_64 | amd64 |
| Desktop | KDE Plasma 6 with systemd user services | KDE Plasma 6 with systemd user services |
| Qt / KDE | Qt 6.8+; KDE Frameworks 6 | Qt 6.10.2; KDE Frameworks 6.24 |
| Python | 3.14 with `os.pidfd_open` | 3.14 with `os.pidfd_open` |
| Proton VPN API Core | 5.7.0-1.plasmavpn1 | 5.6.10-12plasmavpn1 |
| Proton keyring adapter | 0.2.3-9.plasmavpn1 | 0.2.3-9plasmavpn1 |
| Secret Service | Freedesktop Secret Service; KeePassXC verified | Freedesktop Secret Service; live provider UAT pending |
| Package evidence | `0.14.1-0.2.fc44` signed-source build installed and accepted; publication artifacts rebuild from the signed tag | Clean-container build/install/reinstall/autopkgtest |

Required source dependencies include C++20, CMake 3.24, OpenSSL 3, and
`dbus-fast` 2.20. Fedora's tested `cryptography` floor is 50.0.0; Ubuntu 26.04
ships 46.0.5, which passes the complete backend suite. Both packages install
under `/usr`; custom-prefix runtime layouts are not supported.

Both client packages require explicit downstream capabilities:

```text
proton-vpn-api-core-plasma-protun-secret >= 1
proton-keyring-secret-service-owner-pinned >= 1
```

Those requirements prevent a stock Proton package upgrade from silently
removing behavior required by the Plasma client.

## API-Core overlay

The release overlay reconstructs Proton's signed Fedora
`python3-proton-vpn-api-core-5.7.0-1.fc44` package as
`5.7.0-1.plasmavpn1.fc44`. Manifest schema 2 distinguishes the signed Fedora
package version from Proton's latest public source reference, `v5.6.10` at
commit `f1d13b71c506bbd5f47351a9e4392572e21d0169`. Proton did not publish a
public `v5.7.0` source tag at the verification date.

The five patches apply with zero fuzz. Exact-tree policy permits changes only
to six Python source files and twelve derived bytecode files. The overlay:

- shares repeated server strings without changing server behavior;
- removes a deprecated FIDO2 capability query;
- keeps Protun's transient key in Core's existing unsaved NetworkManager
  profile;
- preserves queued connection targets during reconnect; and
- explicitly activates reusable validated protection profiles.

The 5.7.0 rebase preserves Proton's permanent firewall kill-switch unit and
safe final-removal script. Verification includes 14 protection-activation
cases, seven hash-checked actual-Core lifecycle cases, exact changed-path
policy, RPM/SRPM checks, installed startup, and live connection acceptance.

Core 5.7 adds connection-outcome telemetry and defaults its persisted setting
to enabled. Community client builds default this optional reporting capability
off, disable Core's live event queue immediately after every settings load,
discard any events already queued before opt-out, and persist the preference as
off on the next explicit settings write. Pure reads do not rewrite the settings
file. Missing queue controls fail closed. The policy is visible in Settings and
copied community diagnostics. A telemetry-capable build exposes the Core
preference as a user switch; fresh and legacy settings profiles remain off
until the user explicitly opts in, while an explicit persisted preference is
respected.
Required Proton service traffic is not disabled.

The 5.5.6 compatibility fixture is static public-API lint only. It extracts a
SHA-256-pinned RPM but never imports Core, reads credentials, or touches
networking. Behavioral claims use 5.7.0, the retained Ubuntu 5.6.10 baseline,
or installed UAT, not 5.5.6.

### Ubuntu reconstruction

The Debian source package pins Proton's signed Ubuntu
`python3-proton-vpn-api-core_5.6.10_amd64.deb` by SHA-256. Proton's public
5.6.10 tag does not contain the complete generated Protun build inputs, so the
source package carries the vendor binary as a declared upstream component. The
rebuild preserves Proton's compiled payload and maintainer-script behavior,
applies the same five patches, and permits changes only to six manifested
Python sources under `/usr/lib/python3/dist-packages`.

The Ubuntu package set contains three binary packages and their corresponding
`.dsc`, original source archive, Debian delta, build information, and changes
file. CI validates package metadata, root ownership, file modes, disabled
reporting features, exact overlay deltas, installation, reinstallation,
autopkgtest, and the client-removal boundary.

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

Core 5.7.0 exposes cancellation for FIDO2 assertion work but not for multi-key
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
| Maintainer client UAT | `0.14.1-0.2.fc44`; Core `5.7.0-1.plasmavpn1.fc44`; keyring `0.2.3-9.plasmavpn1.fc44`; upgrade, authentication restoration, browsing, settings, local setup, diagnostics, connection, disconnection, reconnect, tray reopening, telemetry-off presentation, and recovery accepted after final corrections |
| START-01 cold launch | Installed direct KDE launch passed inherited Qt-path normalization and backend authorization |
| START-02 recovery | Installed Core revision 12 reused and activated one retained protection profile without duplicates or backend restarts |
| Core 5.7.0 overlay | Signed vendor input verified; all five patches, 14 protection cases, seven lifecycle cases, RPM/SRPM policy, installation, startup, and live connection passed |
| Clean package builds | Client and both overlay package pairs pass policy, transaction, and reproducibility checks |
| Ubuntu 26.04 package validation | Client and both overlay `.deb`/source sets pass clean-container policy and lifecycle checks; community Plasma field acceptance pending |

The corrected telemetry policy, versioned settings and snapshot compatibility,
and readiness paths are included in the focused installed acceptance above.

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
- A distribution is live-supported only after package, activation, and live
  lifecycle acceptance. Ubuntu remains package-validated pending field reports.

Version bounds describe tested compatibility, not a security-support promise
for Proton's services or future packages.
