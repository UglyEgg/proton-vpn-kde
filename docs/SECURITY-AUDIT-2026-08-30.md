# Security and engineering assessment — 2026-08-30, refreshed 2026-09-01

## Current assessment posture

The public `0.11.3` baseline has no open finding from the assessments recorded
in this document. The original review found seven issues: one high, four
medium, and two low severity. All seven were corrected, their original failure
modes no longer reproduce in focused tests, and the 2026-08-31 `0.11.3`
re-review found no new reportable issue.

The unreleased `0.12.0` branch adds event-driven backend lifetime and an
on-demand Connection Inspector. Its pre-final isolated reviews and subsequent
standard security scans found lifecycle, error-class, Secret Service identity,
desktop-action-broker, and inherited native-loader environment defects. Every
reported path has a focused response in the current working tree. **The
`0.12.0` candidate remains explicitly not release-ready until six fresh
isolated reviewers pass one exact remediated commit, its packages complete live
acceptance, and that commit finishes the one-week local soak.**

The current source verification passed Mypy, Ruff, all 35 production
translation units under Clang-Tidy, 198 backend tests at 81% measured branch
coverage, and all 37 CTest targets both normally and under address, leak, and
undefined-behavior sanitizers. These results validate the working tree; they do
not substitute for the exact-commit review, package, live-acceptance, or soak
gates.

The public `0.11.3` source passed Mypy, Ruff, Clang-Tidy across all 34
production translation units, and the complete native test suite under address,
leak, and undefined-behavior sanitizers. The most recent installed Fedora
package, `0.11.2-29.fc44`, contains the 0.11.3 hotfix code and passed host-level
RPM verification, normal Plasma D-Bus activation, KeePassXC session restoration,
VPN connection and disconnection, and deliberate backend restart while the
NetworkManager tunnel remained connected. Earlier `0.11.2-24.fc44` acceptance
covered KeePassXC authentication and deliberate backend-service recovery;
`0.11.2-8.fc44` acceptance covered unauthorized-call rejection and
confirmation-gated KRunner requests.

The exact local `0.11.3-1.fc44` client RPM/SRPM and both pinned overlay
RPM/SRPM pairs were subsequently built from committed release metadata. They
passed their complete package tests, artifact policies, combined replacement
transaction, and native-binary hardening inspection. The final public artifact
must still be rebuilt from the final clean audited commit and signed; none of
these local acceptance packages is a signed release artifact.

This was a maintainer-directed, AI-assisted assessment conducted in the style
of a third-party review. It is not an independent audit, penetration-test
attestation, certification, or warranty of security.

## How to read this document

- **Current assessment posture** and **0.12.0 isolated review gate** describe
  the unreleased branch and make its release decision explicit.
- **Current controls**, **Verification**, and **Residual risk** describe the
  source controls shared by the public baseline and current branch; versioned
  package evidence is labeled separately.
- **Historical finding record** is the authoritative status record for the
  original seven security findings. Every listed finding is closed; the
  retained descriptions concern earlier snapshots and must not be read as
  current vulnerabilities.
- Snapshot identifiers document what was reviewed; they are preserved in their
  tool-generated form and are not release signatures.

## 0.12.0 isolated review gate

Six reviewers inspect Hostile, Subtractive, Entropy, Error-Class,
HPC/Performance, and Hardening/Security concerns independently. Reviewers do
not receive another reviewer's findings or perform multiple legs sequentially.

The first `0.12.0` battery was sealed against runtime commit `659ce23` and
returned:

| Review | Initial result | Release-relevant outcome |
| --- | --- | --- |
| Hostile | Fail | Late settings reads could cross logout; an agent connection could proceed without a current accepted recovery policy. |
| Subtractive | Pass | No release blocker; identified small duplicate checks and presentation helpers. |
| Entropy | Pass | No release blocker; identified documentation and duplicated-label drift. |
| Error-Class | Fail | A retry could outlive cancellation while waiting for network or session readiness. |
| HPC/Performance | Pass | No release blocker; requested refresh coalescing and stronger Inspector retention evidence. |
| Hardening/Security | Pass | No reportable vulnerability; a separate validator classified the unprivileged ephemeral pull-request overlay build as informational under its current authority. |

A formal standard security scan of the 282 tracked files at `659ce23`
(`c22625ca-b71e-4198-b443-c1d29e1c5d19`) also completed all configured surfaces
with zero reportable findings. That scan predates the lifecycle remediations;
the fresh Hardening/Security leg below must therefore review the remediated
snapshot before this gate can close.

