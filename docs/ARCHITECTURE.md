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

The Fedora Core package includes documented downstream patches; it is not an
unmodified Proton binary. Alongside representation and Protun secret-ownership
fixes, the current verified overlay candidate
`5.6.20-2.plasmavpn1.fc44` explicitly activates and reuses matching protection
profiles after manual device disconnection. It rebases the same bounded
behavior onto Proton's signed 5.6.20 Fedora payload; the last installed UAT
used `5.6.10-12.plasmavpn1.fc44`. Core still owns the protection rules and
connection state machine. The
[overlay scope](../packaging/fedora/api-core-overlay/README.md) separates this
authorized integration correction from the community frontend and records its
tests and upstream status.

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
For direct native launches, both `main` entry points use `NativeStartup` before
`QApplication`: remove that shared denylist, then re-execute `/proc/self/exe`
only when removal was needed. This preserves arguments and PID and replaces
the kernel-visible initial environment checked by backend authorization.
Cleanup/re-execution failure terminates startup; a clean service launch incurs
no extra exec. This does not contain code loaded before the initial `main`;
the [authentication boundary](AUTHENTICATION.md) retains that distinction.

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

Native discovery first reads name ownership and activates only an absent
service. Those RPCs are asynchronous, each with a five-second deadline;
identity verification has one five-second total deadline. UID/PID, systemd
metadata, immutable installed files, launcher/environment and final unique-owner
continuity checks remain mandatory. Context-owned callbacks and frontend
generations prevent late verification from reviving a lost owner.

The resident agent retries transient authorization/state reads at most three
times per recovery episode (250/500/1000 ms). It never replays an ambiguous
mutation or retries explicit authorization rejection. A public snapshot does
not establish authorization. Losing the backend means observation is unavailable,
not that NetworkManager disconnected; notifications establish a fresh baseline
after recovery instead of inventing a tunnel transition.

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
Shutdown first retires accepted asyncio work under one absolute deadline,
passed from service publication cleanup through controller and adapter close,
and drops the D-Bus name. It then joins service-created non-daemon threads after
closing the event loop. A Core executor worker that remains blocked past that
final grace period causes an immediate nonzero process exit, preventing an old,
name-less backend from later completing persistence or NetworkManager work
beside its replacement. The systemd user unit's stop deadline is longer than
the complete orderly shutdown budget and remains a final external bound.
Official Core restores its Secret Service session while constructing the VPN
connector, and that connector is required to reacquire an unconfirmed packet
capture. The adapter therefore prewarms the session off the D-Bus event loop.
When a durable capture-recovery entry exists, this prewarm has a short bound:
an unanswered provider prompt fails startup nonzero with the entry retained,
allowing systemd to retry instead of falsely publishing readiness without a
capture supervisor. Once the session is available, Core reuses it while the
adapter constructs the connector and processes recovery before readiness.
Connector construction receives the same recovery-only bounded treatment
because it awaits system D-Bus services before the capture watchdog can be
armed. A stall therefore exits nonzero with the journal retained. If no session
is restored, startup does the same: Core intentionally ignores persisted
connection state while logged out, so its synthetic disconnected connector is
not evidence that an external capture has stopped.
Connector, capture-recovery, and reconnector callbacks remain private during
this startup transaction. The controller receives one authoritative snapshot
only after authentication state, refresher callbacks, and session services are
fully initialized; no intermediate callback can advertise readiness.

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

Same-owner foreground and connection requests also carry monotonic operation
identities. A backend state signal can legitimately arrive before its method
reply and make a retry available; the older reply is therefore discarded when
its operation identity no longer owns the result. The controller emits the
connection identity and target when it accepts the request, so one global QML
feedback surface tracks every origin without duplicating ownership in buttons.
A newer foreground action must still own a connection completion, and sign-out
clears any retained connection feedback from the previous account state.
Control operations also retain the account and foreground generation they
accepted. Disconnect establishes a new foreground owner; a delayed disconnect
or reconnection-preference reply cannot change global guidance, availability,
or completion after a newer action or account transition.
Packet-capture requests retain a separate generation because risk-reducing
cleanup must still settle its typed state and pending application shutdown when
a newer foreground request exists; that cleanup does not overwrite the newer
request's global busy state or guidance.

## Ownership consolidation checkpoint

