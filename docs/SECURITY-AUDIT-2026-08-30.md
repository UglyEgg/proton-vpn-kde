# Security and engineering assessment — 2026-08-30, refreshed 2026-09-08

## Current assessment posture

The original `0.11.3` assessment closed its seven recorded issues: one high,
four medium and two low severity. Their original failure modes no longer
reproduced in focused tests, and the 2026-08-31 re-review found no new
reportable issue. That historical result is not a claim about findings from
later assessments. The current R1–R8 review and correction concern the
unreleased branch; applicability to older public releases was not assessed in
this bounded series.

The accepted `0.12.0` mechanics add event-driven backend lifetime and an
on-demand Connection Inspector. Their pre-final isolated reviews and standard
security scans found lifecycle, error-class, Secret Service identity,
desktop-action-broker, and inherited native-loader environment defects. The
historical section below records each remediation and the final gate without
presenting those closed findings as current vulnerabilities.

The unreleased `0.13.0` branch is a presentation-led redesign over those
accepted mechanics. Review has also admitted narrowly scoped recovery and
asynchronous state-ownership corrections where the new presentation exposed a
real defect. These corrections do not alter Proton Core, VPN protocols,
NetworkManager behavior, or the authentication protocol.

**Current source decision: the seven-isolated-reviewer battery at `4d6b5f2`
required seven P2 corrections and one P3 correction. The bounded patch series
through `5a34639` implements all eight and passes the bounded verification
gates. Independent final release approval and installed UAT remain pending.**
The current R1–R8 register below supersedes earlier candidate decisions. This
is not release approval. No P1 was substantiated in this bounded review, but
partial security coverage cannot exclude undiscovered defects. Subtractive and
Cognitive Load/Code Maintainability required no changes.

The refactor uses hash-checked actual Core **5.6.10** with external I/O replaced
for conformance tests. The older 5.5.6 static API check is not evidence of a
current runtime defect. No live VPN, credential prompt, installed package,
GitHub operation or publication was exercised during the source-review cycle;
subsequent package installation and visual UAT work are recorded separately below.

**Version `0.13.0` remains explicitly not release-ready until all seven isolated
reviewers pass one exact remediated
commit, its binary/source package set repeats the release battery, live
acceptance succeeds, and the planned local soak completes.**

The current battery adds **Cognitive Load/Code Maintainability** to Hostile,
Subtractive, Entropy, Error-Class, HPC/Performance and Hardening/Security.
Each perspective has its own isolated reviewer. The seventh review checks
unnecessary abstraction, duplicate ownership, hidden control flow and the
cost of understanding and changing the implementation. References to six
reviewers in historical records describe the earlier process, not this gate.

The pre-remediation `0.13.0` snapshot `1d88e35` passed Mypy, Ruff, all 35
production translation units under Clang-Tidy, 215 backend tests at 82%
measured branch coverage, and all 38 CTest targets both normally and under
address, leak, and undefined-behavior sanitizers. Its binary/source RPM set was
byte-reproducible, both overlay pairs passed their package policies, and the
combined transaction test succeeded. These results are retained as
pre-remediation evidence and must be repeated on the exact final commit; they
do not substitute for live acceptance or soak gates.

The public `0.11.3` source passed Mypy, Ruff, Clang-Tidy across all 34
production translation units, and the complete native test suite under address,
leak, and undefined-behavior sanitizers. At that historical checkpoint, Fedora
package `0.11.2-29.fc44` contained the 0.11.3 hotfix code and passed host-level
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

- **Current assessment posture** and **Current 0.13.0 error-class review**
  describe the unreleased branch and its open work. This current register takes
  precedence over candidate-remediation statements in the historical rounds.
- **Historical 0.13.0 remediation rounds** records superseded partial reviews;
  a proposed or implemented candidate correction there is not release approval.
- **Historical 0.12.0 isolated review gate** records superseded review cycles
  and closed findings; it is not a list of current vulnerabilities.
- **Current controls**, **Verification**, and **Residual risk** describe the
  source controls shared by the public baseline and current branch; versioned
  package evidence is labeled separately.
- **Historical finding record** is the authoritative status record for the
  original seven security findings. Every listed finding is closed; the
  retained descriptions concern earlier snapshots and must not be read as
  current vulnerabilities.
- Snapshot identifiers document what was reviewed; they are preserved in their
  tool-generated form and are not release signatures.

## Current 0.13.0 error-class review

### Current bounded seven-review correction register — 2026-09-08

Reviewed baseline: `4d6b5f28615f2e4b1543b292879bd1e6b8a42a88`. Each of the seven
perspectives used a separate fresh-context reviewer. The maintainer authorized
one bounded correction series, not a new discovery/refactoring cycle.

| ID | Finding | Implemented correction and regression evidence |
| --- | --- | --- |
| R1, P2 / medium security | Incoming descriptors could lose ownership on ignored bus routes. | `83adae0`: connection-wide cleanup is installed before connecting, permits adoption only after export, and remains through disconnect. Disposable descriptor tests cover ignored calls/signals/replies, all protected consumers and aliases, revocation, shutdown and repeated cleanup. |
| R2, P2 | Backend loss fabricated a disconnected tunnel and notifications. | `bbcf1ab`: unavailable observation is explicit; notification baselines reset across gaps, and tray status does not claim a known connection. A surviving simulated tunnel remains connected while the observer becomes unavailable. |
| R3, P2 | Transient authorization/snapshot failures stranded the resident agent. | `bbcf1ab`: three owner-scoped retries at 250/500/1000 ms; healthy observations cancel read retries, not outstanding authorization. Permanent rejection stays closed. Tests cover retry exhaustion, unsolicited signals, quiet-owner recovery and no mutation replay. |
| R4, P2 | A failed secondary read reclassified a committed settings write as rejected. | `f2fcc3b`: DNS and split-tunneling saves publish/return their confirmed result; secondary refresh failure is separate guidance. Tests cover both families, primary rejection and account expiry during refresh. |
| R5, P2 | Application-autostart guidance bypassed tray-only preferences via `--show`. | `770525a`: both settings surfaces specify the preference-respecting command without `--show`. Startup tests preserve explicit launcher/settings requests and all tray/preference combinations. No autostart is enabled automatically. |
| R6, P2 | Synchronous activation/identity RPCs blocked frontend event processing. | `bbcf1ab`: asynchronous discovery and verification retain every identity check and reject stale generations. Private-bus tests cover an already-running unactivatable owner, delayed metadata with a heartbeat, deadline, destroyed context and late owner completion. |
| R7, P2 | RPM mandatory checks used undeclared ripgrep. | `5169bb9`: explicit BuildRequires plus a guard against its removal. Spec query and QML hygiene gate pass; a clean buildroot remains a package-validation gate. |
| R8, P3 | A blocked route probe could retain its child after cancellation. | `d87c7c5`: three-second probe deadline, bounded terminate/kill escalation and owned cleanup. Tests cover timeout, cancellation during spawn/wait and an ignored terminate. |

R1 security scan `cc22793f-68ac-4017-ad09-b7b74e048ec5` is sealed separately:
**67/326 paths fully security-reviewed, 259 not fully reviewed in that scan**.
Earlier scans' coverage must not be silently combined with this revision.
Its impact was bounded local availability, not demonstrated secret disclosure,
privilege escalation or tunnel-protection bypass. Validation used harmless
ownership fixtures, not a live exhaustion or exploitation workload.

The security-fix procedure used a fresh boundary investigator and one fresh
candidate reviewer. That reviewer identified the remaining pre-connect interval;
the parent confirmed it, closed it and added lifecycle-order regression checks.
The original scan and review outputs remain historical evidence, not rewritten
as an independent approval of the final patch.

Verification of the source candidate `5a346394a8529edc6f7b6df100d4e07f335a333a`:

- **41/41 CTest targets pass normally and under address/leak/undefined-behavior
  sanitizers**, including private-bus, QML, staged-install and negative
  candidate-seal fixtures.
- **439 Python 3.14 tests pass without skips**, including the hash-pinned actual
  Core 5.6.10 conformance fixture. Mypy passes for 31 files; branch-aware
  coverage is 86%. Python 3.11.15 with minimum dbus-fast 2.20.0 passes the same
  suite with eight documented compatibility/opt-in skips.
- **35 production C++ files pass Clang-Tidy**. Ruff, ShellCheck, contract and
  translation provenance, documentation links, candidate seals, RPM dependency
  rejection and exact-commit source archive reproducibility pass.

The native aggregate's backend job does not enable the five opt-in Core cases;
the separate no-skip Python run above covers them. One positive root-ownership
test skips because the sandbox remaps host ownership. At that source checkpoint,
real-host ownership, fresh RPM/SRPM builds and a clean package buildroot had not
been verified. Subsequent package and host checks are recorded separately below.

