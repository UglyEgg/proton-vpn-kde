# Architecture

## Design boundary

Plasma VPN is a native KDE frontend around Proton's official Linux VPN Core.
Its architecture follows five invariants:

1.  Proton Core owns VPN protocols, NetworkManager integration, kill switch,
    IPv6 leak protection, split tunneling, server scoring, session persistence,
    and packet-capture writing.
2.  Community code owns presentation, Plasma integration, bounded validation,
    lifecycle coordination, and a versioned adapter around Core's public API.
3.  Plaintext credentials and second factors never appear in D-Bus arguments,
    snapshots, notifications, or logs.
4.  Closing or restarting the Control Center does not implicitly disconnect an
    active tunnel.
5.  The disconnected resident footprint does not include QML, Proton Core, or
    the complete server model.

## Process model

```text
┌───────────────────────────────────────┐
│ proton-vpn-kde-agent                  │
│ resident C++/Qt/KF6 process           │
│ tray · shortcuts · notifications      │
└───────────────────┬───────────────────┘
                    │ observes; temporary lease for actions
┌───────────────────▼───────────────────┐
│ proton-vpn-kde                        │
│ on-demand C++/Qt/Kirigami process     │
│ Control Center · settings · sign-in   │
└───────────────────┬───────────────────┘
                    │ authenticated session D-Bus
┌───────────────────▼───────────────────┐
│ proton-vpn-kde-backend                │
│ unprivileged Python/asyncio service   │
│ bounded adapter · state · lifecycle   │
└───────────────────┬───────────────────┘
                    │ official public Python API
┌───────────────────▼───────────────────┐
│ python3-proton-vpn-api-core           │
│ official Proton package               │
│ protocols · NetworkManager · KS · ST  │
└───────────────────────────────────────┘
```
The official privileged split-tunneling daemon remains unchanged. KRunner is
not shown as a backend client because the shared KRunner process is
deliberately outside the trusted set; it sends bounded requests to the Control
Center and requires confirmation there.

## Responsibility map


|Concern|Owner|
|-|-|
|Control Center, tray, KRunner, KCM, shortcuts, and notifications|Community C++/Qt/KF6 code|
|Input schemas, public error vocabulary, process lifetime, and reconnection scheduling|Community adapter|
|Account authentication and persisted Proton session|Official Proton SSO/Core through Secret Service|
|Server construction, feature flags, access checks, and fastest scoring|Official Proton Core|
|VPN protocols, routes, DNS application, kill switch, IPv6 leak protection, and split tunneling|Official Proton Core and its packaged services|
|User-interface preferences and pinned targets|KConfig|
|VPN settings, custom DNS, and split-tunneling configuration|Official Core settings objects|

The Python `ProtonCoreAdapter` remains the stable facade consumed by the
backend controller. Provider-object translation, compatibility probes,
protocol discovery, snapshot construction, support workflows, and the bounded
packet-capture state machine live in focused modules behind that facade. The
native `VpnController` similarly remains the single QML-facing type while its
actions, location requests, settings, backend lifecycle, and snapshot handling
are compiled as separate implementation units. QML pages own navigation and
lifecycle; reusable dialogs and settings cards receive explicit controller or
model inputs rather than reaching through implicit application state.

## Session D-Bus contract

The adapter exports:

- bus name `quest.entropy.PlasmaVPN.Backend`;
- object path `/quest/entropy/PlasmaVPN/Backend`; and
- interface `quest.entropy.PlasmaVPN.Backend1`.

The installed introspection XML under `data/dbus/` is the authoritative
machine-readable contract for the backend, resident agent, and Control Center.
Native endpoint, method, signal, and error constants and the Python contract and
authorization definitions are generated from those files. Static analysis
rejects stale generated output, and a backend test compares the Python service's
live signatures with Backend1 before a contract change can merge.

The version-one contract groups operations into:

- non-sensitive snapshots and server browsing;
- connection and reconnection control;
- VPN settings, custom DNS, and split-tunneling settings;
- sign-in, second-factor, FIDO2, logout, and the narrow signed-out kill-switch
  recovery action;
- NPS survey state;
- bounded packet-capture lifecycle; and
- client authorization and lifetime leases.

Structured payloads include a schema version. Input JSON is field-allowlisted,
type-checked, range-checked, and bounded before it reaches Core. An
incompatible contract change requires a new D-Bus interface version; additive
version-one changes must preserve existing clients.

Read-only status remains separate from mutation authority. The backend captures
the actual D-Bus sender before method dispatch and authenticates package-owned
Control Center or resident-agent executables for protected methods. Claims in
arguments never replace the actual sender. Authorization, leases, and one-use
secret keys are revoked on owner loss. Native clients independently verify and
pin the packaged backend's unique owner before sending operations or accepting
signals.

The full authentication design is documented in
[Authentication](AUTHENTICATION.md); deployment identity and systemd tradeoffs
are documented in [Hardening](HARDENING.md).

