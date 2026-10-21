# Architecture

## Ownership

| Owner | Responsibilities |
| --- | --- |
| Proton Core and its services | Protocols, credentials, NetworkManager, routing, DNS, protection, split tunneling, server construction/scoring, persisted sessions |
| Community adapter | Input validation, D-Bus policy, operation ownership, process lifetime, reconnection scheduling |
| Native Plasma code | Control Center, resident agent, KRunner, KCM, notifications, shortcuts, UI preferences |
| Distribution overlays | Declared, version-pinned Core/keyring changes; independently packaged and replaceable |

The privileged Proton split-tunneling daemon is unchanged. Overlay versions
belong in [Compatibility](COMPATIBILITY.md); patch boundaries and hashes belong
in the package manifests. Modified Core packages are not official binaries.

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

`ProtonCoreAdapter` is the backend facade; focused modules own compatibility,
server projection, settings, snapshots, authentication transport, and capture.
`VpnController` is the QML-facing native facade with separate action, location,
settings, lifecycle, and snapshot implementation units. QML owns page lifetime.

## D-Bus contract

- Name: `quest.entropy.PlasmaVPN.Backend`
- Path: `/quest/entropy/PlasmaVPN/Backend`
- Interface: `quest.entropy.PlasmaVPN.Backend1`

The XML in `data/dbus/` owns signatures and method classifications. Native and
Python constants are generated; CI checks drift and live Python signatures.
The interface remains schema 1; snapshots/settings have independently versioned
payloads. Unknown contracts provide restart guidance, not guessed semantics.

