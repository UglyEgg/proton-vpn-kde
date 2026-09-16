# Architecture

## Boundaries

1. Proton Core owns VPN protocols, NetworkManager, routing, DNS, kill switch,
   IPv6 leak protection, split tunneling, server scoring, VPN credentials, and
   persisted Proton sessions.
2. Community code owns the Plasma interface, validation, D-Bus policy,
   lifecycle coordination, and the adapter around Core's public API.
3. Authentication plaintext is excluded from D-Bus arguments, snapshots,
   notifications, and logs.
4. Closing the Control Center does not disconnect an active tunnel.
5. The disconnected resident path does not load QML, Proton Core, or the
   server model.
6. Local authorization targets ordinary and sandboxed session peers, not
   arbitrary native code already executing as the desktop user.

The distribution API-Core overlays are declared downstream builds, not
unmodified Proton binaries. Fedora revision `5.6.20-3.plasmavpn1.fc44` and the
Ubuntu package `5.6.10-12plasmavpn1` carry the same five manifested patches,
including Protun secret ownership and explicit activation of validated
protection profiles. Core retains ownership of protection rules and connection
state. See the [Fedora](../packaging/fedora/api-core-overlay/README.md) and
[Debian](../packaging/debian/api-core-overlay/README.md) overlay policies.

## Process model

```text
proton-vpn-kde-agent                  resident C++/Qt/KF6
  tray · shortcuts · notifications
                 │ observation and transient action lease
proton-vpn-kde                        on-demand C++/Qt/Kirigami
  Control Center · Inspector · settings
                 │ authenticated session D-Bus
proton-vpn-kde-backend                unprivileged Python/asyncio
  validation · state · lifecycle · Core adapter
                 │ public Python API
python3-proton-vpn-api-core           Proton plus declared distribution overlay
  VPN protocols · NetworkManager · protection · sessions
```

The privileged Proton split-tunneling daemon is unchanged. KRunner is not a
backend client; it sends bounded requests to the Control Center for explicit
confirmation.

| Concern | Owner |
| --- | --- |
| Control Center, agent, KRunner, KCM, notifications | Community C++/Qt/KF6 |
| Validation, public errors, lifecycle, reconnection | Community Python adapter |
| Account authentication and session persistence | Proton SSO/Core and Secret Service |
| Server construction, access checks, fastest scoring | Proton Core |
| Protocols, profiles, routes, DNS, protection | Proton Core and Proton services |
| UI preferences and pinned targets | KConfig |
| VPN, DNS, and split-tunnel settings | Proton Core settings objects |

`ProtonCoreAdapter` is the backend facade. Focused modules implement
compatibility, protocol discovery, server projection, snapshots, support, and
capture. `VpnController` is the single QML-facing native type; its actions,
locations, settings, lifecycle, and snapshots are separate implementation
units. QML pages own navigation and visual lifetime.

## D-Bus contract

The backend exports:

- name `quest.entropy.PlasmaVPN.Backend`;
- path `/quest/entropy/PlasmaVPN/Backend`; and
- interface `quest.entropy.PlasmaVPN.Backend1`.

The XML under `data/dbus/` is authoritative. Native and Python constants,
method classifications, signals, and errors are generated from it. CI rejects
generated drift and compares the live Python signatures with the XML.

Schema-1 operations cover snapshots, browsing, connection control, settings,
authentication, account state, NPS, packet capture, authorization, and
lifetime leases. Structured payloads are field-allowlisted, type/range checked,
and size bounded. Incompatible changes require a new interface version.

The backend captures the actual message sender before dispatch. Protected
methods require the current packaged client identity and recheck authorization
before the operation body runs. Native clients independently verify and pin the
backend's unique owner before calls or subscriptions. Owner loss revokes
authorization, leases, and pending secret keys. Replies and signals from an
obsolete owner generation are discarded.

All packaged processes are activated through dedicated systemd user services.
Root-owned executable paths are fixed at build time. Their services, launchers,
and native entry points apply the same generated denylist for dynamic-loader,
OpenSSL-provider, GIO/GI, Python, Qt-plugin, and QML search overrides. A direct
native launch re-executes `/proc/self/exe` before Qt initialization when cleanup
was required. Failure exits before application startup.

