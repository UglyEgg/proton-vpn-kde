# Security and engineering assessment — 2026-08-30

## Current release posture

**No finding from this assessment remains open in the current 0.11.2 release
candidate.** The review found seven issues in total: one high, four medium, and
two low severity. All seven were corrected and their original failure modes no
longer reproduce in focused tests.

The current source passes 35 of 35 native, QML, activation, packaging, and
integration tests plus 128 backend tests. A locally built Fedora package,
`0.11.2-8.fc44`, also passed scoped installed acceptance for package ownership,
service activation, KeePassXC Secret Service access through the declared
downstream keyring build, unauthorized-call
rejection, confirmation-gated KRunner requests, and live VPN connection and
disconnection.

The final public artifact must still be rebuilt from the exact clean release
commit, complete the full packaged acceptance checklist, and be signed. The
local acceptance RPM was not a signed release artifact.

This was a maintainer-directed, AI-assisted assessment conducted in the style
of a third-party review. It is not an independent audit, penetration-test
attestation, certification, or warranty of security.

## How to read this document

- **Current release posture**, **Current controls**, **Verification**, and
  **Residual risk** describe the current release candidate.
- **Closed findings** is the authoritative status table. Every listed finding
  is closed.
- **Historical finding record** describes conditions observed in earlier
  snapshots. Those descriptions are retained for traceability and must not be
  read as current vulnerabilities.
- Snapshot identifiers document what was reviewed; they are not release
  signatures.

## Scope

The assessment covered:

- the C++/Qt/Kirigami Control Center and resident Plasma agent;
- the Python community adapter and its session D-Bus API;
- authentication, second-factor, and FIDO2 PIN transport;
- settings, connection, logout, diagnostics, and packet-capture orchestration;
- KRunner, System Settings, tray, notifications, and shortcuts;
- Fedora packaging, systemd user services, activation, CI, and release
  metadata; and
- the boundary between community code and official Proton Core.

It did not internally audit unmodified Proton packages, NetworkManager, Secret
Service providers, Proton's remote services, or Proton infrastructure. Root,
debugger, and direct same-user process-memory inspection are outside the
project's documented security boundary. Production VPN traffic was not
intercepted or modified.

## Architecture and threat model

The resident Plasma agent and on-demand Control Center communicate with an
unprivileged Python service over the user's session bus. That service delegates
protocol selection, NetworkManager behavior, kill switch, IPv6 leak
protection, split tunneling, session persistence, and packet-capture writing to
official Proton Core.

Protected assets include Proton credentials and second factors, the saved
session, VPN security settings, diagnostics, package integrity, and backend
availability. The primary local attacker considered is an untrusted process in
the same graphical session that can access the user's D-Bus but has neither
root nor release-signing authority. Provider failures and interrupted lifecycle
operations are treated as hostile operating conditions.

The material trust boundaries are:

1. installed Plasma clients to the session-D-Bus backend;
2. frontend secret fields to backend decryption;
3. the community adapter to official Proton Core;
4. the Control Center to Polkit and DNF;
5. diagnostic and capture operations to user-selected storage; and
6. maintainer inputs to published source and RPM artifacts.

Detailed current designs are maintained in
[Architecture](ARCHITECTURE.md), [Authentication](AUTHENTICATION.md), and
[Backend service hardening](HARDENING.md).

## Current controls

### Service identity and client authorization

Installed native clients resolve the backend's well-known D-Bus name to a
unique owner and verify that owner against the packaged, root-owned systemd
user service and launcher. User-owned or writable overrides, unsafe loader and
Python environments, owner replacement, and identity mismatches fail closed.
Calls and signals remain pinned to the verified unique owner.

The backend captures the actual D-Bus sender before dispatch. State-changing
methods accept only authenticated, root-owned Control Center or resident-agent
executables. Registration claims must match the actual sender; authorization,
leases, and outstanding secret keys are revoked when that unique name
disappears.

KRunner is deliberately not a backend principal because it is a shared plugin
host. The runner can request only fastest, disconnect, two-letter country, or
validated exact-server actions from the Control Center. The Control Center
shows a modal confirmation and uses its existing authenticated controller only
after acceptance.

### Authentication payloads