Payloads are field-allowlisted and bounded. Backend discovery, activation, and
identity verification are asynchronous, with five-second RPC/identity bounds.
Unique-owner policy and ingress authorization are specified in
[Hardening](HARDENING.md#d-bus-identity-and-authorization); encrypted descriptors
are specified in [Authentication](AUTHENTICATION.md#secret-transport).

## Request ownership

Requests carry backend, account, foreground, operation, connection-intent, or
capture generations as applicable. Only a current owner may publish a result.

| Operation | Completion evidence |
| --- | --- |
| Connect/Disconnect | Reply acknowledges acceptance; snapshot tracks tunnel outcome; transport timeout requires a fresh read and unconfirmed guidance |
| Settings/DNS/split tunnel | Reply acknowledges the write; readback cannot synthesize acknowledgement; successful writes survive secondary refresh failure |
| Capture Start | Active state cannot erase an unconfirmed Start; Stop/shutdown retain cleanup authority |
| Capture Stop | Confirmed inactive state can satisfy the cleanup postcondition |
| Agent lease/quit | Current authorized state proves readiness/absence, not historical mutation success |
| Auth, NPS, support, package switching | Owned provider result, authorized reply, or command exit |

Settings families use one write generation, typed state, a shared Core settings
object, and completion-order locking. Ambiguous writes block later writes until
reconciliation. Browsing/settings reads share eight backend admission slots;
cancelled provider reads retain their slot until the child retires. Search
allows one request in flight and only the newest queued query.

## Backend lifecycle

Only the primary D-Bus name owner initializes Core; name acquisition never
queues. The Control Center holds a lease while open. The agent observes without
a lease except during an explicit action. Owner loss releases clients without
polling.

Disconnected idle state retires after the production grace period. Active
tunnels, operations, and capture recovery keep the backend alive. Ordinary
initialization failure is published once for explicit retry; durable cleanup
failure exits nonzero for supervised recovery.

Idle retirement waits on lifetime events and one deadline, not a polling loop.
Lease and snapshot changes wake it to recheck eligibility.

Readiness follows saved-session prewarm, connector construction, refreshers,
and recovery initialization. Pending capture recovery bounds unanswered
Secret Service/connector waits without discarding its recovery record.
An open frontend may reactivate a lost backend, reverify identity, and restore
its lease; identity rejection is terminal.

Shutdown closes admission, drains owned work, drops D-Bus, closes the event
loop, and joins service-created non-daemon threads under one absolute deadline.
Unconfirmed retirement exits nonzero; the user unit supplies the outer bound.

## Authentication and account lifecycle

Login, second factor, FIDO2, cancellation, logout, expiry, and shutdown share a
reentrant transition owner. Account work captures an authentication epoch before
entering Core and rechecks it afterward. Saved-session restoration and connector
readiness are independent: networking failure does not erase a valid sign-in.

After Core refreshers start, replacement credentials require a fresh backend.
Sign-out writes a private non-secret handoff, quiesces reconnects, disconnects,
and removes the SSO session. Replacement startup verifies outgoing-process
death with pidfd/start time and clears any restored outgoing session before
admitting login. Missing evidence blocks replacement.

Failed logout restores the prior kill-switch preference. Session expiry retires
account work without automatically disconnecting an established tunnel. NPS
mutations are session-fenced, do not acquire the VPN-operation lock, and join
executor work before teardown.

## Connection, browsing, and recovery

Frontend country/location/server requests are serialized and generation-bound.
One bounded retry covers topology replacement. Search retains immutable scalar
fields per topology generation and resolves mutable load, maintenance, and
availability through current Core objects. Load-only updates do not rebuild it.

Capability filters use AND semantics; Core owns access checks and final ranking.

Unreleased Fastest recovery retains process-local feature and country/group
constraints published by the current serialized dispatch owner, never a queued
or cancelled request. After two automatic retries, network
errors permit up to two alternative logical servers per episode. A newly
ineligible server may be replaced earlier within the same budget. Every attempt
rechecks cached availability, tier, and filters. Ordinary Fastest retains
Core's Tor/Secure Core exclusions; there is no unfiltered fallback.

Budget exhaustion keeps exponential backoff on the last eligible server; no
eligible server means wait. Connected resets the budget. Exact-server
selection, Disconnect, account retirement, and shutdown clear Fastest intent.
Restored connections with unknown intent remain server-pinned. Protocol/backend
selection and protection handling remain Core-owned.

Temporary retry suspension retains episode history and backoff. Unchanged enable
replay does not cancel an accepted Up; genuine policy changes retain their
retirement barrier. Off/On preserves the selection of a retained connection.

Retry eligibility checks the indexed preferred object before enumerating the
catalog. Core groups are constructed from a disposable country-scoped list,
never by sorting the cached full catalog. Exhausted retries validate only the
last target; alternative selection still uses Core's linear filtering/ranking.

Manual and automatic attempts share one connection owner. Supersession and
risk-reducing cleanup cancel/join older work. Executor-backed Core work is
shielded until completion or compensation through public Down. Disconnect
crosses the public event barrier and checks connection identity; observed
Disconnected alone does not prove retirement. Queued reconnection is not
terminal, and early Connected must not cancel its accepted Up caller.

Background authentication failures enter expiry handling. Other refresh
failures preserve the tunnel and publish degraded-services state.

## Settings and observability

Core's public settings API enforces account, protocol, and connected-state
constraints. DNS/split-tunnel conflicts require explicit choice.

The Inspector is an on-demand QML page backed by bounded existing state, with
no timer, traffic collector, or retained history. Closing it destroys the page
after the toolbar transition. Local setup uses existing state, fixed package
queries, and session-bus name lists; it never activates Secret Service.
Installed capability metadata does not prove provider unlock or tunnel readiness.

Snapshot v2 carries local-agent connection-time `server_ipv4`, `server_ipv6`,
and `device_ip` observations. They are not live external-IP probes or proof of
every split-tunnel application's route. Invalid/missing values remain
unavailable; fields clear outside Connected. Privacy/capture/reporting bounds
are specified in [Hardening](HARDENING.md#data-and-reporting).

The IPv6 preference controls tunneled IPv6, not Core's separate connection-scoped
leak protection. NetworkManager may show `pvpn-killswitch-ipv6` while the general
kill-switch setting is Off.

## Plasma integration

The agent owns tray, notifications, shortcuts, pinned targets, and auto-connect.
The Control Center is single-instance and on demand. Closing its window
preserves the tunnel. Tray shutdown distinguishes keep-connected from
disconnect-and-quit; the latter waits for confirmed idle/disconnected state.

Tray, shortcut, and KRunner mutations require validated Control Center
confirmation. KRunner is not a backend authentication principal.

KConfig notifications synchronize the KCM, agent, and Control Center. The KCM
owns desktop preferences only. Login launch is opt-in through a marked KDE
autostart entry; existing unmarked files and symlinks are preserved.
Installation and viewing Settings never enable autostart.
