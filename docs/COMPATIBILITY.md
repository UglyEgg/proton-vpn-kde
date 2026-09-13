# Compatibility

## Supported baseline

The current public release is 0.11.3. Version 0.12.0 was an accepted internal
development milestone rather than a tagged release; unreleased 0.13.0 is the
next public candidate. The supported baseline targets Fedora 44 with KDE Plasma
6, systemd user services, NetworkManager, and a session Freedesktop Secret
Service provider.

The source build requires:

- C++20;
- CMake 3.24 or newer;
- Qt 6.8 or newer;
- KDE Frameworks 6;
- Python 3.11 or newer, built with Linux `os.pidfd_open` support for account recovery;
- OpenSSL 3;
- `cryptography` 45.0.1 or newer;
- `dbus-fast` 2.20 or newer.

The Fedora package declares Proton VPN API Core 5.6.10 as its runtime floor and
requires the separately versioned Protun-secret capability. The current
overlay supplies that capability by rebuilding Proton's exact signed Fedora
5.6.20 package; its version is deliberately newer than Proton's 5.6.20-1
package so Fedora can select it during an upgrade. The adapter separately
retains a static public-API floor check against historical Core 5.5.6. That
older package is extracted and parsed but never imported or executed, and no
behavioral fix is accepted from it.

The supported Fedora package installs both Plasma and project executables below
`/usr`. The hardened System Settings launcher is compiled from that package
prefix; non-`/usr` custom-prefix layouts are not currently an accepted runtime
configuration.