The GUI distinguishes a transport timeout from completed provider work. It
retains a generation-bound unresolved foreground record and suppresses terminal
connection feedback until a valid snapshot read dispatched after the timeout
has returned, followed by confirmed idle state. A pending pre-timeout read is
not that receipt. A busy read preserves ownership; a later current-owner idle
signal can settle it exactly once. Ordinary signal-before-successful-reply
ordering still permits a successor; stale replies cannot settle that successor.

### Request-result evidence contract

**Observation, retirement and acknowledgement are separate facts.** A snapshot
describes current state; idle can release an owned wait; only the current
request's normal method reply acknowledges that request. A normal Connect reply
is not a claim that the tunnel is already established. Conversely a failure is
not proof that every side effect was rolled back. Missing acknowledgement stays
unconfirmed, even when a later state happens to match the requested target.

| Boundary | Permitted evidence and behavior |
| --- | --- |
| All seven native Connect routes and Disconnect | The shared reply handlers alone acknowledge a normal reply. After timeout, fresh read plus idle releases ownership with explicit unconfirmed guidance, never synthetic success. An existing or newly observed connected tunnel cannot prove a particular switch succeeded. |
| QML connection feedback | Present the generation-owned acknowledgement/failure/unconfirmed message. No second completion decision from connection state or unrelated status text. Owner/account loss and stronger connection diagnostics can retire that local feedback. |
| VPN, split-tunneling and DNS settings | A valid mutation reply acknowledges that write. Serialized readback refreshes values and releases the write gate; it does not acknowledge the earlier write. Preserve its unconfirmed marker through later ordinary reads until an explicit new write or owner/account reset. |
| Capture | Active includes reserved and unconfirmed capture obligations, so it cannot acknowledge Start or erase its failure. Confirmed inactive is a cleanup postcondition and may retire Stop guidance. Core's writer and durable supervisor are unchanged. |
| Agent lease and disconnect-and-quit | These answer lifetime/postcondition questions, not historical request success. Current authorized, healthy, ready, idle state can release a lease; idle-disconnected can satisfy quit's absence requirement. Their existing ownership checks remain. |
| Backend auth, settings, retry and capture owners | Preserve provider results/exceptions and explicit account/retirement evidence. Existing public Down barriers and process handoffs are not replaced by a state-only test. No Core changes. |
| Registration, support, NPS and package switching | Results come from their own authorized method reply/provider result or command exit; refreshes project current state. No idle-to-success conversion was found in these callers; their separate controls remain. |

The error-class regressions cross eight connection method routes, starting
connected versus disconnected/error, both settled connection states, and absent
versus present diagnostics (64 native rows). They retain the stale-read → busy
read → idle ordering. A separate 48-row QML matrix crosses initial/final state,
requested target, acknowledgement and reply/snapshot order. Three settings
families and both failed/unconfirmed capture Starts have sibling tests. These
are contract tests, not a guarantee against every future implementation error.

### Settings, browsing and lifecycle ownership

Each settings family has one request generation and a small typed request
state. Applying settings data changes values only, not busy state or request
messages. An ambiguous write requires serialized readback; failed readback
keeps writes blocked. An explicit read or later idle snapshot can retry the
read, never the write. Account or backend replacement invalidates the request.
Successful readback leaves the earlier write's result unconfirmed; the model
shows current values and explicit guidance without automatically repeating it.

Browsing and settings reads share eight backend admission slots. Rejection is
immediate when full, including readers waiting for the settings lock. A
cancelled provider read retains its slot until its child actually exits. The
GUI additionally sends at most one search at a time and retains only the newest
query for dispatch afterward; clearing search does not discard its live owner.
These bounds cover retained work, not the memory size of Core's server cache.

Sign-out publishes the retained account-restart fence even if its first journal
write or preliminary settings read fails. A write can replace the handoff file
before directory sync fails; failure therefore cannot safely erase the record
or reopen account admission. The UI shows recovery instead of stale signed-in
readiness. Degraded background updates likewise retain their own warning and
recovery guidance independently of unrelated operation messages.