The first validation pass exposed a supported manually started service without
an activation file; discovery now queries ownership before requesting activation.
The corresponding private-bus test and affected UI smoke tests pass. One
Clang-Tidy callback-copy diagnostic was corrected and the entire gate rerun.
The committed candidate-seal negative fixture also passes. These were bounded
patch-validation corrections, not another repository-wide discovery cycle.

No new full scan, Core/networking change, installed-client operation or GitHub
operation was part of this series. Package validation, installed UAT, final
independent approval and soak are separate gates. Optional
subtractive/maintainability ideas are deferred, not additional required fixes.

### Package and local-install checkpoint — 2026-09-08

The immutable package source is
`9f26ba2cdf3b07e2850a799f2777496a7775b328`. Its changes after the source
candidate above are documentation-only. No runtime correction was added during
packaging.

- All six binary/source artifacts were built and content-verified: client
  `0.13.0-0.1.fc44`, keyring `0.2.3-8.plasmavpn1.fc44`, and API Core
  `5.6.10-10.plasmavpn1.fc44`. The artifact manifest binds their SHA-256
  digests to that exact commit. These are unsigned local UAT artifacts.
- Two fresh client builds under the same normalized build path produced
  byte-identical RPM, SRPM, debuginfo and debugsource outputs. Both mandatory
  `%check` runs passed all 40 archive-eligible CTest targets and the 439-case
  Python suite with five opt-in Core cases skipped. The history-dependent
  candidate-seal test is intentionally checkout-only; it and the five Core
  cases passed in the source verification above.
- The keyring's 29 tests passed. API Core passed signed-input, exact-payload,
  behavior and source-content verification. Native executables and KDE plugins
  retained PIE/shared-object layout, full RELRO, immediate binding and a
  non-executable stack. Direct support and crash submission remain disabled.
- The extracted client RPM passed a private-bus demo with disposable settings
  and activation disabled. The three-package upgrade passed dependency and
  conflict checks using a copied host RPM inventory. Only the sandbox's
  misleading disk-space check was excluded from that dry run; the subsequent
  real-host install performed the normal check.

With maintainer approval, the three binary RPMs were installed locally.
Root-side `rpm -V` passed without differences for all three packages. The
installed source marker matches the commit above, the executable reports
`0.13.0`, and the resident agent restarted on the installed binary. The
backend and Control Center remained stopped; the existing unrelated connection
was unchanged. The previous client RPM was retained for rollback.

The native identity test was also repeated on a private bus outside sandbox
UID remapping: **12 passed, zero failures or skips**, including the actual
root-owned Fedora systemd drop-in. This closes the ownership-fixture gap,
but does not prove live backend authentication or session restoration.

**Still pending:** clean-environment Fedora validation (these were local-host
builds), live sign-in/Secret Service and backend-identity acceptance, navigation
and settings UAT, connection/suspend/capture lifecycle acceptance, final
independent release approval, and the required one-week immutable-candidate
soak. Installation alone starts neither release approval nor the soak clock.
No tag, push, public release or signing operation occurred.

### Visual UAT corrections — 2026-09-08

Maintainer screenshots exposed three presentation defects after the `0.1`
installation: a split-tunneling banner disconnected from the route graphic,
report fields overflowing their card, and a generic Plasma task-manager icon.
The `0.13.0-0.2` candidate draws the split route with a clickable Internet
branch, bounds and wraps the inactive reporting form, and gives the desktop
icon a unique name. The installed Papirus theme resolved `plasma-vpn` to its
unrelated `plasma` icon; a staged unique-name lookup resolved the correct SVG.
Backend, Core, network behavior and disabled reporting policy are unchanged.

All **42 native test targets pass**. The new presentation fixture passes
separately under address/leak/undefined-behavior sanitizers; the complete
sanitizer-suite result above belongs to the earlier source candidate. Compact,
reported-width, wide, 1.5x text and RTL report cases remain within their card
and cannot submit. Connected/disconnected split-route cases verify visibility
and navigation. Light/dark rendered fixtures were inspected. Static checks
and the explicit mechanics-boundary seal pass. These are bounded regression
results, not another independent seven-review approval.

The client RPM/SRPM were built from `620a87c467a6465a56f58457b8242869199a4466`
with mandatory checks enabled: **41/41 archive-eligible CTest targets pass**,
and the 439-case Python suite passes with its five opt-in Core cases skipped.
Artifact policy, exact source/spec content, disabled-reporting flags and the
packaged icon's byte identity all pass. These are unsigned local-host UAT
packages, not clean-buildroot or repeated-binary-reproducibility evidence.

With maintainer approval, client `0.13.0-0.2.fc44` was installed on 2026-09-08
after all three Plasma VPN services were confirmed stopped. Root-side
`rpm -V` passed without differences; the installed source marker matches
`620a87c467a6465a56f58457b8242869199a4466`. Plasma's application cache was
refreshed, and the host icon resolver selects the installed
`quest.entropy.PlasmaVPN.svg`, whose bytes match the source artwork. The
agent, backend and Control Center remained stopped after the upgrade; no VPN
connection was requested. Core/keyring packages were unchanged, and the prior
`0.1` client RPM remains available for rollback. Installed visual acceptance
is still pending and remains separate from package verification and release
approval.

The follow-up `0.13.0-0.3` source candidate implements the approved horizontal
layouts, endpoint-local metadata and smooth arrow-free split route. A small
shared window component fixes minimum/maximum dimensions to the app-selected
size, with per-monitor work-area bounds and no maximize control. Connection
fits measured content; longer secondary pages scroll. No backend/Core,
networking, authentication or reporting-policy code changes in this follow-up.
All **42 native targets pass**, including the 439-case backend suite with its
five opt-in Core cases skipped. The expanded **14-case presentation fixture**
also passes under address/leak/undefined-behavior sanitizers: fixed sizing,
grow/shrink and screen-bound transitions, stable centered nodes, large text,
long optional metadata and unchanged fact actions. The native transition
checks reject layout warnings; the offscreen harness admits only Qt's exact
unsupported-size-hints notice, not application diagnostics. The eight-image
visual matrix passes, and additional light/dark content-sized captures were
inspected (764×524 full route, 764×643 split route on the offscreen monitor).
Presentation drift seals pass with backend/Core seals unchanged. These are
bounded regression checks, not a new independent release-review battery.

The `0.13.0-0.3.fc44` client RPM/SRPM were built from
`58b3d83dbd27d11cce3d332ef3412929661d823f` with mandatory checks enabled:
**41/41 archive-eligible CTest targets pass**, and all 439 backend cases pass
with the five opt-in Core cases skipped. Artifact policy and exact
source/spec/commit checks pass. These are unsigned local-host UAT packages,
not clean-buildroot or repeated-binary-reproducibility evidence.

With maintainer approval, the `0.13.0-0.3.fc44` client was installed through
KDE/PolicyKit after all three client services were confirmed stopped.
Root-side `rpm -V` passes without differences, and the installed source marker
matches `58b3d83dbd27d11cce3d332ef3412929661d823f`. The agent, backend and
Control Center remain stopped. Existing network connections are unchanged;
no VPN connection was requested. The `0.2` client RPM is retained for
rollback. Core/keyring packages were not rebuilt or changed, and no tag,
signing, push or public release occurred. Installed KWin/monitor/visual
acceptance remains pending and is separate from package verification and
release approval.

### Historical a2b3d5e review checkpoint

The following RC/VAL register records the preceding cycle. It is not the
current R1–R8 status register above.

### Seven-perspective review — 2026-09-08

Reviewed commit: `a2b3d5e945dc46d92838a9979f0b25805b86e801`.
All seven independent results were collected before source edits. The table
lists engineering defects, not demonstrated security vulnerabilities.