The remediation scopes asynchronous settings replies to an account-session
generation, keeps retry cancellation live through every readiness await,
requires the resident agent to apply the current recovery policy before a
connection action, coalesces Inspector snapshot refreshes, cleans partial
logind initialization, and reuses the authorizer's owner verification for
frontend lifetime registration. A later fresh Hostile pass identified a broader
owner-replacement class: delayed generic frontend replies were not all bound to
their originating backend. Every asynchronous Control Center and resident-agent
reply now carries both the authenticated unique destination and backend
generation, and backend signals are accepted only from that current unique
owner. Two service-replacement regressions prove an old owner cannot disable
its healthy successor or clear its queued action. Readiness-probe
exceptions also remain inside the bounded retry lifecycle. Focused regressions
cover every release blocker found to date.

A second pre-final review at `98969fc` deliberately restarted the review gate
after those changes. Hostile review identified late country, group, server,
load, search, and NPS reads that were not yet account-generation fenced, plus a
cancelled logind initialization that could retain its temporary bus. Error-Class
review found that the reconnect exponential could overflow before its 60-second
cap after a sufficiently long outage, a same-owner snapshot timeout could leave
the Control Center falsely offline without retry, and login state could be
committed before refresher startup completed. Those are remediated by complete
account-read fencing, cancellation cleanup, bounded backoff before exponentiation,
transient snapshot retry, and transactional session-service startup.

The standard security scan of that second snapshot
(`a13d81f0-f762-4406-b59c-c50959d10357`) reported three additional issues: one
high-severity Secret Service provider-identity gap and two medium-severity
desktop broker paths. The keyring adapter previously treated the replaceable
`org.freedesktop.secrets` well-known owner as sufficient identity before sending
Proton session material. The new separate overlay patch requires the selected
owner to run as the session user, pins every call to that unique owner, validates
reply and prompt-signal senders, and rejects owner replacement. Live Fedora
acceptance proved that unprivileged executable attestation is not portable:
KeePassXC deliberately denies same-user `/proc/<pid>/exe` inspection, while
process names, command lines, and user-owned autostart units are spoofable. The
current design therefore records the initially selected provider as an explicit
platform trust dependency instead of presenting weak process metadata as
authentication. KGlobalAccel and status-notifier D-BusMenu actions previously
invoked the authorized resident controller directly. They now send only bounded
requests to the Control Center's explicit modal confirmation; the combined
disconnect-and-quit action uses a guarded local confirmation.

These paragraphs are the historical pre-final finding record. They do not mark
the remediated working tree as passed: the exact final commit must still receive
six fresh independent results below.

A later standard security scan of clean revision `e1f4ac8`
(`6d471a8c-ea5b-447a-a87b-3738a0a7ea97`) found that the systemd user manager
could pass OpenSSL-provider and GIO/GI loader overrides into the Python backend
before Proton Core initialization. The remediation defines one checked-in
unsafe-environment contract, generates both systemd units and native policy
from it, scrubs the environment again in the root-owned launcher before imports,
and makes staged-install and RPM checks enforce the exact installed contract.

Review also established the limit of those checks: arbitrary native code
already executing as the desktop user can transiently replace a user-owned
systemd drop-in, inject into a packaged process, and restore the observable
configuration. Unprivileged Linux process metadata cannot durably attest
against that already-equivalent authority. The project therefore explicitly
places arbitrary same-UID host-code execution outside scope while retaining the
sanitization and owner checks against ordinary or sandboxed session peers. This
is a clarified threat boundary, not a claim that the bypass became impossible.

The first exact-commit gate at `42afa2f` then found a related command-search
path: the reconnect readiness probe resolved `ip` through inherited `PATH`, and
the dormant support collector did the same for `journalctl`. A user-writable
leading path could therefore move code execution from a sandboxed peer into the
unsandboxed backend. The remediation pins the Fedora package paths already
required by the client, adds a hostile-`PATH` regression, and makes the
production idle deadline ignore the demo-only environment override. Because
this changed runtime code, every six-review result for `42afa2f` is discarded;
the next exact commit restarts the complete gate.

The restarted exact-commit gate at `b1f010d` found that direct Control Center
D-Bus activation did not cross the new pre-loader systemd boundary. It also
found that the Plasma System Settings module and the agent's last-resort
launches could still select project executables through inherited `PATH`.
Those results are discarded because the remediation adds a dedicated Control
Center systemd user service carrying the shared environment policy, uses one
compile-time installed-path module for the KCM and agent fallbacks, and makes
the desktop entry absolute. Staged-install, package, native hostile-`PATH`, and
missing-helper regressions cover the corrected launch boundaries. The complete
six-review gate must restart again on the resulting exact clean commit.