The adapter uses one task-bound reentrant ownership primitive,
`TaskScope`, for the separate authentication and connection domains. Only the
actual owning task or an explicitly delegated child can reenter; copying an
asyncio context is not authority. Delegation expires with that acquisition.
Children are gated before execution, including with eager task factories.
The required order for coordinated session transitions is authentication before
connection; `TaskScope` does not itself enforce cross-domain lock ordering. The
controller's mutation admission lock has not been removed: it also orders
settings and support work and is not merely a duplicate adapter lock.

`join_owned` returns an `OwnedOutcome` containing provider value/error,
caller cancellation, and cancellation-request failure independently.
`await_owned` is its convenience projection: join first, then preserve caller
cancellation. Neither helper supplies a timeout or proves that a provider
coroutine has joined work that the provider itself detached.

`AsyncReconnector` is retry policy, not a second connection executor. It
requires the adapter's attempt, account-epoch, epoch-validation and expiry
callbacks at construction. Its production binding enters `_attempt_connection`,
the same connection-scope owner used by manual requests. That owner rechecks
account and intent after lock acquisition, joins accepted provider work, and
compensates stale success through the public Down barrier. The optional direct
Core connect/disconnect fallback has been removed; production already supplied
the owned callback before this subtraction.

Retry timing, route and unlocked-session probes, previous-server/protocol/backend
selection, certificate refresh and non-retryable error handling are unchanged.
Policy tests now use an explicit attempt owner and reject any direct Core Up or
Down call. Separate adapter tests cover invalidation while awaiting ownership
and compensation after a stale success. The existing cancellation-resistant
worker and manual-supersession tests continue to cover accepted retry work.
Cleanup and foreground requests have distinct end-to-end budgets below.

The Agent's `OperationCompletion` distinguishes awaiting a method reply from
reconciling that reply and being idle. A still-busy read retains reconciliation;
a later current-owner idle signal can settle it once. A signal before the
reply cannot settle that obligation, and an older result cannot release a
successor's lease. Transport timeout is an explicit completion-unknown
disposition, not owner loss. Browser-context retirement now dispatches retained
parent work, and disconnect-and-quit uses the same available/ready/healthy/idle
predicate on entry and subsequent updates.

Both native clients now derive connection permissions from `ConnectionAction.h`,
exposed through `VpnConnectionController`. The primary button's intent is
separate from permission to start a connection: an enabled **Cancel Connection**
must not enable server selection. Browser actions, pins, tray actions, shortcuts
and external-action confirmations consume the same permissions; native dispatch
and confirmation acceptance recheck them against current state.
The same projection supplies the validated idle-disconnected predicate for
disconnect-and-quit, so an unreadable snapshot cannot settle shutdown from a
previous disconnected observation.

| Current validated state | Connect to a target | Explicit Disconnect |
| --- | --- | --- |
| Ready, signed in, idle; disconnected, connected or error | Allowed, including a target switch | Allowed for connected or error |
| Connecting, or disconnected with pending busy work | Blocked | Allowed to request cancellation |
| Connected and busy, or account expired/unusable with a tunnel | Blocked | Allowed to request cleanup |
| Disconnecting | Blocked | No duplicate Down; disconnect-and-quit may wait |
| Unavailable, not ready, malformed snapshot or failed state read | No mutation | No mutation |

Schema 1 reports `busy`, not the kind of another client's operation. Explicit
Disconnect is therefore permitted during disconnected/busy, but busy alone does
not turn the primary button into Cancel. The backend admits Disconnect through
a retained cleanup owner. It can preempt connection work, but waits for an
already accepted non-connect foreground transaction before dispatching Down.
In particular, Core's settings save applies protection outside the connector's
event lock and must not race Down. Admission is not an immediate-completion
guarantee: a request that exhausts its budget while waiting is withdrawn with
an explicit rejection, without cancelling the earlier transaction or sending
Down later.
The Agent can request on-demand activation while the backend is absent and can
retain an explicit queued target. Neither grants permission to send Connect:
dispatch still requires an authorized owner, lease, applied recovery preference
and current shared capability. Startup auto-connect remains conditional on an
idle disconnected state. These changes add no polling, D-Bus schema or Core
modification. Policy-matrix tests, private-bus GUI/Agent tests and offscreen QML
confirmation tests cover admission; installed tray/shortcut acceptance remains
a separate gate.

The remaining operation contract is tracked here rather than in another ledger:

| Domain | Authority and invalidators | Completion / cleanup obligation |
| --- | --- | --- |
| Manual connect and retry | Authenticated session plus connection intent; newer target, disconnect, expiry, disabled recovery, or close invalidates | Join accepted provider work and compensate stale success within the retirement budget. Public Down samples its completion state in the provider task; identity errors and deadlines remain unconfirmed and force process replacement. Three actual-Core conformance cases supplement route-level fakes. |
| Authentication and FIDO | Authentication scope and epoch; cancellation/account replacement invalidates | Retain prompt and provider ownership through cancellation cleanup. Once refresh services have started, replacement login requires outgoing-process death plus fresh-process cleanup of the saved account. |
| Background refresh errors | Callback binding plus account epoch; disable, rebinding and close invalidate | One worker and one coalesced classified notice. Recheck after taking authentication ownership; defer cleanup outside the provider callback. Close fences admission and joins accepted handling under a bound. This does not join Core's own children. |
| Settings | Controller mutation admission plus account epoch | Do not retry ambiguous writes automatically; reconcile through current-account reads. Unsolicited settings data is not an arbitrary operation-completion receipt. |
| NPS/support | Explicit authorized request and session; NPS has its own completion identity | Ambiguous NPS submission remains non-retryable. Support stays disabled in the community build. |
| Cleanup admission | One session-tagged worker and absolute 30-second deadline per kind: Disconnect and capture Stop | Repeated requests share the original owner and budget. Stop bypasses unrelated foreground work; Down waits for non-connect transactions. Pre-dispatch expiry withdraws only that request. Final dispatch rechecks session and time; provider retirement inherits the remaining budget. New mutations cannot overtake accepted cleanup. |
| Packet capture | Separate capture ownership, durable recovery entry, deadline and byte cap | Stop cancels accepted Start once and joins its compensation; queued successor Start is not an accepted capture owner. Stop remains available during unrelated busy work. Existing capture deadlines and recovery persist. |
| Browsing | Backend owner, account and page/request generations | Stale output cannot update a model; retiring a context must dispatch valid retained work. Errors remain distinct from an authoritative empty list. |
| Agent action / lease | Backend owner and operation generation | Awaiting reply → reconciling → terminal; release once, never for a successor. Read failure and owner loss have explicit retirement paths. |
| Shutdown | First close owns one deadline and terminal result at controller and adapter boundaries | Pass the service deadline inward through handler retirement, connection supersession, Down and capture Stop. Drain cleanup workers without cancelling them during ordinary grace expiry. Expiry is sticky failure; accepted work remains owned until completion or process retirement. Preserve intentionally established tunnels. Process exit does not prove external NetworkManager teardown. |

Controller `busy` is derived from foreground ownership or any accepted cleanup
worker. A settings result, adapter snapshot or cleanup completion cannot clear
another owner's busy state. Cleanup errors also preserve an active foreground
transaction's guidance. The cleanup registry contains at most two workers;
there is no polling or persistent helper. Successor mutations check this
registry both before waiting for the foreground lock and after acquiring it,
then revalidate their captured account epoch. Cleanup revalidates immediately
before provider dispatch. These are ordering controls, not a new security
isolation boundary or a change to Core's networking policy.

**Cleanup request deadline:** the controller starts one 30-second event-loop
deadline when it accepts Disconnect or capture Stop. Waiting for Start
compensation, a conflicting foreground transaction or the cleanup-dispatch
lock consumes that same budget. Expiry before dispatch returns a bounded
`OperationFailed` rejection, not success or backend-owner loss. It does not
cancel the preceding transaction, repeat Start cancellation, or leave a request
that can unexpectedly run later. An explicit subsequent request gets a new
budget; a duplicate of a still-pending request does not.

The adapter inherits the exact deadline. Disconnect uses it for retry/manual
retirement, connection-scope acquisition and the public Down barrier. The
scope timeout bounds acquisition only and never cancels an already-owned
body. An unconfirmed adapter retirement uses the existing nonzero process-exit
boundary. Capture Stop retains its provider task under the same outer bound;
a cancellation-resistant stop that exceeds it likewise requires process
retirement, with the durable capture journal intact. Ordinary provider failure
still reports failure and retains active capture/recovery state. Neither a
deadline nor process exit proves external NetworkManager teardown. Normal
capture watchdog timing and the 15-minute safety limit are unchanged.