| Item | Finding and affected invariant | Correction status |
| --- | --- | --- |
| RC-01, P2 | Settings signals could clear request ownership; old replies lacked a request generation. | Candidate corrected across VPN, split tunneling and DNS. Data-only parsing, typed request state and retained unknown-write readback have three-family private-bus and model tests. |
| RC-02, P2 | Observed state/retirement was confused with request acknowledgement. | Corrected and regression-verified at `1a2366e`: no synthetic acknowledgement or duplicate QML settlement; unconfirmed settings results survive readback; failed/unconfirmed capture-Start guidance survives active snapshots. Final independent approval remains a separate gate. The failed earlier attempt is historical below. |
| RC-03, P2 | Early logout journal/settings failure retained an internal fence without publishing recovery. | Candidate publishes the fence for replace, directory-sync and early settings failures; tests preserve partial handoff records and reject replacement credentials. |
| RC-04, P2 | Unrelated operation messages could replace degraded-background recovery guidance. | Candidate derives stable guidance from degraded state while preserving stronger diagnostics; backend and presentation tests cover message changes. |
| RC-05, P2 | Repeated searches could accumulate accepted reads behind a blocked provider; debounce and stale filtering were not admission bounds. | Candidate adds eight shared browsing/settings slots and latest-query native coalescing. Tests cover saturation, cancellation-resistant reads and queued settings withdrawal. Not a measured ordinary-session leak. |
| VAL-01 | The negative mechanics fixture searched for a retired blanket-busy expression. Exact committed tests were 39/40, not the earlier dirty-tree 40/40 claim. | Corrected: the fixture verifies its capability-check mutation, and exact `7d4d030` passes 40/40 targets normally and under sanitizers. |

Dispositions on that commit: **Hostile, Entropy, Error-Class and HPC/Performance:
changes required; Subtractive and Cognitive Load/Code Maintainability: pass;
Hardening/Security: no reportable finding within partial coverage, not full
approval.** Correction verification must name its own revision.

The seventh reviewer found the existing ownership primitives justified.
Optional follow-ups are broader typed native request context, guaranteed reset
of older shared test fixtures, deriving the capture-start reference from its
owner, removing a test-only watchdog shim, and lazy application discovery.
None warrants another broad refactor or is a demonstrated security defect.
New delayed-reply fixtures use scope guards; the stale Disconnect comment is
corrected.

Standard security scan `a4be8b25-6bc5-4b6a-bd3a-840eef70a627` completed with
**240/325 files covered, 84 deferred and one historical report excluded**.
Canonical manifest, coverage, findings, report and SARIF artifacts are retained
outside the source tree. Runtime backend/native/QML/runner/KCM paths and native
tests were covered; deferred test/tool/document/image files prevent full
repository approval. Questions about confirmation text rendering, tray remote
dispatch, off-path UnixFD ownership and provider-authored errors did not
establish a reportable source-to-impact path; they remain unproven, not closed
vulnerabilities. External Core, NetworkManager, Secret Service identity and
installed filesystem behavior remain runtime validation boundaries.

Two non-vulnerability observations: Fedora requires the API-Core overlay's
compatibility capability (its optional README wording is corrected), and
direct repository switching through `pkexec` may conflict with the Control
Center service's `NoNewPrivileges` policy. The installed launch path needs
acceptance testing; no privilege policy was weakened.

Baseline evidence on `a2b3d5e`: 428 Python 3.14 tests including five opt-in,
hash-pinned actual-Core cases; Python 3.11 with eight expected skips; Mypy for
31 files; 86% branch-aware coverage; 35 production Clang-Tidy units; source
archive reproducibility; and 39/40 native targets normally and under sanitizers
(VAL-01 only). Six demo layouts were inspected, but device scaling is not
independent 1.5x text validation. These are development results, not
exact-correction package, live-UAT or soak evidence.

### Error-class correction — resumed by maintainer on 2026-09-08

