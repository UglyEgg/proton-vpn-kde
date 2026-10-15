# Compatibility

## Supported release baseline

Plasma VPN 0.14.3 is the current public package release. Fedora Core 5.8.3
passed exact reconstruction, overlay policy, reproducibility, installation,
backend-replacement, capability-detection, and live connection acceptance.
Ubuntu retains its package-validated 5.6.10 baseline and remains
package-validated rather than live-supported until community Plasma field
reports establish its live lifecycle.

The 0.14.3 maintenance release uses the overlay revisions below.
The installed Fedora overlays passed fresh-backend authentication restoration
and connection on 2026-10-15. Pre-final Ubuntu binary/source packages pass
artifact, dependency, install/reinstall, and client-removal checks in an offline
tooling container. Exact final builds from a signed commit and clean CI remain
publication gates.

| Component | Fedora 44 | Ubuntu 26.04 package-validated |
| --- | --- | --- |
| Architecture | x86_64 | amd64 |
| Desktop | KDE Plasma 6 with systemd user services | KDE Plasma 6 with systemd user services |
| Qt / KDE | Qt 6.8+; KDE Frameworks 6 | Qt 6.10.2; KDE Frameworks 6.24 |
| Python | 3.14 with `os.pidfd_open` | 3.14 with `os.pidfd_open` |
| Proton VPN API Core | 5.8.3-2.plasmavpn1 | 5.6.10-12plasmavpn1 |
| Proton keyring adapter | 0.2.3-10.plasmavpn1 | 0.2.3-10plasmavpn1 |
| Secret Service | Freedesktop Secret Service; KeePassXC verified | Freedesktop Secret Service; live provider UAT pending |
| Package evidence | 0.14.3 source build and 47 checks pass; recovery overlay RPM/SRPM sets verified and installed; exact-commit client RPM pending | Pre-final client, keyring, and Core binary/source sets pass offline build, artifact policy, Lintian error gate, and install/reinstall/removal checks; clean CI pending |

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

The 0.14.3 client also requires keyring revision 10 on both distributions and
Core `5.8.3-2.plasmavpn1` on Fedora. These package floors ensure a client-only
upgrade installs the recovery fixes; Ubuntu's Core floor remains 5.6.10.

## API-Core overlay

The current overlay reconstructs Proton's signed Fedora
`python3-proton-vpn-api-core-5.8.3-1.fc44` package as
`5.8.3-2.plasmavpn1.fc44`. Manifest schema 3 distinguishes the signed Fedora
package version from Proton's latest public source reference, `v5.6.20` at
commit `3a7c1946623796540884574853492d06870d9477`. Proton did not publish a
public `v5.8.3` source tag at the verification date.

The four patches apply with zero fuzz. Exact-tree policy permits changes only
to six Python source files and twelve derived bytecode files. The overlay:

- shares repeated server strings without changing server behavior;
- removes a deprecated FIDO2 capability query;
- explicitly activates reusable validated protection profiles; and
- suppresses the initial empty server-route monitor update that can race
  recovery after a long outage.

The package also consumes Proton's upstream Protun transient-key behavior in
the existing unsaved NetworkManager profile.

The 5.8.3 rebase preserves Proton's permanent firewall kill-switch unit and
safe final-removal script. Verification includes 14 protection-activation
cases, the initial route-monitor regression, seven hash-checked actual-Core
lifecycle cases, exact changed-path policy, and reproducible RPM/SRPM checks.
Revision 2 and keyring revision 10 were installed on 2026-10-15. A fresh backend
restored authentication and connected to US-IL#788; protection activation,
physical server-route installation, and the tunnel handshake completed without
the prior five-second timeout. No provider-identity or backend error followed.
This validates recovery from the observed failed state; another hours-long
outage and a live provider-restart exercise have not been repeated.

Core 5.7 introduced connection-outcome telemetry and defaults its persisted setting
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
networking. Current Fedora artifact and installed overlay claims use 5.8.3;
Ubuntu retains its 5.6.10 baseline. None use 5.5.6 as a runtime.

### Ubuntu reconstruction

The Debian source package pins Proton's signed Ubuntu
`python3-proton-vpn-api-core_5.6.10_amd64.deb` by SHA-256. Proton's public
5.6.10 tag does not contain the complete generated Protun build inputs, so the
source package carries the vendor binary as a declared upstream component. The
rebuild preserves Proton's compiled payload and maintainer-script behavior,
retains its five-patch baseline, and permits changes only to six manifested
Python sources under `/usr/lib/python3/dist-packages`.

The Ubuntu package set contains three binary packages and their corresponding
`.dsc`, original source archive, Debian delta, build information, and changes
file. CI validates package metadata, root ownership, file modes, disabled
reporting features, exact overlay deltas, installation, reinstallation,
autopkgtest, and the client-removal boundary.

## Keyring overlay

The release keyring package reconstructs Proton's 0.2.3 source with four
manifested patches:

- provider-neutral handling for absent or stale `default` collection aliases;
- reuse of one bounded Secret Service connection for a logical operation;
- same-user provider selection with unique-owner pinning; and
- one complete operation retry after a same-user provider restart.

It supports an already-running provider without a D-Bus activation file and
rejects an owner replacement for the current call before selecting a new
same-user owner. The implementation contains no KeePassXC-specific branch. Its
focused suite covers aliases, activation, locked collections, connection
reuse, same-user selection, replacement, restart recovery, and
read/write/delete behavior.

## Authentication limitations

Core 5.8.3 exposes cancellation for FIDO2 assertion work but not for multi-key
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
| Core 5.8.3 overlay, revision 2 | Signed vendor input, four patches, 18 changed paths, 14 protection cases, route-monitor regression, lifecycle cases, RPM/SRPM policy, and installed behavior verified; fresh connection passed on 2026-10-15 |
| Keyring 0.2.3, revision 10 | 32 focused tests and RPM/SRPM policy passed; installed saved-session restoration passed; live provider-restart UAT remains pending |
| Published 0.14.2 package evidence | Client and both overlay package sets passed policy, transaction, and reproducibility checks |
| Ubuntu 0.14.3 pre-final validation | 46 client archive checks, 464 backend cases (seven explicit skips), 43 keyring cases, exact Core payload policy, binary/source artifact checks, Lintian error gate, and offline install/reinstall/client-removal boundaries pass; community Plasma field acceptance pending |

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