Discovery, activation, and identity verification are asynchronous. Individual
discovery RPCs and the complete identity transaction have five-second bounds.
Late callbacks are context- and generation-owned.

## Request ownership and evidence

Every asynchronous request carries the minimum identities needed for its
scope: backend owner, account session, foreground owner, operation, connection
intent, or capture generation. A completion may mutate current state only while
all applicable identities remain current.

Observation, retirement, and acknowledgement are distinct:

- a snapshot describes current state;
- idle state may release an owned wait;
- only the current request's normal reply acknowledges that request;
- timeout means completion unknown, not failure or success; and
- state matching a requested target does not prove which mutation produced it.

| Operation | Completion rule |
| --- | --- |
| Connect/Disconnect | Reply acknowledges acceptance; state tracks tunnel outcome; timeout requires a fresh post-timeout read and explicit unconfirmed guidance |
| Settings/DNS/split tunnel | Reply acknowledges the write; serialized readback refreshes values but cannot synthesize write success |
| Capture Start | Active state does not erase an unconfirmed Start; Stop and shutdown retain cleanup ownership |
| Capture Stop | Confirmed inactive state may satisfy the cleanup postcondition |
| Agent lease/quit | Current authorized ready/idle state answers lifetime or absence requirements, not historical mutation success |
| Auth, NPS, support, package switching | The operation's own provider result, authorized reply, or command exit is authoritative |

Settings families use one write generation and typed state. Ambiguous writes
block later writes until reconciliation. Reads and writes share Core's single
settings object and completion-order lock. Successful DNS or split-tunnel
mutation remains acknowledged if a secondary scalar refresh fails.

Browsing and settings reads share eight backend admission slots. Cancelled
provider reads retain their slot until their child exits. Native search keeps
one request in flight and only the newest queued query.

## Backend lifecycle

The backend requests its well-known name without queueing; only the primary
owner initializes Core. The Control Center holds a lease while open. The agent
normally observes without a lease and acquires one only for an explicit action.
Owner-loss events release vanished clients without polling.

With no lease, the backend exits after a short grace period only when Core is
disconnected and idle. Active tunnels, operations, and capture recovery keep it
alive. Ordinary initialization failure is published once and held for explicit
retry; durable cleanup failure exits nonzero for supervised retry.

Shutdown closes admission and drains accepted work under one absolute deadline.
It drops D-Bus, closes the event loop, and joins service-created non-daemon
threads. Unretired provider work produces a nonzero terminal exit so an old,
nameless process cannot mutate shared state beside its replacement. The systemd
unit provides a longer outer stop bound.

Core session prewarm and connector construction occur before public readiness.
When capture recovery is pending, unanswered Secret Service or connector waits
fail startup within a bound while retaining the recovery record. Clients receive
one authoritative initial snapshot after authentication state, connector,
refreshers, and recovery are initialized.

If the backend owner disappears, an open client performs bounded reactivation,
identity verification, and lease restoration. Explicit identity rejection is
terminal and is not retried.

## Authentication and account lifecycle

The adapter uses Proton's public login, TOTP, recovery-code, FIDO2, session,
and logout APIs. Authentication operations share one reentrant transition
boundary. Account-scoped work captures an authentication epoch before entering
Core and rechecks it afterward.

Once Core refreshers have run, replacement credentials require a fresh backend
process. Sign-out writes a private non-secret handoff, quiesces reconnection,
disconnects, and asks SSO to remove the session. Replacement startup verifies
the outgoing process through pidfd and start time, clears any restored outgoing
session, then admits login. Missing retirement evidence fails closed.

Logout restores the prior Core kill-switch setting if a later step fails.
Session expiry retires account-scoped work without disconnecting an established
tunnel automatically. NPS side effects are session-fenced and do not acquire
the VPN-operation lock; cancellation joins any executor mutation before
teardown.

FIDO2 is exposed only when Core guarantees cancellation across device
selection, assertion, and PIN work. Core 5.6.20 does not meet that complete
contract, so authenticator and recovery codes remain available but the unsafe
security-key route is not advertised.