Scope is the shared request-result evidence contract in
[architecture](ARCHITECTURE.md#request-result-evidence-contract), not another
repository-wide discovery/repair cycle. The maintainer requested correction of
the class after the explicit stop at `7d4d030`. No new protocol, Core rewrite,
live reproduction, installation or security-scan round is part of this work.
The correction is committed at
`1a2366e069ce137c8d5dd6225c6c14abc64650bd`.

Before production edits, the new tests reproduced one same-state switch false
acknowledgement, all three settings readbacks losing unconfirmed guidance, both
capture-Start diagnostic losses, and 16 QML state/order feedback failures.
These are sibling manifestations of the same evidence-confusion class, not
new security vulnerabilities. The implementation removes state-derived request
acknowledgement instead of guessing success from a server name or message.

The native timeout matrix covers all seven Connect methods plus Disconnect,
two admitted starting states per route, both settled states and diagnostic
presence. QML tests independently vary state, target, acknowledgement and
event order. Existing ownership, cancellation, identity, cleanup and backend
conformance tests remain required. Passing this bounded check does not inherit
the earlier independent review approval or certify the entire codebase.

Correction verification at `1a2366e`: all six focused test targets pass,
followed by **40/40 complete CTest targets normally and 40/40 under
address/leak/undefined-behavior sanitizers**. The private-bus and QML matrices,
settings-family readbacks, capture cleanup, ownership and stale-reply tests are
included in those targets. Static analysis, generated-contract/provenance
checks, documentation links, the candidate-drift gate and exact-commit source
archive reproducibility also pass. No installed or live-VPN result is inferred
from these tests.

All **35 production C++ units pass Clang-Tidy**. The unchanged backend passes
**431 tests with no skips**, including hash-pinned actual-Core 5.6.10
conformance with external I/O replaced; Mypy passes for 31 source files and
branch-aware coverage remains 86%. This closes implementation and regression
verification of the inventoried evidence-confusion class, not every possible
asynchronous defect. No new security or seven-perspective scan was launched.
Independent final approval, exact-candidate packages, installed acceptance and
soak remain pending; the bounded correction stops here.

### Historical correction checkpoint — stopped at `7d4d030`

The grouped correction commit is
`7d4d030ea92aa22a186826b0d338732075f61e53`. It passes 431 backend tests on
Python 3.14 with hash-pinned actual Core 5.6.10 conformance, the Python 3.11
suite with eight documented skips, Mypy across 31 files, 86% branch-aware
coverage, all 40 native targets normally and under address/leak/undefined-
behavior sanitizers, 35 production Clang-Tidy units, static checks and
exact-commit source archive reproducibility. Those passes did not close RC-02
at that revision.

Independent bounded correction checks: HPC/Performance and Cognitive Load/
Code Maintainability **pass**; Error-Class **changes required**. The security
supplement reported no concrete required repair in the correction and reviewed
75 previously deferred paths fully, with nine remaining limited-scope. This
supplements, rather than rewrites, the canonical partial scan. It is not a
second complete seven-perspective approval or an independent certification.
Including the new request-state header, cumulative full/security-inspected
coverage is 316/326 paths, with the historical assessment excluded. Limited
coverage remains in the two large controller/adapter test files, changelog,
roadmap, license and four PNGs; source/test inventory or asset identity is not
an exhaustive review of those paths. The supplement's source-integration
recommendation cannot override the separate open Error-Class defect.

**RC-02 consequence at that stopped revision:** `VpnControllerSnapshot.cpp:247-250`
compared only the reconciled state with `connected`. A server switch is allowed while
already connected; target resolution or pre-connect configuration can fail
without removing the old tunnel. An ambiguous method reply followed by fresh
idle-but-still-connected state therefore emitted success with an empty error.
`ConnectionActionFeedback.qml` suppressed the failure warning. This was a
source-confirmed UI correctness defect, not a demonstrated tunnel/protection
failure. No live fault reproduction was attempted.

**Why that correction missed it:** its native timeout matrix started Connect
from disconnected and Disconnect from connected, then completed in the opposite
state. It proved ownership retention, but not same-state failed replacement.
State/retirement evidence and request success were still conflated. The test
matrix needed initial state, requested intent, outcome and event ordering as
separate dimensions; the resumed correction above adds them. Most findings
in this batch are community-layer ownership/projection defects, not evidence
that Proton's Python implementation caused them. Core's incomplete public
refresher-join contract remains a separate documented dependency limitation.

On the maintainer's 2026-09-08 stop instruction, no further repair or scan
round was started. Existing checks were closed out and the finding recorded.
The maintainer subsequently authorized the bounded error-class correction
recorded above. The code remains on the local feature branch; no install, push,
package release or soak acceptance is claimed.

### Historical refactor checkpoint — baseline `7d1f1b3`

The following records the earlier refactor and its local tests. Candidate-fix
statements here are historical evidence, not the current defect register or
final approval; the seven-perspective register above takes precedence.

The baseline is frozen at `7d1f1b3`. Discovery now includes independent hostile,
subtractive, entropy, error-class, performance and security perspectives. The
standard security scan reviewed the 317-file source scope and reported one
additional medium-severity authorization finding under the documented local
session-peer threat boundary. Its validation was static; no live exploitation
or VPN mutation was performed. This is a baseline assessment, not a security
approval of the subsequent edits.

| Item | Current working-tree status | Evidence / remaining gate |
| --- | --- | --- |
| EC-02 | Candidate fixed | Shared `join_owned` retains provider and caller outcomes separately. Direct tests cover child success/error/cancellation, repeated caller cancellation, cancellation-hook failure and already-complete work. No detached provider exception is logged by the helper on Python 3.14. |
| EC-04 | Candidate fixed | Timeout has a distinct completion-unknown disposition; control operations reconcile without declaring owner loss. Native fake-backend test confirms continued availability and a state refresh. |
| EC-06 | Candidate fixed | Page retirement dispatches retained parent refreshes. Test covers a pending read, context release, successor completion and a late obsolete reply. |
| EC-07 | Candidate fixed | `OperationCompletion` retains reconciliation through a busy read and later idle signal; tests include signal-before-reply, successor isolation and exactly-once lease settlement. |
| EC-01 / PV-013-036 | Candidate fixed | Public Down is required even from observed Disconnected; completion state is captured inside the provider task. Queued promotion identity failure remains unconfirmed and forces terminal exit. Three actual-Core 5.6.10 conformance cases pass with external I/O replaced. Final route review and installed acceptance remain required; no Core logic was changed. |
| EC-03 | Candidate fixed | Public callback is installed before enable. One owned worker plus one coalesced classified notice rechecks account/binding after authentication-lock acquisition. Auth failures expire the session; other failures show persistent degraded updates without disconnecting or automatic replay. Shutdown fences and joins this handler, not Core's children. Provider-free tests and two actual-Core scheduler cases pass; installed acceptance and final independent review remain open. |
| EC-05 | Candidate fixed | One native capability policy separates Connect from cancellation/cleanup across GUI, Agent, browser, pins, tray, shortcuts and confirmations. Explicit Disconnect covers pending lookup before Connecting and remains available after expiry; acceptance rechecks current permission. Invalid or unreadable snapshots block dispatch. Matrix, private-bus client and offscreen confirmation tests pass. Installed surface acceptance and final independent review remain open; backend cleanup admission is still separate. |
| Backend authorization boundary | Locally remediated, release/package verification pending | Ingress and shared export guards now enforce the generated policy consistently, including queued-call revocation and descriptor ownership. Authorizer-free service mode was removed. One fresh independent bypass/regression review found duplicate test imports, which were corrected; no surviving source-backed bypass was reported. |
| Disconnect-and-quit fast path | Candidate fixed | Entry and later updates share the native policy's available, ready, healthy, idle-disconnected predicate. Native tests reject unavailable, busy-disconnected and unreadable-state cases, both on entry and while awaiting completion. |
| Account/tunnel attribution | Candidate fixed | After refresh services start, replacement login requires a fresh process. A private non-secret handoff records tunnel retirement; fresh startup checks outgoing-process exit and clears the saved account before accepting credentials. Expiry preserves an established tunnel until explicit preparation. Native fake-service, adapter handoff and real pidfd tests pass; installed systemd/Secret Service/NetworkManager acceptance remains open. This is an engineering lifecycle finding, not a demonstrated credential disclosure. |
| Retry ownership | Consolidated locally | The optional direct Core mutation/compensation fallback is removed. Attempt and account-lifecycle callbacks are mandatory; production already used the shared owner. The constructor regression failed before the change for all eight missing/invalid callback cases and passes afterward. Policy tests forbid direct Core Up/Down; adapter tests cover stale account/intent at lock admission and after success. This is subtraction of an alternate implementation, not a new networking policy or evidence of a deployed bypass. |
| Independent cleanup admission | Candidate fixed | One session-tagged worker per cleanup kind coalesces callers and retains ownership through caller cancellation. Stop bypasses unrelated foreground work; Down is accepted but waits for non-connect transactions to avoid racing Core settings/protection changes. Final Stop/Down dispatch serializes and revalidates the account; successor mutations cannot overtake cleanup. Controller timing cases, a combined controller/adapter ordering test and eight offscreen capture-button cases pass. This is not an immediate-completion guarantee; installed acceptance and final independent review remain open. |
| Close deadline consolidation | Candidate fixed | Service, controller and adapter inherit one absolute deadline. Repeated/cancelled callers share the first close outcome. Capture Stop consumes remaining shutdown time without resetting durable capture limits. Accepted teardown remains owned on expiry, later stages recheck the deadline, and failed close cannot re-arm retries or become success after late completion. Propagation, sticky-outcome, blocked-scope, capture recovery and retry-fence tests pass. Existing process/systemd bounds remain; installed acceptance and final independent review are pending. |
| Cleanup-request deadlines | Candidate fixed | One 30-second budget starts at controller admission and flows through dependency waits, dispatch and adapter retirement. Pre-dispatch expiry rejects the request without cancelling prior work or issuing cleanup later; duplicate callers cannot reset its deadline. Adapter connection-scope expiry or an unconfirmed provider retirement uses the existing nonzero process boundary. Capture Stop retains its live provider task and recovery journal. Controller/adapter integration, scope and D-Bus tests pass; no live exit, capture or networking was tested. |
| Foreground end-to-end deadlines | Candidate fixed | One 180-second controller budget spans admission, provider work, recovery and state publication. Admission expiry rejects without disturbing preceding work. A whole-transaction child retains auth/settings results through caller cancellation; connect, capture Start and FIDO retain explicit cancellation cleanup. Nested recovery stages join their accepted writes instead of detaching them. Unconfirmed expiry fences new work and uses the existing nonzero process boundary. Installed acceptance and exact-candidate independent review remain required. |

The repeated authentication/connection lock ownership implementation was
replaced by task-scoped ownership with acquisition-bound child delegation.
Controller admission remains separate. Scope tests cover siblings, expired
delegation, cancellation before first execution and eager task startup.

Verification at this checkpoint includes both modeled lifecycle orderings and
the exact installed Core 5.6.10 event/state source. The opt-in conformance
harness verifies source hashes, constructs neither the live API nor
NetworkManager, and replaces external I/O. It is local evidence, not an
implicit CI pass. All 428 backend tests pass on system Python 3.14 with that
fixture enabled; branch-aware coverage is 86%. The hash-pinned Python 3.11
minimum environment passes with eight skips: the five opt-in Core cases,
two eager-task cases, and the real pidfd case because that standalone Python
build omits `os.pidfd_open`. A separate test verifies the missing-API refusal
on both interpreters; Fedora's Python passes the real process-exit case.
Mypy passes for all 31 backend source files. The native presentation test also
checks that degraded background updates remain visible while connected,
preserve stronger diagnostics and do not trigger a restart or disconnect.

Cleanup tests hold provider completion with explicit events. They verify Stop
finishes while settings persistence remains blocked, Down follows that save,
final Stop/Down calls serialize in either order, and duplicate callers share
one worker. Repeated caller cancellation, cancellation before worker entry,
Start compensation during close, account replacement after waiting, successor
admission and shutdown-deadline failure have targeted cases. Busy remains true
for surviving owners and cleanup failure cannot erase foreground guidance.
No live capture, VPN, credential prompt or installed package was exercised.

The close checkpoint adds exact deadline-propagation assertions from service
through controller to adapter and nested retirement boundaries. Success, error
and timeout cases verify singleflight teardown, repeated caller cancellation
and sticky outcomes. Tests also hold authentication/connection scopes beyond
the deadline, reject new teardown after expiry, preserve capture recovery on a
shortened stop budget and prevent retry re-arming after failed shutdown. This
is source/unit evidence; it does not claim that synchronous provider code can
be preempted or that a failed close proves an external tunnel was removed.

Cleanup-deadline tests prove that an expired Disconnect cannot cancel a held
Core settings save or dispatch after that save is released. They also cover
duplicate/cancelled callers, Stop waiting for Start compensation, either kind
waiting for cleanup dispatch, exact deadline propagation, exhausted scope
admission and a cancellation-resistant capture Stop with durable recovery.
The D-Bus test verifies an explicit bounded rejection while backend readiness
remains true. Process-exit tests use substituted providers and injected exit
callbacks; they do not terminate the live backend or reproduce a network fault.

EC-05 adds a 3,584-combination native permission sweep plus named state cases,
all eight direct GUI Connect routes under blocked conditions, explicit pending
Disconnect, and QML confirmation dispatch/revocation cases. Agent tests retain
queued-successor and lease reconciliation coverage, reject malformed/failed
state reads, recover permission after a valid snapshot, and ensure startup
auto-connect is retired on an existing non-disconnected state once not busy. Desktop
handlers consume the tested policy; no live global shortcuts, tray actions or
VPN operations were exercised for this checkpoint.

The native build was repeated from an empty directory against Qt 6.11.2.
An initial working-tree run reported 40 passing targets using a disk-backed
temporary directory. Its negative fixture cloned the previous committed HEAD;
the exact `a2b3d5e` rerun was 39/40 (VAL-01 above), superseding that full-pass
claim. An older incremental directory produced native crashes with objects
left from before the Qt update; those failures did not reproduce after the
complete rebuild. That older directory is not acceptance evidence.
The earlier checkpoint also encountered the host's `/tmp` quota, resolved for
validation by using the disk-backed directory.
Development static analysis passes; its source-archive reproducibility
subcheck examines committed `HEAD` and must be repeated after committing the
candidate. No new package, installed acceptance, or final seven-reviewer
approval is claimed by this development checkpoint.

The foreground completion checkpoint passes 428 backend tests on Python 3.14
(including the opt-in actual-Core fixture), 428 on Python 3.11 with eight
expected skips, Mypy and 86% branch-aware coverage. Focused cases cover
admission expiry without late dispatch, retained auth/settings publication
after repeated caller cancellation, shutdown of the transaction supervisor,
expired provider writes, and FIDO cancellation before assertion entry and
during submission. The six-image layout matrix was rendered and visually
inspected; the Inspector's second open/close cycle retained 794 KiB PSS and
632 KiB private memory in the isolated demo probe. These are local snapshots,
not a long-duration memory bound or installed desktop acceptance.

The approved refresher boundary is implemented locally, not a renamed success
state. Public Core disable still joins scheduling but not all refresh children.
The adapter fences replacement credentials once services have started, records
sign-out before changing account state, and requires a fresh backend to finish
cleanup. The native client requests systemd replacement only after a successful
current-owner Logout acknowledgement; expired-session preparation explains
the disconnect and does not queue credentials across owners. A pidfd/start-time
check refuses manually overlapping startup, and the service explicitly retains
systemd control-group termination. Unavailable pidfd support and incomplete
cleanup fail closed. See the
[account boundary](ARCHITECTURE.md#ownership-consolidation-checkpoint) for
the runtime record and recovery limits. Installed acceptance and the remaining
ownership consolidation are still open. The released versions' exposure to
the newly identified authorization finding has not been determined by this
baseline scan.

### Baseline findings at `7d1f1b3`

The priorities below are engineering remediation priorities, not new claims
of exploitable security vulnerabilities. P1 means a protection/lifecycle
contract can be violated; P2 means a concrete correctness, recovery, or
resource-lifetime defect. All seven need resolution before this candidate is
accepted; the checkpoint above records candidate remediations without rewriting
the original evidence. Static findings describe reachable source paths; they do not assert
that every reported live incident had that cause.

| ID / priority | Historical defect and consequence | Source evidence at reviewed commit |
| --- | --- | --- |
| EC-01 / P1 | Transitional cleanup skips directly observed Disconnected, although Core can still own a queued target. Disable recovery, close, signed-out cleanup, and expiry can return before that target is retired. This is the remaining PV-013-036 gap. | [adapters.py](../backend/proton_vpn_kde_backend/adapters.py), lines 1341–1343 and callers at 1760, 1792, 1980, 2410. Installed Core `vpnconnector.py:477,499–504` and `connection/states.py:174–187`. |
| EC-02 / P2 | `await_owned` can replace already-recorded caller cancellation with a later child exception, bypassing cancellation-specific reconciliation. A provider-free asyncio check returned ValueError while the owner still had a cancellation request; external connection consequences were not exercised. | [async_utils.py](../backend/proton_vpn_kde_backend/async_utils.py), lines 31–51; connection and FIDO consumers in `adapters.py:1188–1201,1605–1622`. |
| EC-03 / P2 | Background Core refresh failures have no installed error callback into the adapter. A failed refresh can disappear from scheduling while the client retains its signed-in/service-enabled projection until some other operation detects failure. | `adapters.py:289–299,1915–1942`; installed Core `api.py:84–85`, `refresher/scheduler.py:195–210`, and public `VPNDataRefresher.set_error_callback`. Neither the backend nor installed Core bootstrap registers that callback. |
| EC-04 / P2 | Same-owner control-operation timeouts are classified as service loss except for NPS. Disconnect, FIDO cancellation, and recovery-preference replies can falsely report “service stopped” without initiating reconciliation. A permanent wedge is not established. | [VpnControllerSnapshot.cpp](../src/VpnControllerSnapshot.cpp), lines 448–496; [BackendCallPolicy.h](../src/BackendCallPolicy.h), lines 73–79. |
| EC-05 / P2 | Action admission differs between surfaces. The external-action confirmation requires not-busy, disabling tray/shortcut cancellation during connecting although the native primary action permits it. GUI Disconnect also ignores disconnected-with-pending-connect while the Agent supports that interval. | [MainDialogs.qml](../qml/MainDialogs.qml), lines 24–28; [VpnControllerActions.cpp](../src/VpnControllerActions.cpp), lines 97–115; [AgentVpnClient.cpp](../src/AgentVpnClient.cpp), lines 194–210. |
| EC-06 / P2 | Page teardown invalidates a server request but does not dispatch retained parent refreshes. After a topology change, the obsolete reply is discarded and the remaining pending flags can leave parent refresh disabled until another event dispatches work. | [VpnControllerLocations.cpp](../src/VpnControllerLocations.cpp), lines 340–381, 590–592; `VpnControllerSnapshot.cpp:35–41`; `VpnController.cpp:149–152`. |
| EC-07 / P2 | Agent operation reconciliation is cleared after one snapshot even if it is still busy. A later idle signal does not retire the transient lease, retaining an otherwise idle disconnected backend until another action, owner loss, or Agent exit. | `AgentVpnClient.cpp:269–274,435–447,724–757`; [lifetime.py](../backend/proton_vpn_kde_backend/lifetime.py), lines 188–190. |

**Required proof gap — refresher retirement.** `adapters.py:1963–1972`
commits DISABLED after public `refresher.disable()`. Installed Core
`refresher/vpn_data_refresher.py:211–231` and `refresher/scheduler.py:109–129`
cancel background children but join only the scheduler task. This does not
establish that all accepted background work has stopped. A late stale-session
side effect was not demonstrated. The refactor must distinguish disabled
scheduling from retired work, and either prove the necessary public contract
or record a narrow upstream capability dependency. It must not quietly reach
into Core's private scheduler to claim completion.
The working-tree checkpoint above now isolates replacement accounts through
process retirement; it does not retroactively establish a public join contract
at this baseline.

Other design risks are not counted as confirmed defects: overlapping task,
lock, epoch, and delegate ownership across controller/adapter/reconnector;
independently started shutdown budgets; and settings-model parsers that clear
operation busy state even when called by unsolicited data signals. No current
deadlock or separate settings incident was established. These are review and
test obligations for the consolidation, not grounds for speculative patches.

### Common causes and why the earlier cycle kept expanding

1. **Observation was confused with completion.** A state label, method reply,
   cancellation request, or disabled scheduler is not necessarily evidence
   that all accepted work has stopped. In Core 5.6.10, `current_state` is
   assigned before state tasks finish. Disconnected subscriber notification
   is normally *after* those tasks; it is the directly readable property that
   exposes the intermediate interval. Even one public Down is not a proven
   universal barrier: Core captures the connection before acquiring its event
   lock, and queued promotion can make that identity obsolete.
2. **Ownership rules were implemented repeatedly.** Python tasks and locks,
   C++ watcher properties, generations, busy flags, page contexts, and lifetime
   leases each encode part of the same protocol. Rejecting stale output is
   necessary but does not release resources, complete compensation, or dispatch
   remaining work. A fix in one callback therefore left sibling routes open.
3. **The tests copied simplified completion sequences.** Adapter tests replace
   Core imports and default to a disconnect that immediately sets Disconnected
   (`test_proton_core_adapter.py:103–137`). The queued-target regression at
   2481–2557 jumps from Disconnecting directly to Connecting. The real-Core
   [overlay oracle](../packaging/fedora/api-core-overlay/rebuild_overlay.py)
   at 689–705 explicitly passes through Disconnected-with-reconnection, but
   runs separately from the adapter. Likewise, Agent timeout coverage supplies
   an immediately idle reconciliation reply, and browser teardown coverage
   releases already-settled requests. Passing those tests leaves ordering gaps.
4. **Discovery and final approval were interleaved.** Twelve recorded partial
   rounds were superseded, often after the opening three reviewers. Fixing
   immediately and restarting approval meant other perspectives arrived after
   design decisions had already changed. One concrete reversal moved NPS cache
   persistence onto the event loop in `950015d`, then off it with retained
   ownership in `039b96c`, 45 minutes later. Cancellation safety and event-loop
   responsiveness needed one joint contract from the start.
5. **Evidence bookkeeping grew faster than evidence fidelity.** The mechanics
   hash gate seals an admitted diff; it cannot prove semantic preservation or
   independent approval. Exact-expression UI checks similarly bind some tests
   to source spelling. Test counts, coverage, sanitizers, and checksums are
   useful complementary evidence, not proofs of temporal ownership.

Git history makes the cost measurable. From accepted baseline `ec27fdce` at
2026-09-01 21:23:13 −05 to `7d1f1b3` at 2026-09-03 08:08:59 −05 there are
40 commits spanning **34h 45m 46s**. The final diff covers 99 files with
+13,050/−1,678 lines; cumulative commit edits total +14,878/−3,506. The
mechanics gate and UI-hygiene gate each changed in 27 commits, the changelog in
31. The adapter grew from 1,650 to 2,504 lines through 11 commits. These are
author-timestamp spans and edit counts, not measured active work or a claim
that all of that effort was wasted. Thirty commits followed the first review
candidate `1d88e35` over a further 20h 37m.

### Evidence limits and disposition

The three reviewers independently inspected backend lifecycle, frontend
operation ownership, and history/test fidelity before consolidation. Installed
Core source was read without constructing a provider or touching networking.
One isolated in-memory cancellation check exercised only `async_utils`; the
other findings are source traces. No live authentication, VPN operation,
installation, GitHub action, or full-suite rerun was performed for this review.
Earlier passing counts remain historical evidence, not a fresh release pass.

The remedy is one bounded ownership/reconciliation program, delivered in
reviewable commits, not a replacement Core or a single unreviewable rewrite.
The [roadmap](ROADMAP.md#ownership-consolidation-before-further-ux-work)
contains its boundaries, dependency order, scenario matrix, and stopping
criteria. No finding is marked fixed by writing that plan. Complete discovery
on a frozen baseline before implementation; seal the resulting candidate only
after class-level proofs exist, then run all six independent final reviewers.

## Historical 0.13.0 remediation rounds

The following records describe earlier candidate intentions and superseded
results. Their “remediated” labels mean an implementation was attempted, not
that the current error-class register is closed. No partial pass is release
approval.

Six fresh reviewers inspect Hostile, Subtractive, Entropy, Error-Class,
HPC/Performance, and Hardening/Security concerns independently. Reviewers do
not receive another reviewer's findings or perform multiple legs sequentially.

The first pass against `1d88e35` is superseded because it produced actionable
findings. Error-Class found that terminal or unavailable backend states could
hide their diagnostic and recovery affordance. Entropy found that the
presentation mechanics gate accepted unmatched files and that release-facing
posture still named `0.12.0`. HPC/Performance found that the Inspector-retention
probe reconstructed Overview rather than exercising the shipped push/back
lifecycle. The remediated candidate must restart all six reviews; no result
from this superseded pass counts toward release approval.

A second candidate at `a109d3b` restarted the battery. Hostile, Subtractive,
and Entropy independently found actionable state-ownership defects before the
remaining three legs ran: recoverable snapshot failures lacked a reliable
restart path; malformed snapshots blocked a risk-reducing packet-capture Stop;
application or delayed page teardown could leave a capture running or stop a
replacement page's capture; signal-before-reply ordering could transfer capture
state to an older watcher; and location or protected survey work could outlive
the account session that created it. Entropy also found that the mechanics gate
claimed baseline equality while admitting exact-reviewed deltas. That partial
pass is superseded and contributes no release approval. The next candidate must
restart all six reviewers after its focused regressions and release-boundary
wording are sealed to one clean commit.

A third partial pass against `2292aff` was also superseded. Hostile and
Subtractive found that a slow accepted packet-capture Start could outlive
Control Center closure because the backend rejected the compensating Stop, and
that a temporary busy/inactive snapshot could release shutdown without an
affirmative stop outcome. Hostile and Entropy found NPS adapter side effects
that occurred before the account-session check. Entropy also found stale NPS
key, dismissal, connection, and foreground replies that could retire or mutate
a replacement operation, plus a definitive NPS failure that could not be
retried. The current candidate adds cancellation-safe Stop preemption and
affirmative shutdown ownership, serializes destructive NPS work with session
changes, and assigns independent generations to NPS, foreground, and
connection operations. No result from the partial pass counts; all six reviews
must restart on the exact clean candidate.

A fourth partial pass against `d89f2b9` was superseded after Hostile,
Subtractive, and Entropy independently found six state-ownership and error-
classification defects. A current capture Stop reply could be discarded when
a newer foreground request existed; Stop could be rejected behind another
mutation or become unavailable after session expiry; a rejected Start could
retain false cleanup ownership; a superseded server-browser retry could retain
the global browser lease; and an official NPS submission that accepted its side
effect before raising remained presented as safely retryable. The remediated
candidate gives capture completion an independent generation, queues
risk-reducing Stop with a session-epoch recheck, clears rejected Start ownership
from authoritative idle state, transfers browser retry ownership, and adds a
non-retryable NPS completion-unknown error. No result from the partial pass
counts; all six reviews must restart on the exact clean candidate.

A fifth partial pass against `70ed630` was superseded after all three opening
reviewers found release blockers. Subtractive and Entropy found that NPS work
held the global VPN-operation lock without publishing busy state, allowing an
automatic survey read or closed-dialog dismissal to reject a visible connect
or disconnect. Entropy also found that dismissal lacked frontend completion
ownership and that a connection reply could still complete global feedback
after logout. Hostile found that authentication, settings, and protection
recovery policy also rejected risk-reducing capture Stop. Review additionally
found historical 0.12 evidence described as current later in this document.
The remediation uses a narrow survey/logout/shutdown side-effect fence, tracks
submission and dismissal without mutating newer foreground guidance, requires
foreground freshness for connection completion, clears feedback at sign-out,
and separates cleanup readiness from authentication-mutation readiness. The
historical evidence is now version-labeled. No result from the partial pass
counts; all six reviews must restart on the next exact clean candidate.

A sixth partial pass against `1e3b2fa` was superseded after Entropy found that
cancelling the coroutine around Core's synchronous NPS mark-seen cache write
could release the side-effect fence while its executor worker continued into
adapter teardown. Hostile independently found the same cancellation-boundary
class in FIDO2: cancelling an assertion at a PIN prompt cleared the adapter's
only interaction reference without releasing the blocking worker. Subtractive
reported no blocker, but no partial result counts. The remediation keeps the
small local mark-seen transaction on the event-loop thread and made FIDO2
cancellation signal and join the underlying assertion before clearing its
interaction. It also labeled older performance measurements explicitly as
historical. That remediation was itself superseded by the next partial pass.

A seventh partial pass against `950015d` was superseded after Subtractive and
Entropy found four release blockers. Proton Core 5.6.10 uses a private event
while selecting among multiple FIDO2 devices, so joining an assertion after
setting only the public event could wait indefinitely. Moving NPS cache
persistence onto the event loop avoided an ownership race but made local
filesystem latency block all D-Bus control. Automatic-reconnect disablement
discarded its cancelled task before cancellation cleanup completed, and
control-method replies lacked complete account and foreground ownership. The
remediation fails FIDO2 closed unless Core explicitly guarantees cancellable
multi-key selection, runs NPS persistence off-loop while joining its owned
worker, joins reconnect work before disconnect/logout/teardown, and fences all
control replies to their accepted account and foreground generations. No result
from the partial pass counts; all six reviews must restart on the next exact
clean candidate.

An eighth partial pass against `039b96c` was superseded after its three opening
reviewers found six lifecycle and temporal-ownership blockers. Hostile found
that a frontend timeout cleared the pending marker for a capture Start while
the backend could still be running it, preventing a later Stop or shutdown
from dispatching preemption. Subtractive found that normal propagation of a
cancelled reconnect skipped the pending replacement-error rearm. Entropy
proved that ordinary Disconnect did not join a cancellation-resistant retry,
allowing a late Connect to reverse an acknowledged disconnect; that a hidden
whole-settings crash-report normalization save from a read could land after
logout; that FIDO cancellation just before PIN-waiter creation was lost; and
that the resident agent did not distinguish delayed same-owner connection
replies from a newer intent. The remediation retains completion-unknown capture
ownership, suspends and joins reconnect work around Disconnect, rearms pending
errors after either cancellation shape, makes settings reads persistence-free,
checks FIDO cancellation before allocating its PIN waiter, and gives resident
connection operations a monotonic intent generation. No result from the
partial pass counts; all six reviews must restart on the next exact clean
candidate.

A ninth partial pass against `03aa938` was superseded after its three opening
reviewers found four members of the same temporal-ownership error class.
Hostile found that concurrent Disconnect calls shared one reconnector
suspension boolean, allowing one caller to resume retry work while another
Disconnect remained active. Entropy found that an obsolete session's
authentication failure mutated adapter state before the frontend could discard
its stale reply; that a queued resident-agent Connect could survive a newer
Disconnect; and that an older settings read could publish after a newer
successful write. The working-tree remediation replaces symptom-level reply
checks with four cross-cutting invariants: serialized authentication
transitions and adapter epochs, serialized Disconnect lifecycle scopes,
monotonic connection intent across queued work and transient leases, and one
completion order for all settings projections. Focused sibling regressions are
present, but this work is not an accepted candidate until it is committed and
the complete source, package, and six-review gates pass. No result from the
partial pass counts.

The tenth partial pass against `3e1553b` found three deeper ownership defects.
An automatic retry could adopt the newest manual generation before the manual
route completed topology lookup; arbitrary child tasks inherited reentrant
lifecycle authority through Python context; and a Core executor thread could
retain an old name-less backend process after asyncio shutdown. The remediation
made retry suspension cover the complete manual route, bound reentrancy to the
actual owner task or an explicit least-authority delegate, and added finite
process-wide non-daemon thread retirement. The complete source gates passed,
but all reviewer results were invalidated by that behavioral change.

The eleventh partial pass against `050034c` then found two remaining members of
one connection-supersession class. Hostile proved that Disconnect could return
while a blocked manual server lookup retained controller busy state and a retry
suspension owner. Entropy traced a separate late-mutation path through the
installed and packaged Proton Core 5.6.10: cancelling the asyncio retry did not
cancel its executor-backed NetworkManager worker, so an obsolete connection
could materialize after the task appeared joined. Subtractive found no blocker,
but no result from this partial pass counts. The current candidate replaces the
symptom-specific checks with the class invariant summarized below.

The twelfth partial pass against `0fa6d05` was superseded after Hostile found
two remaining high-severity forms of the same class. First, Core 5.6.10 can
return from Connect while the requested target remains queued in
Disconnecting; Down in that state preserves the queue, so the old tunnel's
late Disconnected event could start the obsolete target after an invalidator
returned. Second, a failed compensating Down could be discarded while joining
a cancelled manual or automatic owner, converting failed retirement into
normal completion. Subtractive and Entropy reported no release blocker, but
their results do not count after the candidate changed. The current remediation
uses one stable-disconnect primitive across every invalidator and compensation
path: it owns successive Down operations and state transitions until
Disconnected, and any failure or deadline exhaustion terminates the backend
for supervised replacement. All six reviews must restart on the exact next
commit.

| Connection-supersession dimension | Candidate invariant and regression scope |
| --- | --- |
| Manual admission | All seven public routes register one task owner before their first topology await and suspend automatic retry through Core completion. |
| Invalidating transitions | Newer manual target, Disconnect, logout, session expiry, disabled recovery, and close advance intent, cancel every older manual owner, and join it before completion. |
| Provider-side mutation | At this historical checkpoint, directly observed Disconnected was insufficient. The current register records the later public-barrier candidate fix; final acceptance remains pending. |
| Bounded failure | Manual and automatic retirement share one absolute 30-second deadline; incomplete ownership, failed Down, or missing stable state exits nonzero for a fresh systemd process. |
| Current-Core oracle | At this historical checkpoint, the overlay verifier tested pinned 5.6.10 separately from the adapter. The current register adds three combined adapter/Core conformance cases. |
| Observable release | 318 backend tests passed their modeled sequences. The current review identifies omitted provider and frontend event orderings; those counts do not close the class. |

| ID | Pre-final severity | Finding at reviewed snapshot | Current candidate status |
| --- | --- | --- | --- |
| PV-013-001 | Medium | A slow accepted capture Start could reject Stop while close inferred safety from a temporary snapshot | **Remediated in candidate; independent verification pending** |
| PV-013-002 | Medium | Destructive NPS reads and submissions could cross an account-session transition | **Remediated in candidate; independent verification pending** |
| PV-013-003 | Medium | Stale NPS key or dismissal completion could retire a replacement submission, while definitive failure disabled retry | **Remediated in candidate; independent verification pending** |
| PV-013-004 | Medium | Delayed same-owner foreground or connection replies could overwrite or finish a replacement operation | **Remediated in candidate; independent verification pending** |
| PV-013-005 | Medium | A late current capture Stop reply could be discarded solely because a newer foreground operation existed | **Remediated in candidate; independent verification pending** |
| PV-013-006 | Medium | Capture Stop could be rejected behind an unrelated mutation instead of queuing for same-session cleanup | **Remediated in candidate; independent verification pending** |
| PV-013-007 | Medium | A definitively rejected capture Start could retain expected-active ownership and wedge application shutdown | **Remediated in candidate; independent verification pending** |
| PV-013-008 | Medium | Session expiry removed the only frontend and backend path for stopping an active capture | **Remediated in candidate; independent verification pending** |
| PV-013-009 | Medium | A superseded country or exact-server retry timer could strand replacement browser work behind a retained busy lease | **Remediated in candidate; independent verification pending** |
| PV-013-010 | Medium | An NPS side effect accepted before an upstream exception was exposed as a retryable generic failure | **Remediated in candidate; independent verification pending** |
| PV-013-011 | High | NPS retrieval and submission invisibly held the global VPN-operation lock and could reject connect or disconnect | **Remediated in candidate; independent verification pending** |
| PV-013-012 | Medium | NPS dismissal lacked frontend completion ownership and could overwrite newer foreground guidance | **Remediated in candidate; independent verification pending** |
| PV-013-013 | Medium | A superseded connection reply could still complete centralized feedback after logout | **Remediated in candidate; independent verification pending** |
| PV-013-014 | Medium | Authentication-recovery states rejected risk-reducing capture Stop while capture remained active | **Remediated in candidate; independent verification pending** |
| PV-013-015 | Medium | Cancelling an NPS mark-seen coroutine could let its executor worker mutate Core during adapter teardown | **Remediated in candidate; independent verification pending** |
| PV-013-016 | Medium | Shutdown at a FIDO2 PIN prompt could clear the interaction without releasing and joining its blocking worker | **Remediated in candidate; independent verification pending** |
| PV-013-017 | High | Multi-key FIDO2 selection ignored Core's public cancellation event, so cancellation-safe joining could hang indefinitely | **Remediated by a fail-closed Core capability gate; independent verification pending** |
| PV-013-018 | Medium | Synchronous NPS cache persistence on the event loop could stall every backend control operation | **Remediated with an off-loop owned worker; independent verification pending** |
| PV-013-019 | Medium | Reconnection disablement discarded a cancelled retry before its Core operation had quiesced | **Remediated in candidate; independent verification pending** |
| PV-013-020 | Medium | Delayed control replies could cross an account or foreground transition and mutate current guidance or completion | **Remediated in candidate; independent verification pending** |
| PV-013-021 | High | A frontend timeout could discard pending capture-Start ownership and prevent later Stop or shutdown preemption | **Remediated in candidate; independent verification pending** |
| PV-013-022 | Medium | A normally propagated reconnect cancellation skipped rearming a newer pending Error | **Remediated in candidate; independent verification pending** |
| PV-013-023 | High | Ordinary Disconnect could return before a cancellation-resistant reconnect stopped and then be reversed by its late Connect | **Remediated in candidate; independent verification pending** |
| PV-013-024 | High | A hidden whole-settings normalization save from a stale read could land after logout and restore prior-account protection state | **Remediated by persistence-free reads; independent verification pending** |
| PV-013-025 | Medium | FIDO cancellation immediately before PIN-waiter creation could be lost and leave the assertion worker blocked | **Remediated in candidate; independent verification pending** |
| PV-013-026 | Medium | Resident-agent connection replies had no per-intent generation and could overwrite a newer Disconnect result | **Remediated in candidate; independent verification pending** |
| PV-013-027 | High | A stale account-scoped authentication failure could invalidate a replacement session inside the adapter before frontend epoch checks | **Remediated in working tree; complete verification pending** |
| PV-013-028 | High | Concurrent Disconnect scopes could resume automatic reconnect before every accepted disconnect completed | **Remediated in working tree; complete verification pending** |
| PV-013-029 | High | A queued resident-agent Connect and its delayed transient lease could survive a newer Disconnect intent | **Remediated in working tree; complete verification pending** |
| PV-013-030 | Medium | Settings projections lacked one completion order, allowing an older read to publish after a newer write | **Remediated in working tree; complete verification pending** |
| PV-013-031 | High | A retry could adopt a newer manual intent before topology lookup and compete with that target | **Remediated in candidate; independent verification pending** |
| PV-013-032 | Medium | Inherited Python context could grant arbitrary child tasks reentrant lifecycle authority | **Remediated with explicit task ownership and least-authority delegates; independent verification pending** |
| PV-013-033 | High | A Core executor thread could retain a name-less backend process and mutate shared state beside its replacement | **Remediated with finite process-wide thread retirement; independent verification pending** |
| PV-013-034 | High | Disconnect could return while a blocked manual lookup retained busy and retry-suspension ownership | **Remediated across every manual route and invalidating transition; independent verification pending** |
| PV-013-035 | High | Cancelling a retry task could detach Core 5.6.10's executor-backed NetworkManager mutation and permit a late stale connection | **Remediated with provider-operation joining and compensating disconnect; independent verification pending** |
| PV-013-036 | High | Core 5.6.10 could retain and later promote a queued connection after Disconnect, logout, session expiry, disabled recovery, sign-out cleanup, or close returned | **Candidate fixed in the current working tree; final verification pending; see EC-01 in the current register** |
| PV-013-037 | High | A failed compensating Down could be discarded while joining a superseded connection owner | **Remediated with fail-closed shared compensation; independent verification pending** |

## Historical 0.12.0 isolated review gate

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

The gate at `ee12c05` entered isolated review after two clean normalized
package builds again produced byte-identical binary, debug, debug-source, and
source RPMs. Subtractive review found two lifecycle/error-state defects. A
client could lose its unique D-Bus name while identity checks were in flight,
then be added after its revocation signal had already passed and retain an idle
backend indefinitely. A Proton session expiring during a settings save could
publish the normal signed-out state, then have compensation overwrite it with
a restart-only settings-unavailable state. Every result from that gate is
discarded. Pending authorization now records owner loss only for the bounded
duration of its identity probe, and settings transactions treat session expiry
as the authoritative signed-out recovery path without attempting a second
authenticated write. Focused regressions cover both direct and compensation
expiry as well as cancellation while the expiring write is in flight. The
complete six-review gate must restart on the resulting exact commit.

The next candidate at `ea9d844` again passed source analysis and two normalized,
byte-reproducible package builds before isolated review. Hostile review found
that shutdown canceled the only process-local packet-capture watchdog after an
unconfirmed Core stop. A replacement backend had no durable knowledge of the
capture or its original deadline, so capture could outlive the advertised
safety interval. The Subtractive result from that same wave is discarded with
all other results. Capture start now atomically records its original deadline
before Core receives the request; confirmed stop removes it; unconfirmed
shutdown preserves it; and a replacement must reacquire Core and retry before
publishing readiness. The recovered watchdog keeps retrying bounded stop calls
after the deadline until Core confirms completion. Focused regressions cover
pre-start persistence, unconfirmed shutdown, successful replacement recovery,
missing-connection fail-closed behavior, and post-deadline retries. The complete
six-review gate must restart on the resulting exact commit.

The next exact candidate at `a4983be` passed the same source and two-build
package gate. Its first fresh review wave found that a pre-readiness recovery
whose bounded Core stop calls exceeded the ordinary ten-second idle deadline
could still be canceled into a clean exit. Because `Restart=on-failure` would
not replace that process, the durable record could remain without a live
supervisor. Every result from that wave is discarded. Startup lifetime now
treats any recovery entry as retained work until initialization clears or
validates it, while a genuine initialization failure still exits nonzero for
systemd retry. Focused tests combine the real journal with no frontend lease and
a delayed initialization. The complete six-review gate must restart on the new
exact commit.

The next exact candidate at `75322a9` passed source, native, sanitizer,
Clang-Tidy, and two-build byte-reproducible package gates. Its first fresh
review wave found that Core session restoration could open an unanswered
Secret Service prompt before durable packet-capture recovery ran. Startup
retention kept the process alive but did not arm the recovery watchdog, so the
original `CLOCK_BOOTTIME` deadline could pass without a stop attempt. Every
result from that wave is discarded. The adapter now acquires and registers the
Core connector and completes durable recovery before the potentially
interactive session probe. A focused regression holds provider approval open
after an expired journal deadline and proves that Core receives the stop first.
The resulting `7bad3b8` candidate passed those same source and package gates,
but its first fresh review wave proved that official Core itself restores the
Secret Service session while constructing that connector. The mock-based
ordering test had not modeled this implicit access, so the claimed ordering was
not achievable through the public Core API. Every result from that wave is
also discarded. Startup now prewarms the Core session first and bounds that
wait whenever a durable recovery entry exists. An unanswered prompt exits
nonzero with the entry retained for systemd retry; a successful prewarm is
reused by connector construction and recovery. Focused tests model the
implicit Core access, verify one provider prompt, and prove both successful
recovery and timeout retention. The resulting exact candidate at `9997dd5`
passed the same source and two-build package gates. Its first fresh review wave
found that a missing or revoked session made Core deliberately ignore persisted
connection state and synthesize a disconnected connector. Recovery trusted
that state and deleted the only completion-unknown journal without asking Core
to stop capture. Every result from that wave is discarded. A pending recovery
entry now requires a restored logged-in session before connector construction;
otherwise startup exits nonzero with the entry retained. A regression verifies
that the logged-out connector is never requested and the journal is preserved.
The resulting `af73ec9` candidate passed the same source and two-build package
gates. Its fresh entropy review found that successful session restoration was
followed by unbounded Core connector construction. Because a recovery journal
deliberately retains startup, a stalled split-tunneling system D-Bus operation
could leave the backend unready forever without arming the capture watchdog or
exiting for systemd retry. Every result from that battery is discarded.
Connector construction is now bounded whenever startup recovery is pending; a
timeout exits nonzero with the journal retained. A focused regression holds
connector construction open after successful session prewarming and verifies
bounded failure without false readiness. The complete six-review gate must
restart on the resulting exact commit.

The resulting `a18650c` candidate passed the complete source, native, sanitizer,
Clang-Tidy, and two-build byte-reproducible package gates. Five isolated review
categories passed, but Error-Class found that successful capture recovery could
emit a ready snapshot while refresher and reconnector initialization was still
in flight. That callback exposed a transient logged-in/signed-out contradiction
and could admit frontend work against a partially initialized adapter. Every
result from that battery is discarded. Snapshot callbacks are now suppressed
throughout adapter initialization; internal recovery state is retained and the
controller receives one authoritative snapshot only after session services are
ready. A regression holds refresher startup open and proves that recovery,
connector, and reconnector callbacks cannot publish early. The complete
six-review gate must restart on the resulting exact commit.

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
| PV-012-023 | Medium | Owner loss during an asynchronous identity probe could be processed before authorization, allowing the dead client to be added afterward and retain an idle backend | **Remediated with a bounded pending-authorization owner-loss marker; final independent verification pending** |
| PV-012-024 | Medium | Session expiry during a settings write or compensation could be overwritten with a restart-only settings-unavailable state | **Remediated by preserving the authoritative expired-session state and deferring persisted-settings reconciliation to the next sign-in; final independent verification pending** |
| PV-012-025 | Medium | Backend shutdown could discard the only watchdog after an unconfirmed packet-capture stop, leaving a replacement unable to enforce the original deadline | **Remediated with an atomic runtime recovery record, pre-readiness Core reacquisition, and continuing deadline retries; final independent verification pending** |
| PV-012-026 | Medium | The no-client startup idle deadline could cancel a hanging capture-recovery stop and exit cleanly, leaving the durable record without a scheduled supervisor | **Remediated by retaining initialization while any recovery entry exists and preserving nonzero failure retry; final independent verification pending** |
| PV-012-027 | Medium | An unanswered or unavailable Secret Service session, or stalled Core connector construction, could delay recovery indefinitely or synthesize a disconnected state that falsely cleared the durable packet-capture journal | **Remediated with bounded session and connector restoration, a required logged-in session, nonzero startup retry, and durable journal retention; final independent verification pending** |
| PV-012-028 | Medium | Packet-capture recovery could publish a ready snapshot before authentication and session-service initialization completed | **Remediated by suppressing snapshot callbacks until the adapter returns its final authoritative startup state; final independent verification pending** |

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
The original deadline is atomically persisted before start, removed only after
confirmed stop or confirmed tunnel termination, and reacquired before a
replacement backend reports ready. A failed stop retains bounded retry
supervision beyond the deadline instead of discarding capture ownership.

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
The separate `0.12.0` tables above are historical records for mechanics that
were subsequently accepted; their superseded intermediate findings are closed.
Defense-in-depth opportunities are listed under **Residual risk and follow-up**
and are not represented as undisclosed vulnerabilities.

## Verification

### Automated source verification

The accepted `0.12.0` mechanics at `ec27fdc` passed:

- 37 of 37 CTest tests, including native controllers, QML, D-Bus activation,
  staged installation, authentication, lifetime, KRunner, System Settings, and
  API-Core overlay coverage;
- 215 backend Python tests;
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
from the then-unreleased, subsequently accepted `0.12.0` gate above and the
historical finding record below.

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