**Close deadline contract:** service shutdown supplies its already-running
30-second absolute event-loop deadline. Controller capture-Start compensation
is capped at 20 seconds within that deadline; ordinary work gets at most a
2.5-second grace (or half the remaining time) before cancellation. Neither
stage starts a fresh total budget. Adapter close inherits the exact deadline
for handler retirement, connection supersession, public Down and retry disable.
Capture Stop uses the lesser of its normal five-second attempt limit and the
remaining shutdown time. Its separate 15-minute `CLOCK_BOOTTIME` capture limit
and durable recovery deadline are unchanged.

Repeated close requests share the first deadline and cached terminal outcome;
even caller cancellation waits for that outcome before propagating. A bounded
adapter waiter retains its teardown worker rather than cancelling mandatory
provider cleanup when time expires. Time is rechecked after asynchronous
ownership waits and before subsequent teardown stages. An accepted provider
call can finish late, but cannot make an expired close successful. Retry
scheduling is fenced at close admission so failed teardown cannot re-arm it.
Service cleanup launches no further asynchronous stage once its budget is
exhausted; synchronous bus disconnect remains the name-drop fallback.

These bounds assume a progressing event loop, not preemption of synchronous
Core code. The existing one-second process-task and 250-ms thread-retirement
graces follow service cleanup, with systemd's unchanged 35-second stop limit as
the external backstop. The cleanup deadline deliberately does not cancel a
conflicting settings save.

**Foreground deadline contract:** each controller mutation starts one fixed
180-second event-loop budget before waiting for cleanup/admission. Expiry
before admission rejects the request without disturbing the previous owner.
After admission, one watchdog covers settings/session/scope waits, the full
provider transaction, compensation and state publication. It is not refreshed
by repeated cancellation, provider stages or security-key PIN input. Waiting
for an OTP between separate requests is not part of an active transaction.

The controller joins one complete transaction child. Auth and settings caller
cancellation waits for its authoritative state publication; it cannot cancel
an executor-backed write and skip reconciliation. Connect, capture Start and
FIDO forward cancellation once to their explicit cleanup path. Shutdown drains
the supervisor rather than independently cancelling its child. FIDO retains
the assertion/submission transaction while signalling its cancellable prompt.
Settings/report methods use this same owner instead of repeating wrappers.

Inner recovery limits still classify a slow stage, but accepted side effects
stay owned until terminal. They cannot extend the outer lifetime budget. At
expiry, the controller fences new work and uses the existing nonzero process
exit boundary; a late synchronous return also checks expiry. This does not
prove an external tunnel was removed, nor preempt synchronous code while the
event loop is stalled. The frontend's shorter transport timeout remains
completion-unknown, not proof of backend death. Read-only browsing and separate
NPS operations retain their existing domain policies rather than acquiring a
global mutation owner.

**Account replacement boundary (approved and implemented locally):** In Core
5.6.10 through 5.6.20, the public refresher's disable operation joins the
scheduler, not every child refresh operation. DISABLED still does not mean all
provider work has joined. Instead,
after refresh services have first started, the adapter permanently rejects
replacement credentials in that process. Sign-out records a non-secret handoff,
retires accepted connection work and the old tunnel through Core, and fences
account-scoped work even if sign-out fails or is cancelled. Protection-write
compensation remains available, but refreshers are not restarted afterward.

The native client requests systemd replacement after a current-owner successful
Logout reply. An expired session keeps an established tunnel until the user
chooses **Prepare sign-in**, whose notice explains the disconnect and restart.
No username, password, OTP or security-key response is queued across owners.
A failed/ambiguous Logout is not automatically retried or treated as permission
to restart; explicit recovery remains available.

`$XDG_RUNTIME_DIR/plasma-vpn-account-transition-v1.json` is an atomic, private,
bounded record containing only format version, outgoing process generation,
PID/start time and tunnel-retirement status. It survives backend failure, not
desktop logout/reboot. Fresh startup checks the previous process through a
Linux pidfd and start time, so a new D-Bus owner or PID reuse cannot masquerade
as overlapping account retirement. The systemd unit explicitly uses
`KillMode=control-group` and `SendSIGKILL=yes`; no process is signaled by the
journal reader. Startup then clears any restored outgoing session before
enabling refreshers or exposing readiness, verifies signed-out state, and only
then acknowledges the record. Recovery retains the startup lease and bounds
session restoration, connector restoration and account cleanup.