Plaintext authentication fields are never placed in D-Bus string arguments.
The frontend authenticates the backend owner, requests an ephemeral X25519 key
bound to its actual sender and intended operation, derives an AES-256-GCM key
with HKDF-SHA256, and sends bounded ciphertext in a sealed anonymous `memfd`.
Keys are one-use and owner-generation bound. The backend requires the exact
field set, bounds the descriptor to 16 KiB, closes every descriptor path, and
overwrites its mutable input buffer.

The design does not claim to remove immutable copies that Qt or Python may
retain until normal allocator reuse, or to protect a process from root, a
debugger, or direct same-user memory inspection.

### Error and state handling

All exported methods pass through a shared error boundary. Explicit
backend-authored validation messages are bounded and single-line; unexpected
provider or library exceptions become stable public error classes without
their original text. Mutations are serialized and input patches use strict
field, type, range, and collection bounds.

Logout treats the temporary kill-switch transition as transactional. Any
failure after the transition restores the prior value through Proton Core's
official settings path before session services recover. A restoration failure
has a separate fail-safe error.

### Diagnostics and resource bounds

Direct support submission and anonymous crash reporting to Proton are disabled
in community builds at independent UI, native-controller, backend, and package
feature boundaries.

The dormant support collector uses fixed journal sources, no shell, a 20-second
process timeout, a 1 MiB limit per source, and a 2 MiB aggregate limit. Packet
capture requires a connected supported protocol, an existing writable absolute
directory, and Core's positive reviewed byte ceiling, currently no greater
than 512 MiB. A generation-bound 15-minute watchdog stops capture through
Core, and one lock serializes manual, watchdog, disconnect, and shutdown stops.

### Privilege and Core boundary

The backend and agent are unprivileged user services. Fedora packages use
absolute executable paths, `NoNewPrivileges`, an isolated Python launcher,
and explicit loader, Python, Qt-plugin, and QML environment cleanup. Packaged
native binaries were verified as PIE with non-executable stacks, GNU RELRO, and
immediate binding.

Package-channel changes use Polkit, absolute executables, and fixed arguments;
no shell or user-selected package name reaches DNF. Community code does not
implement VPN protocols or directly mutate NetworkManager, the kill switch,
IPv6 leak protection, split tunneling, or Proton session storage.

## Closed findings

| ID | Severity | Historical finding | Current status |
| --- | --- | --- | --- |
| PV-SEC-001 | High | A substituted session-bus backend could receive authentication secrets | **Closed** |
| PV-SEC-002 | Medium | Session-bus callers could invoke security-sensitive mutations without authorization | **Closed** |
| PV-SEC-003 | Medium | Failed logout could leave the persisted kill switch disabled | **Closed** |
| PV-SEC-004 | Medium | Rejected support-report calls leaked backend file descriptors | **Closed** |
| PV-SEC-005 | Low | Enabled support-log collection lacked byte limits | **Closed**; feature also remains disabled by default |
| PV-SEC-006 | Low | KDE capture orchestration lacked duration enforcement and Core-cap validation | **Closed** |
| PV-SEC-007 | Medium | Trusting the shared KRunner host granted broader backend authority than intended | **Closed** |

There are no deferred or accepted-open findings from this assessment.
Defense-in-depth opportunities are listed under **Residual risk and follow-up**
and are not represented as undisclosed vulnerabilities.

## Verification

### Automated source verification

The current remediated tree passed:

- 35 of 35 CTest tests, including native controllers, QML, D-Bus activation,
  staged installation, authentication, lifetime, KRunner, System Settings, and
  API-Core overlay coverage;
- 128 backend Python tests;
- static analysis, shell analysis, documentation-link validation, release
  metadata synchronization, and patch-whitespace validation;
- an optional build without direct KF6 status-notifier integration;
- isolated descriptor, sender-authorization, owner-replacement, secret replay,
  tamper, logout rollback, support-budget, and packet-capture race tests; and
- staged installation using the same systemd user-unit directory compiled into
  backend identity verification.

The focused harnesses show that the seven original failures no longer
reproduce: substituted owners are rejected, unauthorized mutations do not
reach the controller, secret keys cannot cross callers or operations, logout
restores the saved protection state, descriptors remain stable, diagnostics
stay within their budgets, captures cannot bypass Core's cap or the watchdog,
and KRunner cannot call the backend directly.

### Packaged Fedora acceptance

The locally built `proton-vpn-kde-0.11.2-8.fc44.x86_64` package passed:

- RPM payload, dependency, root ownership, systemd, D-Bus activation, and
  native-binary hardening inspection;