That next gate at `8dac1fd` returned four passes before Error-Class review found
two transactional-state defects. A cancelled or completion-unknown Core packet
capture start could leave capture active without the community watchdog, and a
failed reconnection-observer registration could leave reconnection marked
enabled while future registration attempts became no-ops. Every result from
that gate is discarded. The remediation now reserves capture state before the
Core call, compensates uncertain starts while retaining the original deadline,
commits reconnection enablement only after registration, and guarantees session
probe cleanup after observer-removal failure. The complete gate must restart on
the new exact commit.

The following gate at `b50b693` then failed its HPC/Performance leg because a
non-returning Core stop reply could hold the compensation lock indefinitely
before the watchdog was armed, retaining capture startup and blocking bounded
backend shutdown. Every result from that gate is discarded. The watchdog is
now armed before compensation, every Core stop attempt and retry is bounded,
and a never-returning-stop regression covers the controller shutdown path. The
complete gate must restart on the resulting exact commit.

The gate at `59fa94b` then passed HPC/Performance and Entropy before
Error-Class review found that a Core object rejecting the capture-directory
assignment could leave capture falsely active without a watchdog, although Core
had never received a start request. Every result from that gate is discarded.
Capture configuration is now accepted and sanitized before lifecycle state is
reserved; focused coverage proves rejection remains inactive, watchdog-free,
and retryable. The complete gate must restart on the resulting exact commit.

That gate at `75bdbd0` passed Error-Class and HPC/Performance before Entropy
reported `git diff --check` failures on the single-space context markers
required by a checked-in unified-diff payload. Every result from that gate is
discarded. Git now treats those context markers as patch syntax, while a
dedicated source check continues to reject trailing whitespace in lines the
overlay actually adds to its target. The patch bytes and manifest digest remain
unchanged. The complete gate must restart on the resulting exact commit.

The gate at `a522fd0` then failed Error-Class review because the first semantic
checker treated every `+++` prefix as a file header, including an in-hunk added
target line whose content began with `++`. Every result from that gate is
discarded. The checker now tracks declared old/new hunk sizes, distinguishes
headers from content by parser state, and has focused regressions for ordinary
additions, blank context markers, file headers, and `++`-prefixed target
content. The complete gate must restart on the resulting exact commit.

The gate at `a4c174a` then failed Entropy review because Python's generic byte
line splitter treated an embedded carriage return as a line boundary. A valid
added line ending in carriage-return, space, line-feed could therefore evade
the dedicated trailing-whitespace check even though Git applied those bytes.
Every result from that gate is discarded. Patch input is now split only on
line-feed boundaries, genuine CRLF framing is normalized, stray carriage
returns are rejected, and both cases have raw-byte regressions. The complete
gate must restart on the resulting exact commit.

The gate at `0bd16be` then failed Error-Class review. Per-line CR stripping
allowed a mixed-LF/CRLF patch to introduce a carriage return into target source,
and a terminal line-feed could masquerade as empty hunk content. Separately, a
Core settings write could persist a disabled kill switch before connector
application failed; retrying then skipped the Core write and falsely reported
the live state disabled. Every result from that gate is discarded. Line-ending
style is now enforced for the complete patch, terminal split sentinels are not
hunk content, and login preparation always asks Core to apply the disabled
kill-switch state. Focused regressions cover all three paths. The complete gate
must restart on the resulting exact commit.

The gate at `222f5f0` passed Hostile, Subtractive, Entropy, Error-Class, and
HPC/Performance review, then failed the canonical Hardening/Security scan. The
native frontend objects exported every public slot, including unauthenticated
`Agent1.Quit` and `ControlCenter1.Quit`; an ordinary session peer could cleanly
terminate the agent or Control Center. The active Core tunnel remained intact,
so the validated finding was Low severity. Every result from that gate is
discarded. The Control Center shutdown method is removed, the agent's retained
background-controls shutdown path authorizes the current packaged Control
Center owner, and object registration exports only explicitly scriptable
slots. Isolated activation coverage proves an arbitrary shutdown caller fails
while both processes remain alive. The complete gate must restart on the
resulting exact commit.

The gate at `4b36979` passed HPC/Performance review, then failed Error-Class
review. The backend acquired its public D-Bus name before awaiting authorization
setup and exporting `Backend1`. The agent could observe that intermediate state,
make its one authorization attempt too early, and leave a queued automatic
connection stranded after the backend became ready. Every result from that gate
is discarded. Backend startup now installs authorization handling and exports
the service object before publishing the well-known name. A deterministic
ordering regression covers the publication boundary. The complete gate must
restart on the resulting exact commit.