## Backend lifecycle

The backend is D-Bus activated and requests its well-known name without
queueing. Only the primary owner initializes Proton Core, preventing duplicate
refreshers, connectors, or SSO sessions.

The Control Center holds a lease while open. The resident agent observes
without a lease and acquires one only while an explicit action is starting.
With no live lease, the backend exits after a short grace period only when Core
reports a fully disconnected, idle state. Active tunnels and packet captures
keep it alive. Closing the Control Center during an unanswered Secret Service
prompt therefore does not strand an initializing backend indefinitely, while a
real frontend or tray action protects the prompt long enough to complete.

If Core initialization fails, the backend publishes a fixed startup-failure
state, releases D-Bus resources, and exits nonzero. The user service can
recover transient Secret Service, NetworkManager, or Core failures through
`Restart=on-failure` instead of retaining a permanently unready process.

If the backend owner disappears while the Control Center remains open, the
frontend requests bounded D-Bus reactivation and re-establishes its lease. A
client-identity rejection is not retried: it fails closed with restart and
reinstall guidance, which covers an executable left running across an RPM
replacement without turning the backend into a restart loop.

## Authentication and account state

The adapter calls Proton's public API facade for password login, TOTP and
recovery codes, FIDO2, session retrieval, and logout. Proton SSO persists the
session through whichever conforming Freedesktop Secret Service provider owns
`org.freedesktop.secrets`.

The frontend receives only minimum account display metadata. Authentication
fields use a one-use encrypted and sealed descriptor transport, and provider
exceptions are mapped to fixed public errors. Logout disconnects first and
restores the previous Core kill-switch setting if any later step fails.

## Server data and connection selection

Country, location-group, and exact-server reads are serialized at the frontend
boundary. Requests carry generations so replies for obsolete navigation targets
are discarded. A bounded retry covers Core's short topology-replacement window
without turning a genuinely empty group into an infinite refresh loop.

Global search uses an immutable scalar projection per Core topology generation.
It stores normalized display fields but no Proton server objects. Current load,
maintenance state, and account availability are resolved through current Core
objects for matching records. Load-only updates do not rebuild the projection;
topology or localized-name changes invalidate it for lazy reconstruction.

Capability-aware selection accepts bounded combinations of P2P, Streaming, Tor,
and Secure Core with AND semantics. The adapter asks Core to filter by the
combined feature mask and delegates final selection to Core's fastest-server
score. The frontend does not replace Proton's scoring with displayed load.

## Settings and diagnostics

Settings use Core's public settings objects and official save/apply paths.
Protocol and kill-switch changes require a disconnected tunnel. Paid features
respect account access, and custom-DNS or split-tunneling conflicts are shown
to the user rather than resolved by silently changing another setting.

The IPv6 setting controls whether supported IPv6 traffic is carried inside the
VPN tunnel. It does not disable Core's separate connection-scoped IPv6 leak
protection. NetworkManager may therefore show Core's `pvpn-killswitch-ipv6`
connection while the general kill-switch setting is Off; Core removes that
temporary protection after disconnecting.

Packet capture remains an operation of the active official protocol. The
adapter requires Core's reviewed byte ceiling and adds a 15-minute lifecycle
watchdog, but it does not inspect, rename, upload, or rewrite PCAP data.

Direct support submission and anonymous crash reporting to Proton are disabled
in community builds through synchronized build, frontend, and backend gates.
The retained support implementation is bounded and inactive unless an approved
distribution deliberately enables it.

## Plasma integration

The resident agent owns the status notifier, notifications, global shortcuts,
pinned targets, and auto-connect behavior. The complete Kirigami Control Center
starts on demand and exits when its window closes. Both are single-instance
processes. Tray shutdown distinguishes leaving the Core-managed tunnel active
from disconnecting it: the latter waits for a fully disconnected, idle Core
snapshot before the agent exits and keeps supervision alive if confirmation
times out.

KRunner recognizes only explicit VPN prefixes and validated connection targets.
It addresses the Control Center activation service, never the backend. A modal
confirmation is required before the Control Center's authenticated controller
acts.

The System Settings module owns desktop preferences only: startup,
auto-connect, drop recovery, window and tray behavior, notifications, pinned
targets, icon style, and capture storage. Live Proton settings are not
duplicated into a second controller. KConfig change notifications synchronize
the KCM, agent, and Control Center.

## Safety rules

- Demo mode is the default path for automated and visual tests and cannot
  connect NetworkManager or a Proton account.
- Real mutations are serialized, and connection actions are disabled while an
  incompatible operation is active.
- A signed-out client can disable permanent kill switch for login only through
  one dedicated operation; it cannot reach general settings.
- Closing the Control Center never disconnects an active tunnel.
- KRunner and other shared plugin hosts are not trusted backend clients.
- The GUI never issues direct NetworkManager mutations.
- Optional representation-only Core memory optimizations never gate VPN or
  account behavior.