Invalid records, unavailable Python/kernel pidfd support, a still-running
outgoing process, missing retirement evidence
without a restorable session, and failed cleanup preserve the record and block
new credentials. The last case can require operator assistance: do not remove
the record merely to bypass an unconfirmed tunnel. It is not a credential store
or a defense against arbitrary same-user code. Actual installed systemd handoff,
Secret Service prompts and external NetworkManager teardown remain UAT gates.

**Background refresh failures (EC-03, implemented locally):** before enabling
Core's scheduler, the adapter installs its public `set_error_callback`. A
synchronous callback classifies the exception and returns without doing
cleanup. The relay retains one worker and one pending notice, prioritizing
authentication failure over an ordinary update failure. Notices contain only
account epoch, binding generation and failure kind, not provider messages,
tracebacks or credentials. A forced first yield preserves that handoff even
with eager task execution.

The worker acquires authentication ownership and rechecks the binding, epoch,
account-transition fence and signed-in state. Authentication failure uses the
existing expiry path: retire pending connection intent and disable scheduling,
but preserve an established tunnel until explicit sign-in preparation. Other
escaped refresh failures leave the account, tunnel, remaining jobs and retry
policy unchanged. They produce a persistent `signed_in_degraded` projection
and a warning in the main window, with sign-out/sign-in recovery guidance.
Foreground diagnostics retain priority; once cleared, the degraded message
returns. There is no automatic job replay or new background polling loop.

Close rejects new notices before taking a lock the handler may need. It
retains the worker through caller cancellation, and incomplete retirement
fails close under the inherited shutdown deadline. The enclosing service then
retires the process nonzero; late handler completion cannot refresh the budget
or change that failed result. Retired Core
callbacks use a stateless sink rather than retaining the adapter or setting
the callback to None (which tells Core to re-raise into the event loop).
This does not fix or suppress Core errors that occur before its callback
dispatch, nor imply that disabled scheduling has joined every Core child.
Foreground deadlines do not strengthen Core's public refresher join contract.

Provider-free tests cover coalescing, late callbacks, startup/login ordering,
stale session ownership, connection lookup cancellation, shutdown and handler
failure. Two opt-in tests additionally execute Core 5.6.20's hash-checked
scheduler and public callback forwarding, replacing all refresh I/O.

## Authentication and account state

The adapter calls Proton's public API facade for password login, TOTP and
recovery codes, FIDO2, session retrieval, and logout. Proton SSO persists the
session through a separately packaged keyring adapter. That adapter requires
the desktop-selected Secret Service provider to run as the session user, then
pins traffic to its unique owner instead of continuing to address the
replaceable `org.freedesktop.secrets` well-known name. The desktop's initial
provider selection remains an explicit session trust boundary.

Login, two-factor completion, sign-in cancellation, FIDO2 startup, logout,
session-expiry cleanup, and adapter shutdown share one reentrant authentication
transition boundary. Account-scoped settings, topology, and connection work
captures the adapter authentication epoch before entering Core. An
authentication failure may publish signed-out state and disable session
services only while that epoch still owns the active session; a stale failure
remains a failed request but cannot mutate a replacement account. The boundary
is reentrant for the owning task and explicitly registered settings/logout
recovery children only. Context inherited by an arbitrary child task grants no
authority; that task queues as an independent owner. Recovery deadlines execute
in their registered owner instead of relying on Python-version-specific
implicit task creation.

The frontend receives only minimum account display metadata. Authentication
fields use a one-use encrypted and sealed descriptor transport, and provider
exceptions are mapped to fixed public errors. Logout first quiesces automatic
reconnection, then disconnects, and restores the previous Core kill-switch
setting if any later step fails.
Destructive NPS notification retrieval and NPS submission share a narrow
session-side-effect fence with logout and backend shutdown. They do not acquire
the VPN-operation lock, so survey work cannot invisibly reject connect or
disconnect. Logout takes the VPN lock before the side-effect fence and shutdown
drains both in the same order. Shutdown rejects queued survey work before it can
enter the adapter. Core's synchronous mark-seen cache transaction runs on an
owned executor task so local filesystem work cannot block D-Bus control. Task
cancellation joins that worker before releasing the controller fence, so its
mutation cannot outlive ownership and race adapter teardown. Each
survey operation revalidates its captured session before and after the adapter
call, so work waiting behind logout cannot mark or submit data for the
replacement account. Submission and dismissal also retain frontend
generations until completion, but their failures do not replace foreground VPN
guidance. Once the official submission API is invoked, an exception is
conservatively classified as completion unknown: the frontend consumes the
survey without retry rather than risking a duplicate side effect.