The gate at `223e590` passed Error-Class, HPC/Performance, and Hostile review,
then failed Entropy/Reproducibility review. Independent builds from the same
clean commit produced identical source archives but different RPM and SRPM
bytes because RPM headers retained the wall-clock build time and local host.
Every result from that gate is discarded. The spec now derives header build
time from the source-date epoch and uses a fixed non-routable build host, while
CI compares the complete output sets from two clean package builds byte for
byte. The complete gate must restart on the resulting exact commit.

The gate at `3e58e63` did not enter isolated review. Its local package proof
found that installed native targets retained the build-tree translation path
and that RPM source headers necessarily retained expanded top-directory paths.
The package build now compiles the installed translation directory into
production targets and runs both clean builds under one normalized RPM build
and source path while retaining separate output trees. The byte comparison
still covers the complete binary, debug, debug-source, and source RPM set. The
complete gate must start on the resulting exact commit.

The gate at `6aaab53` entered isolated review only after two clean normalized
package builds produced byte-identical binary, debug, debug-source, and source
RPMs. Error-Class review then found three completion-state defects. A
successful login-cleanup call could publish signed out even when Core still
reported an authenticated session; a settings save could persist a new value
before live connector application failed; and frontend timeouts treated
connection or settings mutations as definitely failed without first
reconciling authoritative state. Every result from that gate is discarded.
Login cleanup now follows only Core's postcondition, user settings writes use
bounded compensating transactions with explicit recovery-required states, and
both native frontends retain or reload state until a completion-unknown
operation is reconciled. Focused regressions cover persisted-then-failed
writes, failed and timed-out compensation, Core-confirmed login states, and
same-owner D-Bus timeouts. The complete six-review gate must restart on the
resulting exact commit.

| ID | Pre-final severity | Finding at reviewed snapshot | Current working-tree status |
| --- | --- | --- | --- |
| PV-012-001 | Medium | Account-scoped location and NPS reads could complete after logout | **Remediated; final independent verification pending** |
| PV-012-002 | Low | Cancellation during logind proxy setup could retain a temporary bus | **Remediated; final independent verification pending** |
| PV-012-003 | High | Pathological reconnect count overflowed before applying the backoff cap | **Remediated; final independent verification pending** |
| PV-012-004 | Medium | A same-owner snapshot timeout could leave the UI falsely offline | **Remediated; final independent verification pending** |
| PV-012-005 | Medium | Login state could commit before session services finished starting | **Remediated; final independent verification pending** |
| PV-012-006 | High | A replaceable Secret Service owner could receive future Proton session writes | **Mitigated by unique-owner pinning; initial provider remains a documented platform trust dependency; final independent verification pending** |
| PV-012-007 | Medium | KGlobalAccel could invoke the authorized resident controller directly | **Remediated; final independent verification pending** |
| PV-012-008 | Medium | D-BusMenu tray activation could invoke the authorized resident controller directly | **Remediated; final independent verification pending** |
| PV-012-009 | High | Inherited OpenSSL and GIO/GI environment overrides could load native code in the backend | **Remediated within the documented threat boundary; final independent verification pending** |
| PV-012-010 | Medium | Inherited `PATH` could select an attacker-written `ip` executable for the reconnect probe | **Remediated with a fixed packaged path; final independent verification pending** |
| PV-012-011 | High | Direct Control Center D-Bus activation could load inherited native-loader overrides before Qt startup | **Remediated with a sanitized systemd activation unit; final independent verification pending** |
| PV-012-012 | Medium | KCM and agent fallback launches could select project executables through inherited `PATH` | **Remediated with configured absolute paths; final independent verification pending** |
| PV-012-013 | Medium | Cancellation or a late failure after Core accepted packet-capture start could leave capture outside the community watchdog | **Remediated with precommitted state, compensating stop, and original-deadline watchdog; final independent verification pending** |
| PV-012-014 | Medium | Failed reconnection-observer registration could leave enablement stale and future attempts inert | **Remediated with registration-first commit and rollback; final independent verification pending** |
| PV-012-015 | Medium | A non-returning Core capture-stop reply could retain startup and block backend shutdown before the watchdog was armed | **Remediated with pre-armed watchdog and bounded stop attempts; final independent verification pending** |
| PV-012-016 | Medium | A rejected Core capture-directory assignment could leave a false active state with no watchdog and block retries | **Remediated by configuring before lifecycle reservation; final independent verification pending** |
| PV-012-017 | Low | Public frontend D-Bus `Quit` methods allowed arbitrary session peers to terminate the agent or Control Center | **Remediated by removing Control Center shutdown, authorizing agent shutdown, and explicitly allowlisting exported slots; final independent verification pending** |
| PV-012-018 | Medium | The backend published its D-Bus name before authorization and object export were ready, allowing the agent's one startup authorization attempt to fail permanently | **Remediated by publishing the well-known name only after ingress authorization and object export are ready; final independent verification pending** |
| PV-012-019 | Medium | RPM and SRPM headers embedded wall-clock build time and the local builder host, defeating byte-reproducible package builds | **Remediated with source-epoch build time, a fixed non-routable build host, and a two-build byte-comparison gate; final independent verification pending** |
| PV-012-020 | Medium | Successful login cleanup could publish signed out while Core still retained or could not confirm the authenticated session | **Remediated by deriving the published state exclusively from Core's postcondition; final independent verification pending** |
| PV-012-021 | Medium | A user settings write could persist before live connector application failed, leaving the current interface and next startup inconsistent | **Remediated with serialized compensation and recovery-required states for unconfirmed persistence; final independent verification pending** |
| PV-012-022 | Medium | Frontend timeouts treated connection and settings mutations as definitely failed and released their reconciliation lifetime early | **Remediated with authoritative refresh and lease retention for completion-unknown operations; final independent verification pending** |