Authentication payload details are in [Authentication](AUTHENTICATION.md).

## Connection, browsing, and recovery

Country, location, and server requests are serialized at the frontend and
generation-bound. One bounded retry covers Core's topology-replacement window;
a replacement target supersedes an older retry. Global search uses an immutable
scalar projection per topology generation and resolves mutable load,
maintenance, and availability through current Core objects.

Capability filters combine P2P, Streaming, Tor, and Secure Core with AND
semantics. Core applies the feature mask and remains responsible for final
fastest-server scoring.

Manual connections and automatic recovery share one connection-intent owner.
Supersession, Disconnect, logout, session expiry, disabled recovery, or adapter
close cancel and join older owners before proceeding. Because Core may continue
executor-backed NetworkManager work after outer-task cancellation, the adapter
shields and joins Core's call and compensates with public Down when required.
Teardown crosses Core's public event barrier and verifies connection identity;
observed `Disconnected` alone is not a universal teardown receipt.

Background Core refresh errors are reduced to session-tagged failure kinds.
Authentication failure uses session-expiry handling; ordinary refresh failure
preserves the tunnel and publishes a persistent degraded-services state. Raw
provider errors do not cross the public boundary.

## Settings and diagnostics

Settings use Core's public objects and save/apply paths. The client enforces
Core constraints for account access and connected state. DNS and split-tunnel
conflicts require explicit user choice.

The Connection Inspector is an on-demand QML page backed by existing bounded
state. It has no timer, traffic collector, history, telemetry, or networking
authority. Closing it destroys the page. Direct Proton support and crash-report
submission are independently disabled in the build, native controller, backend,
and package policy.

The local setup view uses existing backend/Core state, fixed read-only package
queries, and session-bus `ListNames`/`ListActivatableNames`; it never invokes
or activates `org.freedesktop.secrets`. Package capabilities confirm installed
metadata, not that a provider is unlocked or that a tunnel will connect.
The community report formats only allowlisted version, availability, state,
and error-code facts. It reads no logs or addresses, performs no network call,
and copies the displayed preview only after an explicit user action.

Snapshot contract v2 carries addresses from the active Core `Connected` event's
local-agent connection details. `server_ipv4` and `server_ipv6` are displayed as
the reported VPN exit addresses; `device_ip` is labeled as a device observation
at connection time. Neither value is independently re-probed, and the device
address does not attest the current route of every split-tunnel bypass app.
Missing or malformed values remain explicitly unavailable. The fields clear
outside `Connected`; the address-bearing snapshot is visible to processes on
the user's session bus, so it must not be logged or added to crash reports.

Packet capture uses the active official protocol, requires Core's positive byte
cap, and is supervised by a 15-minute generation-bound watchdog. Start failure
or ambiguity compensates with Stop. A mode-restricted atomic recovery record
preserves the original deadline across backend replacement. The client does not
inspect, upload, rename, or rewrite capture output.

The IPv6 preference controls tunneling of supported IPv6 traffic. It does not
disable Core's connection-scoped IPv6 leak protection; NetworkManager may show
`pvpn-killswitch-ipv6` while the general kill-switch preference is Off.

## Plasma integration

The resident agent owns the status notifier, notifications, shortcuts, pinned
targets, and auto-connect. The Control Center is single-instance and on demand.
Tray, shortcut, and KRunner mutations pass through validated confirmation in the
Control Center. Disconnect-and-quit waits for confirmed idle/disconnected state;
plain window close preserves the tunnel.

KConfig change notifications synchronize the KCM, agent, and Control Center.
System Settings owns only desktop preferences. Login launch is opt-in and writes
a marked KDE autostart entry without shell use. Existing unmarked files and
symlinks are not overwritten. Installation and viewing Settings never enable
autostart.

## Safety invariants

- Automated and visual tests default to a non-networking demo backend.
- Mutations are serialized or explicitly preemptible by risk-reducing cleanup.
- Signed-out users can disable permanent kill switch only through the dedicated
  login-recovery operation.
- Shared desktop brokers are not trusted backend clients.
- The GUI never mutates NetworkManager directly.
- Optional memory optimizations never gate VPN or account behavior.
