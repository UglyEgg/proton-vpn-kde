# Compatibility

## Supported baseline

The first public alpha targets Fedora 44 with KDE Plasma 6, systemd user
services, NetworkManager, and a session Freedesktop Secret Service provider.

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
requires the Protun-secret capability supplied by this repository's exact
5.6.10 overlay. The adapter separately retains a static public-API floor check
against historical Core 5.5.6. That older package is extracted and parsed but
never imported or executed, and no behavioral fix is accepted from it.

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
under test. The overlay verifier imports the pinned 5.6.10 payload and exercises
its queued-target state machine: the newest Up replaces an older queued target,
Down while Disconnecting retains it, and the old tunnel's late Disconnected
event promotes it. This is a provider-semantics oracle, not a combined
adapter/provider conformance test. The 2026-09-07
[error-class review](SECURITY-AUDIT-2026-08-30.md#current-0130-error-class-review)
found an intermediate state missing from the adapter's fake-driven regression.
The working-tree refactor adds an opt-in combined adapter/Core conformance
harness for the unmodified, SHA-256-checked 5.6.10 connector, state, scheduler
and refresher callback-forwarding modules:

```sh
PYTHONPATH=backend:backend/tests \
PLASMA_VPN_TEST_CORE_SITE_PACKAGES=/usr/lib64/python3.14/site-packages \
python3 -m unittest -v test_core_lifecycle_conformance
```

It constructs neither the live API nor NetworkManager, and substitutes all
external I/O. It checks paused teardown, queued promotion with stale connection
identity, preservation of established tunnels, and authentication/non-authentication
failures dispatched by the actual scheduler. Its five cases skip unless
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

Proton API Core 5.6.10 exposes a cancellation event for FIDO2 assertions but
does not apply it while choosing among multiple attached keys. The Plasma
client therefore does not advertise FIDO2 on that version. Authenticator and
recovery codes remain available. A future Core must explicitly guarantee
cancellable multi-key selection before the security-key action is enabled.

## Current local candidate — acceptance pending

On 2026-09-08, client `0.13.0-0.1.fc44` from `9f26ba2` and its paired
keyring/API-Core packages were installed locally and passed root-side payload
verification. The resident agent restarted successfully. This is not a new
live compatibility baseline: backend authentication, Secret Service restoration,
connections and suspend recovery still require maintainer UAT. The exact
package versions, build evidence and remaining gates are in the
[package checkpoint](SECURITY-AUDIT-2026-08-30.md#package-and-local-install-checkpoint--2026-09-08).

The preceding `0.13.0-0.2` presentation candidate from `620a87c` was
installed with maintainer approval and passed root-side payload verification.
It fixes route/form layout and theme icon-name fallback without changing that
Core/keyring stack. All three client services remained stopped after the
upgrade. Its [visual checkpoint](SECURITY-AUDIT-2026-08-30.md#visual-uat-corrections--2026-09-08)
keeps package verification separate from pending live visual acceptance.

The follow-up `0.13.0-0.3` layout candidate from `58b3d83` passes local
client RPM/SRPM validation and is now installed with maintainer approval.
Root-side payload verification passes, and all three client services remain
stopped. Installed visual acceptance is still pending. Its window size is
app-controlled and limited to the active monitor's work area; long
pages scroll rather than relying on manual resizing or maximizing. This
presentation change does not raise the Qt/KDE or Proton runtime requirements.

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