**Final result:** pending six fresh isolated reviews of the remediated snapshot.
This pending line is a release gate, not an open vulnerability claim.

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
debuggers, and arbitrary native code already executing as the desktop user are
outside the project's documented security boundary. This includes direct
same-user process-memory modification, native injection into packaged
processes, and transient mutation of user-owned systemd units or drop-ins.
Production VPN traffic was not intercepted or modified.

## Architecture and threat model

The resident Plasma agent and on-demand Control Center communicate with an
unprivileged Python service over the user's session bus. That service delegates
protocol selection, NetworkManager behavior, kill switch, IPv6 leak
protection, split tunneling, session persistence, and packet-capture writing to
official Proton Core.

Protected assets include Proton credentials and second factors, the saved
session, VPN security settings, diagnostics, package integrity, and backend
availability. The primary local attacker considered is an ordinary or sandboxed
process in the same graphical session that can access the user's D-Bus but has
neither root, release-signing authority, nor arbitrary native-code execution as
the desktop user. Provider failures and interrupted lifecycle operations are
treated as hostile operating conditions.

The material trust boundaries are:

1. installed Plasma clients to the session-D-Bus backend;
2. frontend secret fields to backend decryption;
3. the community adapter to official Proton Core;
4. the Control Center to Polkit and DNF;
5. diagnostic and capture operations to user-selected storage; and
6. the keyring adapter to the selected Secret Service provider; and
7. maintainer inputs to published source and RPM artifacts.

Detailed current designs are maintained in
[Architecture](ARCHITECTURE.md), [Authentication](AUTHENTICATION.md), and
[Backend service hardening](HARDENING.md).

## Current controls

### Service identity and client authorization

Installed native clients resolve the backend's well-known D-Bus name to a
unique owner and check its current process against the packaged, root-owned
launcher, active systemd user service, acceptable unit inputs, and safe loader
environment. User-owned or writable overrides fail closed while present, and
calls and signals remain pinned to the checked unique owner. These current-state
checks are defense-in-depth against the in-scope attacker, not OS-backed
attestation against arbitrary native same-UID code.

The backend captures the actual D-Bus sender before dispatch. State-changing
methods accept only senders currently executing the root-owned Control Center
or resident-agent paths without a denied loader environment. Registration
claims must match the actual sender; authorization, leases, and outstanding
secret keys are revoked when that unique name disappears.

KRunner, KGlobalAccel, and status-notifier D-BusMenu are deliberately not
backend principals because they are shared desktop brokers. They can request
only fastest, disconnect, two-letter country, validated group, or validated
exact-server actions from the Control Center. The Control Center shows a modal
confirmation and uses its existing authenticated controller only after
acceptance. The resident tray's combined disconnect-and-quit action requires a
guarded local confirmation before its coordinator can act.

### Secret Service provider identity

The downstream keyring adapter activates the configured Secret Service without
sending secret data, resolves the well-known name to a unique owner, requires
that owner to run as the session user, and then addresses the unique owner
directly. It verifies method-reply and prompt-signal senders and checks the
well-known owner before every operation. Owner replacement fails closed. The
Fedora client requires the overlay's explicit owner-pinned capability so the
older alias-only package cannot satisfy this control accidentally.