FIDO2 is advertised only when Core explicitly guarantees that its public
cancellation event reaches multi-key selection as well as assertion and PIN
work. Enabled assertions set that event and any active PIN waiter, then join the
underlying task before releasing the adapter interaction or beginning teardown.
Current Core releases without the complete contract keep authenticator and
recovery-code sign-in available but do not expose the unsafe security-key flow.

## Server data and connection selection

Country, location-group, and exact-server reads are serialized at the frontend
boundary. Requests carry generations so replies for obsolete navigation targets
are discarded. A bounded retry covers Core's short topology-replacement window
without turning a genuinely empty group into an infinite refresh loop. If the
user selects a replacement target while that timer owns the browser, the timer
releases its busy lease and dispatches the queued current target instead of
silently abandoning both requests.

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

General settings, split tunneling, and custom DNS are views and mutations of
one persisted Core settings object. Their backend entry points therefore share
one completion-order lock, recheck their account epoch after waiting and after
Core returns, and are drained before adapter teardown. Pure reads return their
requested snapshot without emitting mutation notifications; only a successful
explicit update publishes the corresponding change signals.

DNS and split-tunneling saves acknowledge the confirmed primary result before
the separate scalar-settings refresh can fail. A refresh error produces a
fixed warning, not a rejected-write result or stale replacement list. Epoch
checks prevent secondary projections or warnings from reviving an expired
account. Transport timeouts still require read reconciliation, not write replay.

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

The home gear keeps the Inspector contextual and exposes one Help &
information page for non-operational project depth. That page states the
community support boundary before linking to separately owned release-history
and reporting pages. These pages use the same dynamically owned back stack, so
opening deeper information returns first to the hub and then to Connection;
direct visual and desktop deep links remain available for deterministic tests.

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
deadline. A frontend Stop can preempt an accepted in-flight Start, and
application shutdown retains cleanup ownership until the backend accepts Stop
or an authoritative idle snapshot confirms inactivity after a
completion-unknown reply. A temporary `busy=true`, inactive snapshot is not
sufficient. If the frontend's own Start call times out first, its positive
capture expectation remains cleanup ownership: a later Stop or shutdown still
dispatches the backend's preemptive Stop even though the original watcher has
settled. Stop remains available after account-session expiry and during an
unrelated foreground mutation. It joins accepted Start compensation before
dispatch and shares only final cleanup dispatch with Down. The session epoch
is checked again before Core is called so queued cleanup cannot cross into a
replacement account. Cancelling a caller does not abandon the retained worker.
Authentication, settings, and protection recovery states likewise preserve
this cleanup path while continuing to reject ordinary mutations.
Every Core stop attempt has its own timeout, so a non-returning
reply cannot indefinitely retain startup or backend shutdown. A
mode-restricted, atomically replaced recovery record in the private desktop
runtime directory preserves the original deadline across backend replacement.
The replacement reacquires Core and retries an unconfirmed stop before
publishing readiness; if no active connection can be reacquired, startup fails
for bounded systemd retry rather than discarding capture ownership. Any
recovery-directory entry also retains initialization against the ordinary
no-client idle deadline until startup clears or validates it; malformed state
therefore fails startup rather than being abandoned by a clean idle exit.
Deadline retries continue until Core confirms completion. The adapter does not
inspect, rename, upload, or rewrite PCAP data.

Direct support submission and anonymous crash reporting to Proton are disabled
in community builds through synchronized build, frontend, and backend gates.
Loading settings disables the unsupported runtime reporting sender and always
presents that preference as off without persisting a whole settings object from
a read path. An explicit settings mutation also persists the preference as off.
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
can be dispatched. An ordinary Disconnect temporarily suspends scheduling,
cancels and joins the owned retry, invokes Core only after that retry has
quiesced, then restores observation. A newer Error received while an older
retry unwinds rearms from the new generation whether the old cancellation is
suppressed or propagated. Every manual connection route acquires the same
owned suspension before its first server-list read and retains it through Core
connection completion. A delayed automatic attempt therefore cannot adopt a
newer manual intent, and an Error arriving during target lookup cannot schedule
a competing retry.