CI runs the isolated backend suite under Python 3.11 with the exact minimum
`cryptography` 45.0.1 and `dbus-fast` 2.20.0 wheels. A separate source-level
contract check downloads and extracts Proton's SHA-256-pinned Fedora 44 API
Core 5.5.6 RPM, then verifies every public class, method, property, and exported
type consumed by the adapter. It does not instantiate Core, read credentials,
or touch networking and must not be interpreted as the behavioral runtime
under test. The overlay verifier imports the pinned 5.6.20 payload and exercises
its queued-target state machine: the newest Up replaces an older queued target,
Down while Disconnecting retains it, and the old tunnel's late Disconnected
event promotes it. This is a provider-semantics oracle, not a combined
adapter/provider conformance test. The 2026-09-07
[error-class review](SECURITY-AUDIT-2026-08-30.md#current-0130-error-class-review)
found an intermediate state missing from the adapter's fake-driven regression.
The adapter includes an opt-in combined adapter/Core conformance
harness for the unmodified, SHA-256-checked 5.6.20 connector, state, scheduler
and refresher callback-forwarding modules:

```sh
PYTHONPATH=backend:backend/tests \
PLASMA_VPN_TEST_CORE_SITE_PACKAGES=/usr/lib64/python3.14/site-packages \
python3 -m unittest -v test_core_lifecycle_conformance
```

It constructs neither the live API nor NetworkManager, and substitutes all
external I/O. It checks paused teardown, queued promotion with stale connection
identity, preservation of established tunnels, and authentication/non-authentication
failures dispatched by the actual scheduler. Its seven cases skip unless
the fixture is explicitly selected; they currently supplement local validation
and are not a silently assumed CI pass. A changed provider hash requires
contract review. Core 5.5.6 static lint establishes neither runtime support nor
cancellation/event-order behavior. Installed lifecycle acceptance remains open.
The static public-API check also requires `set_error_callback`; the runtime
implementation does not read or manipulate Core's private scheduler.

Account replacement now depends on the packaged systemd user service, Linux
pidfds and Python's `os.pidfd_open` API: the new backend confirms
outgoing-process death before consuming its
non-secret runtime handoff. Manual overlapping startup is refused. Failed
cleanup retains recovery state and cannot expose a replacement login form.
No Core networking, protocol or session-persistence patch is added for this.
Some standalone Python builds omit that API even when the kernel supports it.
They report a blocked-recovery diagnostic instead of assuming process death.
The local minimum-version Python build exercises that refusal and skips the
real pidfd test; the installed Fedora Python exercises actual process exit.

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

Working-tree revision `0.2.3-9.plasmavpn1.fc44` adds Proton's current
copyright and GPL notice to the new upstream test module, corrects the RPM
license expression to `GPL-3.0-or-later`, and carries the strict-JSON SPDX
annotation into both binary and source packages. All 29 focused tests and the
binary/source content checks pass. This is a provenance-only package revision;
the installed package remains `0.2.3-8.plasmavpn1.fc44`.

Proton API Core 5.6.20 exposes a cancellation event for FIDO2 assertions but
does not apply it while choosing among multiple attached keys. The Plasma
client therefore does not advertise FIDO2 on that version. Authenticator and
recovery codes remain available. A future Core must explicitly guarantee
cancellable multi-key selection before the security-key action is enabled.

## Core 5.6.20 overlay — installed runtime, provenance revision built

The working-tree overlay rebuilds Proton's signed Fedora
`python3-proton-vpn-api-core-5.6.20-1.fc44` package as
`5.6.20-3.plasmavpn1.fc44`. It provides the capability already required by the
installed Plasma client, so it can replace both the older 5.6.10 overlay and
Proton's stock 5.6.20 package without weakening the client's dependency.

Revision `3` removes the incorrect implication that Proton published a public
`v5.6.20` source tag. Manifest schema 2 records `5.6.20` as the signed Fedora
vendor package version, records no corresponding public source tag, and pins
public `v5.6.10` commit `f1d13b71c506bbd5f47351a9e4392572e21d0169`
only as the latest reference verified on 2026-09-12. It changes no runtime
patch or installed Python/bytecode hash from installed revision `2`.

All five patches apply with zero fuzz. Exact tree verification permits only
six Python sources and their twelve derived bytecode files to differ from the
vendor payload. The overlay adopts Proton 5.6.20's current dependency,
conflict, obsolete and package-script contracts instead of carrying those
forward from 5.6.10. Fourteen protection-activation regressions, seven
hash-checked actual-Core lifecycle cases, all 448 backend cases, Mypy for 31
source files, and Ruff pass against the extracted 5.6.20 candidate.

Two builds in distinct clean RPM top directories on the same Fedora 44
workstation produced byte-identical unsigned artifacts:

```text
7967a4323ee2202bc59ad466cf3cf4ee8ccba5b8a6c6f64b3294d943ad001c56  python3-proton-vpn-api-core-5.6.20-3.plasmavpn1.fc44.x86_64.rpm
2ebba1f846ec16d236367a559aa68687d3fa8c04e524dd26371dcd110c756dbb  python3-proton-vpn-api-core-5.6.20-3.plasmavpn1.fc44.src.rpm
```

The workstation has runtime-equivalent revision
`5.6.20-2.plasmavpn1.fc44` installed. Revision `3` has source/package evidence
only and has not been installed; its metadata and source-package changes do not
create a new installed runtime UAT result.

## Current local candidate — maintainer UAT passed, release pending

The latest recorded installation is the maintainer-approved
`0.13.0-0.9.fc44` client from
`f6e12d0f04a729f9d032fbbc2f6aed2b7afa2160`, installed on 2026-09-09. Its
client RPM/SRPM passed two clean builds and exact artifact/source checks;
root-side payload verification and the installed source marker matched.

The working tree declares client RPM revision `0.13.0-0.10.fc44` so the
installed Python-template SPDX additions cannot produce a second package under
the `0.9` identity. This source/package-identity revision also aligns the public
release history and refreshes the application gallery. It has not been built or
installed and carries no additional runtime UAT claim.

| Component | Current installed package (2026-09-12 readback) |
| --- | --- |
| Plasma client | 0.13.0-0.9.fc44 |
| Proton VPN API Core overlay | 5.6.20-2.plasmavpn1.fc44 |
| Proton keyring overlay | 0.2.3-8.plasmavpn1.fc44 |

The maintainer accepted UAT for client `0.9` with Core
`5.6.10-12.plasmavpn1.fc44` on 2026-09-09, confirming expected operation and
presentation after the recovery/disconnect/reconnect checks. The later
5.6.20 revision `2` entry above is installed-package readback, not a claim that
the complete UAT battery was repeated after that upgrade.

The upgrades changed the client and Core, leaving the keyring package unchanged.
The [START-02 installation record](SECURITY-AUDIT-2026-08-30.md#start-02-inactive-leak-protection-device--2026-09-09)
records successful saved-session startup and connection. A retained-profile
recovery test verified the client's stable error presentation and zero automatic
restarts, but exposed Core revision `11` rejecting NetworkManager-normalized
settings. That superseded revision was replaced by Core `12` below.

Core overlay `5.6.10-12.plasmavpn1.fc44`, from signed source `5fa8279`,
corrects that comparison. Its 14 offline regression cases, RPM/SRPM checks and
root-side installed verification pass. Installed cold-start recovery also
passes with a retained protection device whose `GENERAL.AUTOCONNECT` remains
`no`: the original protection profile was reused and explicitly activated,
without duplicate profiles or backend restarts. The maintainer confirmed
recovery without clicking Retry or Connect. A subsequent in-app Disconnect
removed the Proton profiles and test interface. A normal in-app Connect then
created fresh profiles and reconnected, still without a backend restart and
with the unrelated private VPN unchanged. These are dated acceptance checks, not
continuous monitoring or an independent leak test. The client binary is
unchanged by this separate Core-only correction.
The client-side correction remains usable with the older Core overlay, but
automatic recovery from the specific inactive-device defect requires the new
Core patch. Installed acceptance and release review remain separate gates.

The window is app-sized within the active monitor's work area; long pages
scroll instead of relying on manual resizing or maximizing. The shared Startup
section adds opt-in login launch, window/tray presentation and existing
auto-connect choices. Package installation does not enable login launch, and
automatic connection still requires an authenticated session and available
Secret Service. Same-day upgrades invalidate older embedded System Settings
QML through commit-derived resource timestamps. These changes do not raise the
Qt/KDE or Proton runtime requirements.

This UAT-accepted local candidate is not yet a released compatibility baseline.
Outstanding controlled-failure checks, exact-candidate independent review,
final package validation and the planned soak remain separate release gates.

## Last accepted live-UAT stack

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
in the security assessment. It is historical evidence, not acceptance evidence
for the current `0.13.0` candidate.

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