The session bus does not portably attest the executable behind a non-dumpable
provider. The initial desktop-selected same-user Secret Service provider is
therefore a trusted platform dependency. This control prevents a later name-
owner replacement from inheriting traffic; it does not prove the package
provenance of the initially selected provider.

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

The backend, agent, and Control Center are unprivileged user services. Fedora
packages use absolute executable paths, `NoNewPrivileges`, an isolated Python
launcher, and one generated policy for dynamic-loader, OpenSSL-provider,
GIO/GI, Python, Qt-plugin, and QML environment cleanup. D-Bus activation of all
three processes crosses those systemd units before application imports, and
the launcher repeats the cleanup before backend and Core imports. Packaged
native binaries were verified as PIE with non-executable stacks, GNU RELRO,
and immediate binding.

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

There are no deferred or accepted-open findings among the original seven.
The separate unreleased `0.12.0` table above remains verification-pending until
the final six-reviewer gate closes.
Defense-in-depth opportunities are listed under **Residual risk and follow-up**
and are not represented as undisclosed vulnerabilities.

## Verification

### Automated source verification

The current remediated tree passed:

- 37 of 37 CTest tests, including native controllers, QML, D-Bus activation,
  staged installation, authentication, lifetime, KRunner, System Settings, and
  API-Core overlay coverage;
- 198 backend Python tests;
- static analysis, shell analysis, documentation-link validation, release
  metadata synchronization, and patch-whitespace validation;
- an optional build without direct KF6 status-notifier integration;
- isolated descriptor, sender-authorization, owner-replacement, secret replay,
  tamper, logout rollback, support-budget, and packet-capture race tests; and
- staged installation using the same systemd user-unit directory compiled into
  backend identity verification.

The current keyring overlay rebuilt from Proton's pinned 0.2.3 archive, applied
all three manifest-hashed patches without fuzz, passed 29 of 29 focused tests in
RPM `%check`, and produced one binary and one source RPM. Its artifact check
verified both the provider-neutral and owner-pinned capabilities. The corrected
package subsequently selected the already-running KeePassXC provider and
restored the live Proton session without a restart loop or warning.

The focused harnesses show that the seven original failures no longer
reproduce: substituted owners are rejected, unauthorized mutations do not
reach the controller, secret keys cannot cross callers or operations, logout
restores the saved protection state, descriptors remain stable, diagnostics
stay within their budgets, captures cannot bypass Core's cap or the watchdog,
and KRunner cannot call the backend directly.

### Packaged Fedora acceptance

The accepted `0.12.0` runtime revision `d2e7a74` produced the exact local
`proton-vpn-kde-0.12.0-0.4.fc44` client RPM/SRPM and
`python3-proton-keyring-linux-0.2.3-7.plasmavpn1.fc44` overlay RPM/SRPM. The
client package passed all 142 backend tests, Mypy, 79% measured branch coverage,
all 36 CTest targets, artifact policy, and a combined replacement transaction.
The keyring package applied all patches without fuzz, passed 29 focused tests,
and exposed the provider-neutral and owner-pinned capabilities. The accepted
binary SHA-256 digests were `22358efa087ac4c7f94d7c0a1149939a514b4b18ca7f6b3ad4846649d74f75d8`
for the client and `a598c8412bfdcef5948c912bc43fddf58faa78c1bd88402b52bca193f0c32265`
for the keyring overlay.

Both packages were installed in one transaction. Host verification found their
payloads root-owned and unmodified, the resident agent and backend active with
zero restarts and no warning-level journal entries, and KeePassXC still owning
`org.freedesktop.secrets` as the same session user. Maintainer acceptance covered
the Control Center, Connection Inspector, and normal navigation. The pre-existing
Proton VPN profile, `proton0` tunnel, and leak-protection connection remained
active throughout installation and backend startup. This proves compatibility
with the intended live stack; it does not close the six-reviewer or soak gates.

The exact local `proton-vpn-kde-0.11.3-1.fc44.x86_64` package candidate passed:

- all 130 backend tests, Mypy, 78% measured branch coverage, and all 36 CTest
  tests during RPM `%check`;
- RPM payload, dependency, root ownership, mode, systemd, D-Bus activation,
  community-reporting gate, digest, and source-package inspection;
- independent keyring and API-Core overlay RPM/SRPM builds and policy checks;
- a combined three-package replacement transaction; and
- inspection of all four native ELF files for PIE/shared-object relocation,
  non-executable stacks, GNU RELRO, and immediate binding.