Manual targets are also registered as explicit asyncio owners. A newer manual
target, Disconnect, logout, session expiry, disabled recovery, or adapter close
invalidates the generation, cancels every older owner, and joins it before the
transition can complete. That rule covers all seven selection routes rather
than only a particular Connect entry point. Proton Core 5.6.10 through 5.6.20
can wait for NetworkManager in an executor, so cancelling the outer retry task
is not proof that the provider-side mutation stopped. The adapter shields and joins Core's
connection coroutine, performs a compensating disconnect after cancellation,
and only then releases lifecycle serialization. Those Core versions can also
return from Connect while a replacement target remains queued in Disconnecting; a
Down in that state does not clear the queue. Every invalidating transition
retains ownership across serialized Down requests and state changes. The
2026-09-07 [error-class review](SECURITY-AUDIT-2026-08-30.md#current-0130-error-class-review)
found that transitional cleanup skipped directly observed Disconnected while
Core still has queued work. Core assigns that property before awaiting state
tasks; its normal Disconnected notification comes later. A public Down also
captures connection identity before acquiring Core's event lock, so one round
trip alone is not a proven universal barrier.

The adapter crosses public Down even from directly observed
Disconnected. It captures the terminal state inside the task returning from
Down, not later in its waiter; every subsequent state change requires another
public barrier. A stale connection identity is unconfirmed, not silently retried
as success. The opt-in actual-Core harness uses hash-checked 5.6.20 connector
and state code with external I/O replaced, covering paused teardown, queued
promotion/identity rejection, and established-tunnel preservation. This
supplements the separate overlay oracle and unit-fake route matrix; it is not
full networking integration. Retirement retains its 30-second budget and
nonzero process exit on failure. Process exit bounds Python ownership, not
external NetworkManager teardown; installed acceptance remains required.

The resident agent likewise treats the recovery
preference as applied only after the current backend owner acknowledges it; a
failed or stale policy reply cannot release a queued connection action. Its
connection calls, queued actions, and transient lifetime leases also carry one
monotonic intent generation. Disconnect establishes a new intent before
checking the projected connection state, including the interval after Connect
dispatch but before the first connecting snapshot. A delayed reply or lease
from an older Connect can neither mutate state nor dispatch abandoned work; it
may serve a genuinely newer queued intent or is released.

KRunner recognizes only explicit VPN prefixes and validated connection targets.
It addresses the Control Center activation service, never the backend. KRunner,
global shortcuts, and tray connection actions share the bounded validator and
modal confirmation before the Control Center's authenticated controller acts.

The System Settings module owns desktop preferences only: startup,
auto-connect, drop recovery, window and tray behavior, notifications, pinned
targets, icon style, and capture storage. Live Proton settings are not
duplicated into a second controller. KConfig change notifications synchronize
the KCM, agent, and Control Center.

Both settings surfaces reuse `StartupSettingsSection.qml`. Window/tray and
auto-connect choices retain the existing KConfig and connection paths; `FASTEST`
still applies the configured capability requirements. Automatic connection does
not bypass saved-session or Secret Service requirements. Selecting tray-only
also enables the tray controls it needs; turning those controls off selects
window startup. Explicit application-launcher `--show` requests remain visible.

Login launch is separately opt-in. A lazily created `AutostartSettings` object
manages `$XDG_CONFIG_HOME/autostart/proton-vpn-kde.desktop` (normally under
`~/.config`), using the configured installed executable without `--show` or a
shell. It writes a KDE-only, marked desktop entry with `TryExec`; disabling
sets `Hidden=true`. Existing unmarked files and symlinks are not overwritten.
The file is re-read when the settings section is shown and before a write;
errors remain visible rather than reporting a successful save. This is an
ordinary same-user preference, not a security boundary against that user.
Installation and merely opening settings never enable login launch. The tray
agent does not construct this helper, poll autostart files, or add a watcher.

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