- backend activation with KeePassXC owning `org.freedesktop.secrets` and
  `python3-proton-keyring-linux-0.2.3-4.codex1` installed;
- ready, signed-in, disconnected startup without the GTK client;
- rejection of an arbitrary direct `UpdateSettings` call as unauthorized;
- loading the replacement KRunner plugin and requiring Control Center
  confirmation for its requests; and
- live KRunner connection and disconnection with NetworkManager returning to a
  disconnected state.

This was scoped acceptance of the security remediation, not a substitute for
the complete exact-release checklist in [Releasing](RELEASING.md).

### Performance regression check

An isolated disconnected demo stack measured 25.2 MiB backend PSS, 4.5 MiB
resident-agent PSS, and 52.9 MiB Control Center PSS: 82.5 MiB combined. The
current server-search projection retained about 2.63 MiB of traced allocation,
and measured query medians remained between 0.215 ms and 6.766 ms. These tests
found no material regression from the security controls. They are not live
connected-session measurements; full methodology is in
[Performance](PERFORMANCE.md).

## Holistic review result

### Hostile

Malformed signatures, unexpected descriptors, unauthorized senders, false
sender claims, secret replay and tampering, oversized inputs, settings
allowlists, rollback failures, capture stop races, support limits, and service
lifetime transitions were exercised. No open release-blocking hostile-input
defect remained after remediation.

### Subtractive

The client builds without optional direct status-notifier integration, runs
tests without official Core through the demo adapter, and keeps support and
crash submission removable through synchronized build capabilities. No
duplicate VPN protocol, NetworkManager, kill-switch, split-tunneling,
server-construction, or session-persistence implementation was found.

### Entropy and drift

Release metadata, documentation links, static-analysis policy, ignored debris,
and generated inputs are mechanically checked. The final tag must still be
created from a clean, reviewed tree and its exact source archive; assessment
digests are not release signatures.

### Error class

Public failures use a bounded, stable vocabulary. The review checked resource
and state postconditions in addition to exception types. No current
release-blocking error-class defect remained.

### HPC and performance

Authorization state, D-Bus checks, support bounds, and capture lifecycle state
remain bounded. Source measurements found no material disconnected memory or
search-latency regression. Connected official Core memory remains dependent on
server data, imported backends, and live NetworkManager state.

### Hardening and security

The current controls preserve the most important same-session trust boundary
without taking networking ownership from Core. The services intentionally omit
mount-namespace controls that prevent required peer verification under Fedora
SELinux; this tradeoff is documented in [Hardening](HARDENING.md).

## Residual risk and follow-up

- The project has not received an independent security audit. External review
  of service identity, sender authorization, and authentication transport is
  desirable before a stable or security-reviewed claim.
- Executable identity protects package-owned isolated processes, not arbitrary
  code already running inside them. Shared hosts such as KRunner therefore
  remain outside backend trust.
- Any same-session process can request a bounded KRunner confirmation dialog.
  It cannot silently mutate VPN state through that path, but it can create a
  presentation nuisance.
- Qt and Python cannot guarantee immediate erasure of every immutable secret
  copy. Root, debuggers, and direct process-memory readers remain out of scope.
- Official Proton Core, NetworkManager, Secret Service providers, and remote
  Proton services are trusted dependencies outside this assessment.
- The verified provider-neutral Secret Service behavior currently depends on a
  separately patched Proton keyring package. Its source, provenance, and
  distribution must be resolved before advertising stock-package KeePassXC
  compatibility.
- `systemd-analyze security --offline=yes --user` rates both desktop services
  9.0, “UNSAFE,” largely because a functional desktop VPN adapter retains host
  networking, home-state, device, and D-Bus access. This heuristic is not a
  vulnerability verdict. Compatible options such as a restrictive `UMask`,
  empty capability bounding set, `LockPersonality`, `RestrictRealtime`,
  `RestrictSUIDSGID`, `SystemCallArchitectures=native`, and selected
  `ProtectKernel*` controls remain defense-in-depth candidates requiring live
  Core, FIDO2, capture, KRunner, KCM, and tray regression testing.
- Every published release must repeat the full clean-tree package and live
  acceptance battery. Passing this assessment does not validate a later Core,
  Fedora, Qt, KDE Frameworks, or package revision automatically.

## Historical finding record — all closed

This section records what the assessment found before remediation. Every entry
below is closed in the current release candidate.

### PV-SEC-001 — Substituted backend identity

**Severity:** High
**Status:** **Closed**