The installed `proton-vpn-kde-0.11.2-29.fc44.x86_64` hotfix package added the
0.11.3 reconnect changes. With the independently verified API-Core and keyring
overlays installed, it passed RPM verification, normal D-Bus activation,
KeePassXC authorization, connection and disconnection, and a deliberate backend
restart while the tunnel remained connected. NetworkManager reported that no
additional Protun secrets were required; the client reauthenticated the new
backend owner and returned to ready signed-in state without replacing the live
tunnel.

The same installed stack later crossed a real suspend/resume cycle. Core
reported one timeout while Ethernet reacquired DHCP, deleted the stale profile,
then created exactly one replacement profile. Protun reported that no secrets
were needed and established the tunnel in the same second. The final state had
one Proton VPN profile, one `proton0` tunnel, one kill-switch profile, Proton
DNS scoped to the tunnel, and IPv4/IPv6 policy routes with unreachable
fallbacks. A later liveness probe recovered immediately without duplicating or
replacing the tunnel.

The locally built `proton-vpn-kde-0.11.2-26.fc44.x86_64` package passed:

- all 130 backend tests and all 36 CTest tests during RPM `%check`;
- RPM payload, dependency, root ownership, mode, systemd, D-Bus activation,
  community-reporting gate, digest, and transaction inspection;
- installation and host-level RPM verification with the repository-built
  `python3-proton-keyring-linux-0.2.3-4.plasmavpn1` package installed;
- normal D-Bus activation of the Control Center, backend, and resident agent;
  and
- maintainer acceptance of the intended client behavior after the internal
  adapter, QML, location-model, and controller decomposition.

The earlier `0.11.2-24.fc44` package authenticated with KeePassXC owning
`org.freedesktop.secrets`, reached ready signed-in disconnected state without
the official desktop client, and verified automatic backend reactivation,
client reauthorization, lease restoration, and return to ready state after a
deliberate service stop.

The earlier `0.11.2-8.fc44` security-remediation package additionally passed an
unauthorized `UpdateSettings` rejection and confirmation-gated KRunner
connection and disconnection, with NetworkManager returning to a disconnected
state. Those earlier observations remain historical evidence; they are not
represented as a fresh `-26` connection test.

This remains release-candidate evidence, not a substitute for signing the exact
tagged artifacts and completing the publication steps in
[Releasing](RELEASING.md).

### Performance regression check

An isolated disconnected 0.11.3 demo stack measured 21.5 MiB backend PSS,
4.7 MiB resident-agent PSS, and 50.3 MiB Control Center PSS: 76.5 MiB combined.
The current server-search projection retained about 2.63 MiB of traced
allocation, and measured query medians remained between 0.205 ms and 5.667 ms.
These tests found no material regression from the reconnect or security
controls. They are not live connected-session measurements; full methodology
is in [Performance](PERFORMANCE.md).

## Public 0.11.3 holistic review result

The complete Hostile, Subtractive, Entropy, Error-Class, HPC/Performance, and
Hardening/Security battery was repeated on 2026-08-31 for the 0.11.3 release
candidate. It produced no new open finding.

### Hostile

Malformed signatures, unexpected descriptors, unauthorized senders, false
sender claims, secret replay and tampering, oversized inputs, settings
allowlists, rollback failures, capture stop races, support limits, and service
lifetime and owner-generation transitions were exercised. The new reconnect
path was also checked across a sleeping network, absent Protun secret agent,
backend replacement, and a still-active NetworkManager tunnel. No open
release-blocking hostile-input defect remained after remediation.

### Subtractive

The client builds without optional direct status-notifier integration, runs
tests without official Core through the demo adapter, and keeps support and
crash submission removable through synchronized build capabilities. No
duplicate VPN protocol, NetworkManager, kill-switch, split-tunneling,
server-construction, or session-persistence implementation was found. The
reconnect correction remains a four-line behavior patch inside the existing
official Protun profile construction; it does not add a community secret agent
or alternative connection path.

### Entropy and drift

Release metadata, documentation links, static-analysis policy, ignored debris,
generated D-Bus contracts, overlay manifests, patch hashes, permitted payload
paths, and resulting file hashes are mechanically checked. No tracked build
output, local package, credential, diagnostic, or machine-specific artifact was
found. The final tag must still be created from a clean, reviewed tree and its
exact source archive; assessment digests are not release signatures.

### Error class

Public failures use a bounded, stable vocabulary. The review checked resource
and state postconditions in addition to exception types, including stale
signed-in state after backend loss and the bounded manual service retry. No
public-baseline release-blocking error-class defect remained.

### HPC and performance

