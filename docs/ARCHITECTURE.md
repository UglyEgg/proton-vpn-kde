# Architecture

## Design boundary

Plasma VPN is a native KDE frontend around Proton's official Linux VPN Core.
Its architecture follows six invariants:

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
6.  Session-bus authorization resists ordinary or sandboxed peers without
    equivalent host-code execution; it does not claim to attest processes
    against arbitrary native code already running as the desktop user.

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
│ Control Center · inspector · settings │
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

Fedora D-Bus activation routes all three packaged processes through dedicated
systemd user services. Their root-owned executable paths are fixed at build
time, and the Control Center, agent, and backend remove the same native-loader
and runtime search overrides before their entry points load application code.
The desktop file and community-owned fallback launches also use configured
absolute paths rather than the inherited desktop executable search order.

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
the actual D-Bus sender before method dispatch and applies packaged executable,
current environment, and unique-owner policy to protected methods. Claims in
arguments never replace the actual sender. Authorization, leases, and one-use
secret keys are revoked on owner loss. Native clients independently apply the
corresponding current-state policy and pin the backend's unique owner before
sending operations or accepting signals. The packaged units and launcher remove
the same generated native-loader and runtime search overrides before backend or
Core imports. These checks are defense-in-depth within the documented same-user
threat boundary, not OS-backed process attestation.

The full authentication design is documented in
[Authentication](AUTHENTICATION.md); deployment identity and systemd tradeoffs
are documented in [Hardening](HARDENING.md).

## Backend lifecycle

The backend is D-Bus activated and requests its well-known name without
queueing. Only the primary owner initializes Proton Core, preventing duplicate
refreshers, connectors, or SSO sessions.

The Control Center holds a lease while open. The resident agent observes
without a lease and acquires one only while an explicit action is starting.
Their public session-bus objects export an explicit method allowlist. The
Control Center has no remote shutdown method; the agent accepts its shutdown
method only from the current packaged Control Center owner after UID,
executable, environment, and owner-continuity checks. This preserves the
background-controls setting without granting lifecycle authority to arbitrary
session peers.
Lease acquisition checks D-Bus ownership once; the existing authenticated
`NameOwnerChanged` stream releases vanished clients without a polling timer.
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

Every asynchronous Control Center and resident-agent request records both the
authenticated backend's unique destination and its local owner generation.
Replies that complete after owner replacement are discarded before they can
change availability, busy state, messages, models, or queued actions. Backend
signals are accepted only from the currently authenticated unique owner. This
extends owner pinning across the complete asynchronous result path rather than
only the method-call destination.

## Authentication and account state

The adapter calls Proton's public API facade for password login, TOTP and
recovery codes, FIDO2, session retrieval, and logout. Proton SSO persists the
session through a separately packaged keyring adapter. That adapter requires
the desktop-selected Secret Service provider to run as the session user, then
pins traffic to its unique owner instead of continuing to address the
replaceable `org.freedesktop.secrets` well-known name. The desktop's initial
provider selection remains an explicit session trust boundary.

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

The Connection Inspector is a dynamically created Control Center page, not a
resident service. It renders bounded, read-only connection, settings, and
runtime state already exposed by the authenticated controller. Opening it uses
the current connection snapshot and lazily loads its settings models; an
explicit refresh coalesces the connection request and reloads all three
Inspector-owned models. Settings replies carry the active account-session
generation, so a response completed after sign-out or account replacement is
discarded instead of repopulating cleared state. Closing the page destroys it.
It has no timer, traffic access, history store, remote telemetry, or networking
authority, and a source gate rejects background-collector types in the page.

The IPv6 setting controls whether supported IPv6 traffic is carried inside the
VPN tunnel. It does not disable Core's separate connection-scoped IPv6 leak
protection. NetworkManager may therefore show Core's `pvpn-killswitch-ipv6`
connection while the general kill-switch setting is Off; Core removes that
temporary protection after disconnecting.

Packet capture remains an operation of the active official protocol. The
adapter requires Core's reviewed byte ceiling and reserves its local capture
generation only after Core accepts the selected destination. A rejected
destination therefore remains inactive and retryable. Cancellation or a
completion-unknown start issues a compensating stop; if Core cannot confirm
that stop, the watchdog is already armed against the original 15-minute
deadline. Every Core stop attempt has its own timeout, so a non-returning reply
cannot indefinitely retain startup or backend shutdown. The adapter does not
inspect, rename, upload, or rewrite PCAP data.

Direct support submission and anonymous crash reporting to Proton are disabled
in community builds through synchronized build, frontend, and backend gates.
The retained support implementation is bounded and inactive unless an approved
distribution deliberately enables it.

## Plasma integration

The resident agent owns the status notifier, notifications, global shortcuts,
pinned targets, and auto-connect behavior. The complete Kirigami Control Center
starts on demand and exits when its window closes. Both are single-instance
processes. Because KGlobalAccel and status-notifier menus are session-bus
brokers rather than authentication principals, their VPN-changing actions open
the Control Center's validated confirmation dialog and cannot call the agent's
authorized controller directly. The combined disconnect-and-quit tray action
uses a guarded local confirmation before invoking its coordinator. Tray
shutdown distinguishes leaving the Core-managed tunnel active from
disconnecting it: the latter waits for a fully disconnected, idle Core snapshot
before the agent exits and keeps supervision alive if confirmation times out.

Drop-recovery retries retain a cancellation generation through every network,
session, and previous-connection readiness await. Disabling recovery or
resetting the session invalidates that generation before another connection
can be dispatched. The resident agent likewise treats the recovery preference
as applied only after the current backend owner acknowledges it; a failed or
stale policy reply cannot release a queued connection action.

KRunner recognizes only explicit VPN prefixes and validated connection targets.
It addresses the Control Center activation service, never the backend. KRunner,
global shortcuts, and tray connection actions share the bounded validator and
modal confirmation before the Control Center's authenticated controller acts.

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
- KRunner and desktop action brokers are not trusted backend clients.
- The GUI never issues direct NetworkManager mutations.
- Optional Core string-sharing optimizations never gate VPN or account
  behavior. The separately verified Fedora Core overlay also changes Protun's
  transient-key ownership inside its existing unsaved NetworkManager profile;
  that Plasma interoperability behavior is version-pinned and tested rather
  than described as representation-only.