The original frontend encrypted credentials to whichever process owned the
backend's well-known bus name without authenticating that owner. An isolated
bus test demonstrated pre-ownership by an unrelated process. The correction
verifies and pins the packaged backend's unique owner before key retrieval,
binds each operation to that owner generation, and fails closed on replacement.
Pre-ownership and owner-change regressions now pass.

### PV-SEC-002 — Missing mutation authorization

**Severity:** Medium
**Status:** **Closed**

The original backend validated inputs but did not authorize the actual caller
of state-changing D-Bus methods. A client that never registered could persist a
settings change. The correction captures the true sender at ingress,
authenticates package-owned client executables, mechanically classifies every
method, scopes keys and leases, and revokes state on owner loss. Unauthorized
calls now fail before controller dispatch.

### PV-SEC-003 — Logout kill-switch rollback

**Severity:** Medium
**Status:** **Closed**

The original logout path persisted a zero kill-switch value before remote
logout and did not restore the previous value if the remote operation failed.
The correction makes the transition transactional across reconnector shutdown,
remote failure, and cancellation. Failure-injection tests verify restoration
before session services recover and a distinct error if restoration itself
fails.

### PV-SEC-004 — Descriptor leak on rejected reports

**Severity:** Medium
**Status:** **Closed**

The feature-disabled support path originally rejected a transferred descriptor
before the only close path adopted it. Repeated calls increased the backend's
descriptor count one-for-one. The correction gives ingress exactly-once
descriptor ownership, closes unexpected descriptors on every method, and
requires exactly one referenced descriptor for secret methods. Isolated-bus
tests now show a stable descriptor count.

### PV-SEC-005 — Unbounded support attachments

**Severity:** Low
**Status:** **Closed**; direct submission remains disabled by default

The optional support collector originally bounded journal age and process time
but not bytes. The correction streams fixed sources under per-source and
aggregate limits with deterministic truncation, process termination, reaping,
and cleanup. The default community package still rejects submission before
collecting fields or logs.

### PV-SEC-006 — Capture lifecycle bounds

**Severity:** Low
**Status:** **Closed**

The initial finding overstated storage exposure: supported Core versions
already supplied a 512 MiB byte ceiling to Protun. The confirmed
community-owned gap was failure to validate that cap and the absence of a time
limit. The correction fails closed without a positive reviewed Core limit and
adds a 15-minute generation-bound watchdog. Serialized stop-path tests confirm
that Core receives at most one stop for each capture generation.

### PV-SEC-007 — Shared KRunner host authority

**Severity:** Medium
**Status:** **Closed**

The first remediation trusted `/usr/bin/krunner` as a backend client. Because
KRunner loads multiple native plugins in one process, executable verification
authenticated the shared host rather than this project's plugin. The
correction removes KRunner from every trusted-client list. The plugin now sends
only four validated request forms to the Control Center, which requires a
modal confirmation before its authenticated controller acts. Adversarial tests
prove that KRunner cannot authenticate to or call the backend directly.

## Assessment record

| Field | Original assessment | Post-remediation re-audit |
| --- | --- | --- |
| Date | 2026-08-30 | 2026-08-30 |
| Project version | 0.11.2 release candidate | 0.11.2 release candidate |
| Base revision | `67b8d5c91eb138e9f2f47dce31e59445bf51f5e8` | `67b8d5c91eb138e9f2f47dce31e59445bf51f5e8` |
| Working-tree snapshot | `codex-security-snapshot/v1:sha256:73c150323a8626eec3e86e728b20a9b605dc97bc204bada0c0f7004f24605286` | `codex-security-snapshot/v1:sha256:f2f8ee7938c821b0ccc9597f41212138832a1d44efa2f3ac90f9559eae56920e` |
| Canonical scan ID | `2addbe32-b22c-4e43-80ac-17dc593e5f80` | `6914a5eb-b5e4-4ab1-b332-dfc9096641cc` |
| Source inventory | 207 files | 214 files |
| Result at scan time | Six findings | One additional medium finding, PV-SEC-007 |
| Current status | All findings closed | PV-SEC-007 subsequently closed |

The working tree contained a coherent uncommitted release-candidate change set,
so the base revision alone does not identify either assessed snapshot. The
later KRunner correction and packaged `0.11.2-8` acceptance occurred after the
sealed re-audit snapshot and are identified by current source, tests, and
package evidence rather than by rewriting that historical digest.