Authorization state, D-Bus checks, support bounds, and capture lifecycle state
remain bounded. The complete native suite passed under address, leak, and
undefined-behavior sanitizers, and all production C++ translation units passed
Clang-Tidy. The isolated 0.11.3 stack measured 76.5 MiB combined PSS, while
search medians remained from 0.205 ms through 5.667 ms. Connected official Core
memory remains dependent on server data, imported backends, and live
NetworkManager state.

### Hardening and security

The current controls preserve the most important same-session trust boundary
without taking networking ownership from Core. The 2026-08-31 standard audit
reviewed eight security surfaces and found no new reportable issue. Installed
Fedora binaries retain PIE, non-executable stacks, GNU RELRO, and immediate
binding. The services intentionally omit mount-namespace controls that prevent
required peer verification under Fedora SELinux; this tradeoff and the 9.0
systemd heuristic score remain documented in [Hardening](HARDENING.md).

## Residual risk and follow-up

- The project has not received an independent security audit. External review
  of service identity, sender authorization, and authentication transport is
  desirable before a stable or security-reviewed claim.
- Executable-path, unit, environment, and unique-owner checks protect against
  ordinary or sandboxed session peers, not arbitrary native code already
  running as the desktop user or injected into an allowed process. Shared hosts
  such as KRunner therefore remain outside backend trust. A stronger same-UID
  boundary would require a materially different privileged or MAC-enforced
  service architecture.
- Any same-session process can request a bounded connection confirmation dialog
  through the exposed desktop brokers. It cannot silently mutate VPN state
  through that path, but it can create a presentation nuisance.
- Qt and Python cannot guarantee immediate erasure of every immutable secret
  copy. Root, debuggers, and arbitrary same-user native code with process-memory
  access remain out of scope.
- Official Proton Core, NetworkManager, Secret Service providers, and remote
  Proton services are trusted dependencies outside this assessment.
- The verified provider-neutral Secret Service behavior depends on a separately
  patched Proton keyring package. Its exact upstream source, patch hashes,
  focused tests, Fedora spec, and source/binary CI build live in this repository.
  The adapter requires a same-user provider and pins all traffic to its unique
  owner, but the portable Secret Service and D-Bus APIs cannot prove the
  executable behind a non-dumpable initial provider. Desktop provider selection
  is therefore a platform trust boundary rather than an authenticated package-
  provenance claim. The overlay remains an unofficial downstream dependency
  until Proton accepts equivalent changes; stock Proton 0.2.3 must not be
  described as KeePassXC-compatible or owner-pinned.
- The Fedora API-Core overlay keeps Protun's transient private key in
  NetworkManager's unsaved profile rather than a desktop secret agent. Fedora
  may materialize that profile as a mode-0600 file under volatile `/run` while
  the tunnel exists; live verification confirmed the `UNSAVED` flag and
  deletion on disconnect. Root, NetworkManager, and disk-backed swap remain
  outside the project's protection boundary. The exact vendor RPM, patch,
  permitted path set, resulting hashes, and behavior are independently
  verified so an equivalent upstream fix can replace the overlay.
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

## 2026-08-31 release re-review record

This record describes the public `0.11.3` no-findings re-review. It is separate
from the unreleased `0.12.0` gate above and the historical finding record below.

| Field | Release re-review |
| --- | --- |
| Date | 2026-08-31 |
| Project version | 0.11.3 release candidate |
| Reviewed runtime revision | `1242f2ad8095715a016ddca9a8f2aeba9508126c` |
| Working-tree snapshot | `codex-security-snapshot/v1:sha256:7f0eda03c458b5aec9598a5e3cd366762a3c7bb12ee7663de773b024f1fc1441` |
| Canonical scan ID | `f1444f01-a3d0-4199-83c9-4a37c5f3b6c5` |
| Source inventory | 281 files |
| Reviewed surfaces | 8 of 8 complete |
| Result | No candidate or reportable finding; no deferred surface |
| Package evidence | `0.11.3-1.fc44` candidate built from release-metadata commit `6be0e9d` |

The source scan was sealed against the runtime hotfix revision. The subsequent
commit changed release metadata and documentation, not runtime code; its exact
package candidate supplied the package evidence above. Independent delegated
reviewers were unavailable under the active review policy, so one reviewer
performed sequential architecture and full-surface passes. This is therefore a
maintainer-directed, AI-assisted assessment rather than an independent audit.

## Historical finding record — all closed

This section records what the assessment found before remediation. Every entry
below is closed in the public `0.11.3` baseline and remains covered by current
regression tests.

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
later KRunner correction and packaged acceptance for `0.11.2-8`, `0.11.2-24`,
and `0.11.2-26` occurred after the sealed re-audit snapshot and are identified
by current source, tests, and package evidence rather than by rewriting that
historical digest.
