# Roadmap

This roadmap records remaining work and dated verification checkpoints.
Completed user-visible changes belong in the [changelog](../CHANGELOG.md),
and detailed review evidence and closed findings remain in the
[security assessment](SECURITY-AUDIT-2026-08-30.md).

Every item must preserve the project boundary: Proton's official Core owns VPN
protocols, NetworkManager integration, kill switch, IPv6 leak protection,
split tunneling, server selection, and session persistence. A Core change is an
independent upstream contribution, not a hidden part of this client.

## 0.13.0: progressive Plasma experience

Version 0.13.0 is a presentation-led release based on the accepted 0.12.0
mechanics. Its design principle is progressive disclosure: begin with the one
clear task or decision most people need, then reveal relevant depth in context
as the person asks for it. The interface should feel simple on first use and
grow with the user without creating separate novice and expert modes.

This does not mean hiding operational truth. Connection and protection state,
the consequences of an action, authentication requirements, errors, and the
next safe recovery step remain visible at the point where they matter. Details
may be collapsed; safety state may not be.

The implementation constraints are:

- Use native Qt 6, Kirigami, and KDE Frameworks controls. System colors,
  typography, spacing, icon theme, font scaling, directionality, contrast, and
  motion preferences remain authoritative.
- Keep one obvious primary action per task surface. Reveal filters, exact
  servers, diagnostics, and uncommon settings from the relevant summary
  instead of presenting the complete control surface at once.
- Preserve a stable navigation and spatial model as more detail appears. A
  user should not be moved to another section merely because a setting changed
  or an asynchronous operation completed.
- Prefer recognition over recall: show selected criteria and active effects in
  plain language, with technical identifiers available one level deeper.
- Keep advanced disclosure contextual. Do not create an undifferentiated
  Advanced page or use nested accordions as a place to hide design debt.
- Change no Proton Core, VPN networking, or authentication protocol behavior.
  The error-class review has identified a coordinated client-side lifecycle
  stabilization prerequisite below. It is an explicit behavioral workstream,
  not presentation-only work disguised as small exceptions. The existing
  mechanics gate compares against `ec27fdc` and seals admitted deltas; that
  checksum is drift detection, not proof of correctness or reviewer approval.

### Frozen release-candidate checkpoint — 2026-09-09

The seven isolated reviewers completed one bounded review of
`0912144793b8a149b8b2e2933bd8c78b71470214`. It required five P2 corrections and
one low-severity/P3 security correction. **All six are now implemented and
verified in signed commit `17791c7`; release approval remains pending.**
No P0/P1 was substantiated; security coverage is explicitly partial. The
[current finding register](SECURITY-AUDIT-2026-08-30.md#frozen-release-candidate-review--2026-09-09)
contains the evidence, priorities and regression requirements.

The maintainer-authorized bounded series implements four work areas:

1. Own startup intent once, defer auto-connect until admissible, prevent later
   preference changes from reviving it, and wait for tray activation/fallback.
2. Publish local preference changes only after persistence is confirmed.
3. Render public action-confirmation data as literal text, without image loads.
4. Repair both offline search-benchmark fixtures without relaxing production
   authentication, then refresh the measurement evidence.

The review itself was read-only; the subsequent correction and verification
are recorded in the [remediation checkpoint](SECURITY-AUDIT-2026-08-30.md#bounded-rc1rc6-remediation--2026-09-09).
Subtractive and Cognitive
Load found no blockers or reason for a broad refactor. Four optional P3
follow-ups stay separate in the register; they do not expand this series.
The fixes add no Core or networking changes. Do not automatically repeat broad
discovery and repair.

The runtime correction `17791c7` passes 42 normal and sanitized native targets,
440 Python/Core cases, affected-unit Clang-Tidy and static/mechanics checks.
Its first local package (`705c4b2`, `0.13.0-0.5.fc44`) passed workstation
checks but exposed test-isolation assumptions in a clean container. That
[failed package checkpoint](SECURITY-AUDIT-2026-08-30.md#rc-package-validation-checkpoint--2026-09-09)
is retained as historical evidence, not a current blocker or a passing build.

The authorized **test-isolation correction, not a runtime refactor**, now
owns desktop directories before actual-Core imports and inside the offline
benchmark fixture. Adapter tests use fake route/session inputs, reject escaped
real probes and bound fixture-event waits. All 442 Python/Core cases pass with
desktop variables removed; the formerly unbounded wait fails in five seconds
when its fake prerequisite is deliberately withheld. The
[correction record](SECURITY-AUDIT-2026-08-30.md#pkg-01-test-isolation-correction--2026-09-09)
keeps that evidence separate from package approval. The replacement local
Python candidate `f667277` passes all 442 cases in the clean container too.
Collecting all native results exposed two more ambient inputs: an installed
translation catalog and undeclared visual-theme data. Test-target catalog
paths/fallbacks and the Breeze/platform-theme build dependencies are now
explicit. No production or overlay source changed, and no broad
discovery/repair cycle was started.

**PKG-01 is closed for package validation.** Signed source `4eebc3f` produces
the replacement `0.13.0-0.7.fc44` candidate. Two clean Fedora builds each pass
442 Python/Core cases and all 41 archive-eligible native targets; all four
client RPM outputs are byte-identical. Both overlay RPM/SRPM pairs pass their
policies, and the combined container-only installation passes payload and
native-hardening verification. Exact source and six-artifact hashes are in the
[replacement package checkpoint](SECURITY-AUDIT-2026-08-30.md#replacement-package-verification--2026-09-09).

The `0.13.0-0.7.fc44` first-launch UAT exposed START-01: KRunner's
inherited Qt plugin path causes the GUI's authorization to fail, while the
clean service path used on tray reopening succeeds. A controlled warm-backend
reproduction confirmed that rejection without disconnecting the VPN.

The bounded `0.8` source correction normalizes both native entry points before
Qt initialization, re-executing only when the shared denylist requires it.
It preserves backend authorization and Core/networking behavior. The
[START-01 checkpoint](SECURITY-AUDIT-2026-08-30.md#start-01-direct-native-launch--2026-09-09)
records the regression cases and separates implementation from installed UAT.

Bounded source verification passes: 43 CTest targets, 442 Python/Core cases,
41 normal/sanitized startup-probe cases, the real native-entry-point environment
check, affected-unit Clang-Tidy, and static/metadata/scope checks.

Signed candidate `1db0dd4` now builds `0.13.0-0.8.fc44`. Two clean Fedora builds
each pass 442 Python/Core cases and 42 package-eligible CTest targets; all four
RPM outputs are byte-identical. The full container transaction and hardening
checks pass. The authorized host upgrade is installed and root-verified with
Core/keyring unchanged, and user-service definitions have been reloaded.
The installed cold-launch registration check passes with the inherited Qt
plugin-path canary. Subsequent UAT exposed a separate **START-02 availability
blocker**: manually disconnecting the IPv6 protection device leaves
NetworkManager autoconnect disabled, while Core startup adds another profile
and times out. Backend restarts repeat Secret Service prompts. Explicitly
reactivating the original profile recovered saved-session startup and the
Proton connection with no source change; 23 backed-up inactive duplicates were
removed, leaving active protection and unrelated connections unchanged.

That initial operational recovery did not close START-02. The maintainer authorized
both the community startup/retry correction and a narrow Core activation patch.
Both are implemented in the working candidate. The
[UAT checkpoint](SECURITY-AUDIT-2026-08-30.md#start-02-inactive-leak-protection-device--2026-09-09)
records their boundaries and evidence: 448 Python/Core cases with zero skips,
43 clean-build CTest targets, and 13 mandatory Core RPM activation cases pass.
The client distinguishes restored credentials from failed networking startup,
holds ordinary failures for explicit retry, and preserves durable cleanup
supervision. The Core overlay reuses validated profiles and explicitly activates
them without changing protection rules or deleting uncertain profiles.

Signed client source `f6e12d0` now builds `0.13.0-0.9.fc44`: two clean builds
each pass 448 Python/Core cases and 42 package-eligible CTest targets, and all
four client artifacts are byte-identical. The client and Core revision `11`
were installed and root-verified, with keyring unchanged. Saved-session startup
and connection passed. Controlled retained-profile recovery verified the stable
startup error/no-restart behavior but exposed an unmodeled NetworkManager
normalization step in the Core comparison.

Core revision `12`, from signed source `5fa8279`, normalizes only the comparison
copy and models normalized stored profiles in the regression fixture. All 14
cases and its isolated RPM/SRPM checks pass, as do 448 Python/Core cases with
zero skips against that fixture. It is now installed and root-verified.
Cold-start recovery passed with a retained device whose autoconnect policy was
disabled: the original protection profile was explicitly activated, without
duplicates or backend restarts. The maintainer confirmed automatic recovery
without Retry or Connect. In-app Disconnect removed the Proton profiles and
temporary test interface and left the backend ready and signed in. A normal
in-app Connect then created fresh profiles and reconnected without a backend
restart; the unrelated private VPN was unchanged. This is a Core-only package correction, not another
native-client rebuild or final independent approval.

Still required: exact-candidate review, signed/reproducible package validation,
remaining START-02 explicit-retry and desktop/tray acceptance,
maintainer first-window/session acceptance and ordinary desktop/tray UAT, final independent
seven-perspective approval, and the planned one-week immutable-runtime soak.
Version 0.13.0 remains unreleased.
The dated checkpoints below retain earlier evidence, not current approval.

### Ownership consolidation before further UX work

This is the approved refactor program following the 2026-09-07
[error-class review](SECURITY-AUDIT-2026-08-30.md#current-0130-error-class-review)
of `7d1f1b3`. Its seven defects and separate refresher-quiescence proof gap
informed the refactor. The checkpoint below separates the implemented
candidate from remaining verification obligations.
One coordinated design should
replace repeated symptom patches; implementation should still use small,
dependency-ordered commits with focused proofs.

#### Review checkpoint — bounded error-class correction 2026-09-08

Earlier isolated review: the separate seven-review battery at `4d6b5f2` found seven
P2 issues and one P3. The maintainer-authorized bounded series through `5a34639`
implements R1–R8 with regression cases. All 41 normal/sanitized test targets,
439 backend tests, 35 Clang-Tidy production files and static/candidate gates
pass; explicit environment and package-validation gaps remain in the register.
The [previous correction register](SECURITY-AUDIT-2026-08-30.md#previous-bounded-seven-review-correction-register--2026-09-08)
separates these results from the older checkpoints retained below. Do not reopen
optional cleanup or begin another automatic scan/repair loop. After the bounded
gates, freeze the candidate for package validation and focused installed UAT;
final independent release approval and soak remain required.

The package candidate `9f26ba2` has now passed two byte-identical local client
builds, the six-artifact content checks and an isolated upgrade check. The
three binary RPMs were installed with maintainer approval and passed root-side
payload verification. The [package checkpoint](SECURITY-AUDIT-2026-08-30.md#package-and-local-install-checkpoint--2026-09-08)
records the exact evidence and remaining clean-environment and live-UAT gates.
This installation is for local acceptance, not release approval or soak entry.

Visual feedback from that installation is addressed in the `0.13.0-0.2`
client candidate: integrated split-route graphics, a contained report form,
and an unambiguous task-manager icon name. All 42 native targets and the new
sanitized layout fixture pass. See the [visual UAT checkpoint](SECURITY-AUDIT-2026-08-30.md#visual-uat-corrections--2026-09-08).
Its client RPM/SRPM pass their mandatory tests and artifact/source checks.
The approved `0.2` client upgrade passed root-side verification; the host
icon resolver selected the correct installed artwork.
The preceding local client candidate, `0.13.0-0.3`, implements the approved
horizontal layouts: endpoint-local facts, a smooth arrow-free split route,
and app-owned, content-fitted window sizing with no manual resize/maximize.
All 42 native targets, the sanitized layout fixture and presentation checks
pass. The client RPM/SRPM from `58b3d83` also pass their mandatory tests and
artifact/source checks. The approved `0.3` client upgrade was installed and
passed root-side verification before the follow-ups below. KWin resize controls
and monitor changes remain part of final installed acceptance. That upgrade
did not change the Core/keyring packages or replace the remaining release gates.

The next maintainer-authorized follow-up added smooth dashed-curve rendering
and one shared Startup section for optional login launch, window/tray startup,
and existing auto-connect targets. It does not change Proton Core, networking,
or authentication. At that source-only checkpoint, `0.3` remained the installed
candidate pending replacement-package approval. Startup registration
and real login/session-restoration acceptance remain opt-in live-UAT gates;
automated fixtures use disposable configuration and never enable host startup.
Runtime revision `443b7c1` passes all 42 normal test targets, the three affected
settings/presentation/KCM targets with address, leak and undefined-behavior
sanitizers, Clang-Tidy for the three affected production files, and static,
source-archive and documentation checks. The graphics fixture also passes all
ten data cases through OpenGL at 150% display scaling, explicitly checking
that Qt selects the curve renderer; it includes narrow, large-text and RTL
startup layouts. These are development checks, not a new independent review
battery or release approval. No replacement RPM or installation was included
in that source checkpoint.

The subsequent bounded presentation polish, committed at `470e592`,
reduces current in-app notes to five highlights, makes startup explanations
contextual, and restores normal text contrast to shared descriptions and
Inspector labels. It keeps the existing positive protected-state color and
attention-colored bypass branch, correcting a misleading neutral default in
the isolated layout fixture. Native focus/tooltip feedback and the demo
gallery are refreshed; the README links to dated evidence instead of
duplicating test counts. No backend or Proton networking code changes.

This follow-up passes all 42 CTest targets, the three targeted
settings/presentation/KCM sanitizer targets, static checks and the mechanics
scope gate. Fourteen layout data cases also pass at 150% scaling through
OpenGL, with actual curve-renderer selection asserted for the route.
The [bounded polish checklist](VISUAL-SYSTEM.md#bounded-polish-acceptance)
distinguishes these checks from installed keyboard/screen-reader, KWin and
monitor-change acceptance. That source checkpoint did not include a new
independent review battery, package, installation or release approval.

The latest recorded local installation is **`0.13.0-0.4.fc44`**, built from
`16ed2392d8f6f67d4223ec36f1106d94b2cdd1f8`. It includes the Startup controls,
presentation polish and a same-day-upgrade QML cache correction caught by the
mandatory package checks. All 41 archive-eligible CTest targets, Python
analysis and RPM/source-content checks pass. The approved client-only upgrade
passed root-side payload verification; all three services were stopped at that
checkpoint, with Core/keyring packages and existing network connections unchanged.
The [installation checkpoint](SECURITY-AUDIT-2026-08-30.md#startup-and-polish-local-install--2026-09-08)
separates this unsigned local-UAT build from final review, live acceptance,
reproducibility and release gates. No push, tag or publication occurred.

The coordinated lifecycle refactor is committed at `a2b3d5e`. All seven
isolated perspectives have completed review of that same frozen revision.
Results and the consolidated correction register are in the
[security and engineering assessment](SECURITY-AUDIT-2026-08-30.md#current-0130-error-class-review).
This is a completed development review cycle, not final release approval.

Five runtime corrections and one stale negative-test fixture were grouped
in local commit `7d4d030`: settings request ownership, ambiguous GUI
completion, early sign-out recovery publication, persistent degraded-update
guidance, and bounded account reads/latest-query coalescing. Cognitive Load
and Subtractive reviews found no reason for another broad structural refactor.
Optional cleanup is recorded separately from required corrections.

The bounded Error-Class re-check found that the ambiguous-completion correction
can mistake an unchanged connected tunnel for a successful server switch.
RC-02 remained open despite 431 backend tests and 40/40 normal/sanitized native
targets passing. The matrix missed same-state failed replacement. Implementation
stopped at the maintainer's request. The maintainer then authorized a bounded
class correction: observation and idle retirement must never manufacture a
request acknowledgement. The contract and sibling-surface inventory are in
[architecture](ARCHITECTURE.md#request-result-evidence-contract). Native/QML,
settings and capture now follow that contract at `1a2366e`. Its 64-row native
and 48-row QML matrices, all three settings families and failed/unconfirmed
capture Starts pass. The full 40-target suite passes normally and under
sanitizers; 431 backend tests including actual-Core 5.6.10 conformance, Mypy,
35 production Clang-Tidy units and static/archive checks also pass. The bounded
implementation and regression-verification task is complete; no new scan or
Core change was needed.

Performance and Cognitive Load correction checks passed on `7d4d030`.
Security reported no concrete required correction within its stated source
scope. Those earlier checks are not independent approval of `1a2366e`.

The refactor retains the approved fresh-process account boundary, public Core
5.6.10 completion evidence, owned background error handling, shared native
capability policy, independent cleanup admission, and absolute foreground,
cleanup and shutdown deadlines. No new Core patch or wire protocol is involved.

Do not restart broad discovery or another repair cycle automatically. A new
unrelated defect or wider protocol proposal requires a separate scope decision.
No Core rewrite is part of this roadmap. Local UAT now targets the installed
package candidate above. Before release, complete independent final approval
and the remaining exact-candidate clean-environment package battery.
The full security scan had partial coverage, explicitly recorded in the
assessment; no-finding is not full approval. Installed acceptance, true 1.5x
text/keyboard/accessibility checks and the one-week soak remain separate
gates. Local installation has occurred; no publication has occurred in this cycle.

#### 1. Freeze discovery and specify the contract

- Collect all seven independent perspectives against the unchanged
  runtime baseline before another fix/restart cycle. The current backend,
  frontend, and process investigation is error-class discovery, not six final
  release approvals. Consolidate duplicates under invariant families and
  distinguish defects, evidence gaps, and optional cleanup.
- Inventory connection routes, retries, authentication/FIDO, settings, NPS,
  capture, browsing, background refresh, frontend leases, and shutdown. For
  each, record admission, owner/session, invalidators, side effects, cleanup,
  completion evidence, deadline, and UI result in the existing architecture
  document. Do not create another parallel finding ledger.
- Explicitly distinguish intent accepted, provider work pending, result
  unknown, cleanup pending, and terminal outcome. A snapshot, coroutine return,
  cancellation request, or scheduler-disabled flag is not by itself a receipt
  that provider work has stopped.
- Preserve domain independence: capture Stop must survive unrelated foreground
  changes, and an ambiguous NPS submission must not be retried automatically.
  Closing a frontend or disabling recovery must not become an implicit
  instruction to disconnect an intentionally preserved established tunnel.

Exit: one reviewed operation/ownership contract, one consolidated backlog, and
explicit preservation policies. No implementation-driven redefinition of the
invariants merely to make a failing test pass.

#### 2. Establish provider and event-order conformance tests

- Use actual pinned Core 5.6.10 connector/state logic with substituted external
  I/O in an isolated harness. Do not instantiate live NetworkManager, read
  credentials, or contact Proton. Keep fast unit fakes, but make their supported
  transition traces agree with the provider harness. The separate overlay
  oracle currently proves provider behavior, not that our adapter handles it.
- Cover admission and lookup, Core lock wait, executor work, queued replacement,
  directly observable Disconnected while state tasks await, promotion, and
  compensation. Test stale connection identity during a public Down. Prove
  retirement or report it unconfirmed; do not assume one additional Down fixes
  every sequence or inspect private Core queues in production.
- Give the shared ownership primitive a direct terminal-outcome matrix:
  cancellation before/during/after child success, child exception, and child
  cancellation; repeated cancellation; and cleanup failure. Assert which
  outcome is published and that reconciliation happens exactly once.
- Extend native fake-backend tests with timeout → still-busy read → idle signal;
  topology change → page destruction → stale reply; same-owner control timeout;
  and cancellation through the external-action confirmation. Include
  signal-before-reply, owner replacement, and unrelated-domain supersession.
- Resolve the refresher stop/join contract against installed source. If public
  Core cannot supply required retirement evidence, record an upstream capability
  requirement and an explicit blocked/unknown outcome. Do not invent a wrapper
  guarantee or add a hidden Core patch.

Exit: reproducible, failing-before/fixed-after acceptance scenarios for every
confirmed defect, with provider fidelity demonstrated rather than assumed.

#### 3. Consolidate backend ownership

- Extract a narrow lifecycle coordinator from the adapter's existing machinery,
  owning session transitions, connection intent, accepted work, and retirement.
  Keep authentication and connection domains distinct, document lock order,
  and avoid replacing all domains with one blocking global lock.
- Give owned operations separate caller-cancellation, provider-result, and
  cleanup outcomes. Join accepted work and reconcile once before publishing a
  terminal result. Pass the same absolute deadline inward; repeated close
  joins one existing completion instead of starting a fresh budget.
- Keep version-specific completion interpretation in a small Core boundary
  adapter. A confirmed retirement and an unconfirmed retirement are different
  results. Backend replacement bounds process lifetime; it does not prove that
  NetworkManager has torn down an externally owned tunnel.
- Make retry logic request operations through that coordinator rather than
  retaining a second direct mutation path. Let the controller validate inputs
  and project authoritative results instead of reconstructing ownership.
- Route background refresher errors through a session-tagged owned handler.
  Do not synchronously join the scheduler from its own failure callback, or
  allow an old callback to invalidate a replacement account session.

Exit: EC-01 through EC-03 and the provider-quiescence obligation have explicit
verified outcomes across all routes; unresolved upstream limits are blockers,
not renamed success states.

#### 4. Consolidate frontend reconciliation and release obligations

- Replace repeated watcher-property/boolean interpretations with typed request
  context and a shared disposition: success, definitive rejection, completion
  unknown, or owner lost. Keep verified unique-owner pinning and sealed-secret
  transport unchanged. A timeout alone must not declare the service dead.
- Give each operation domain its own completion record. Settlement,
  cancellation, invalidation, and page teardown must each decide both resource
  release and remaining-work dispatch. Completion-unknown records retain their
  reconciliation obligation through later signals, with bounded read retries
  when necessary rather than permanent polling.
- Derive action capabilities in native policy. QML, tray, shortcuts, and
  confirmation dialogs consume the same can-connect/can-disconnect decisions;
  a blanket busy gate must not override risk-reducing cancellation.
- Keep settings/snapshot parsers data-only; unsolicited projections do not
  finish arbitrary operations. Browser-context retirement must dispatch valid
  pending parent work. Agent reconciliation must release its transient lease
  once its own operation is terminal, without releasing a successor's lease.
- Preserve the GUI/Agent process and lifetime split. The confirmed defects do
  not require a new D-Bus schema: schema-1 parsing rejects unknown fields, so
  any later wire-level operation IDs would need a separately approved migration.

Exit: EC-04 through EC-07 pass the shared event-order matrix in both native
clients; no abandoned callback is required for queue progress or idle release.

#### 5. Subtract superseded machinery and seal once

- Remove replaced task/delegate/busy bookkeeping and duplicate action rules as
  each new owner becomes authoritative. Do not retain both implementations or
  split large files while leaving their ownership unchanged.
- Move source-spelling behavioral assertions to execution tests where practical;
  retain genuine static policy and schema checks. Label the mechanics hash
  gate as a reviewed-delta seal only after review actually occurs. Update the
  changelog once for the coordinated user-visible change, not every helper edit.
- Map every accepted invariant to evidence. Exercise all entry routes against
  each applicable invalidator; do not substitute exact Down-call counts or a
  coverage percentage for terminal state, absent late work, and resource release.
- Recheck responsiveness under a blocked provider, event-driven idle exit,
  bounded task/lease counts after repeated operations, and no accumulating
  resident memory across repeated open/close cycles. Preserve existing sanitizer,
  minimum-dependency, static-analysis, packaging, and security controls.

Exit: no unresolved release blockers or unacknowledged proof gaps, provider and
fake traces agree for covered scenarios, all class-level tests pass, and the
documentation accurately distinguishes tested controls from upstream limits.
Then seal one clean runtime commit for the full release sequence below. This
reduces repeated approval work without weakening final review requirements.

### Delivery sequence

1. Complete the ownership consolidation above, then verify compact and wide
   windows, keyboard-only use, screen-reader names,
   1.5x text, right-to-left layout, light and dark schemes, high contrast, and
   reduced motion before repeating the full release battery.
2. Seal all admitted mechanics corrections and their class-level regressions to
   one clean commit, then run seven independent reviews: Hostile, Subtractive,
   Entropy, Error-Class, HPC/Performance, Hardening/Security, and Cognitive
   Load/Code Maintainability. The seventh perspective, added on 2026-09-08,
   examines unnecessary abstraction, duplicated machinery, hidden control
   flow, excessive configuration and the effort needed to understand or change
   the code. Reviewers inspect the same exact revision without receiving each
   other's findings. Collect all seven results before beginning another
   remediation cycle; do not repeatedly stop discovery after the opening wave.
   Behavioral changes invalidate final approval and require re-review, but
   focused development checks are not themselves final approval rounds.
3. Repeat source-archive, sanitizer, static-analysis, reproducibility, RPM,
   SRPM, overlay-policy, and combined-transaction verification from the exact
   review-passing revision.
4. Install only the resulting artifacts and repeat live Plasma acceptance,
   including authentication, connect/disconnect, suspend recovery, server
   browsing, settings, resident controls, and packet-capture shutdown.
5. Use that accepted build locally for the planned soak period before any
   public release or merge decision.

### Information-architecture target

| User intent | First layer | Disclosed depth |
| --- | --- | --- |
| Get protected | Current state and one connect or disconnect action | Chosen criteria, server, protocol, and protection details |
| Choose a destination | Fastest suitable choice and visible capability filters | Country, state or city, exact server, load, and capabilities |
| Adjust behavior | Common settings grouped by outcome | Contextual exceptions, custom DNS, and split tunneling |
| Understand a problem | Plain-language state and one safe recovery action | Technical error, component status, and diagnostics |
| Inspect a connection | Short live summary | The existing read-only Connection Inspector |
| Manage identity | Sign-in requirement or current account | Two-factor, Core-compatible security key, plan, and sign-out actions |

## Post-release stabilization

- Send Proton a concise engineering introduction after the public tag and
  signed Fedora artifacts are available for review.
- Triage public-alpha reports against the documented support boundary and add
  regression coverage before changing behavior.
- Keep the compatibility matrix current as Proton Core, Fedora, Qt, and KDE
  Frameworks releases change.
- Expand the release battery to a second independently tested Plasma
  distribution before claiming broader Linux support.
- Seek an independent review of the authentication transport, D-Bus service
  identity, and sender-authorization design before describing the project as
  independently security-reviewed or stable.
- Complete translation coverage for Plasma-specific strings without guessing
  translations or obscuring their provenance.
- Add a publication-mode release-metadata gate that requires a dated changelog
  entry and final Fedora release number while preserving the current local-soak
  workflow for unreleased feature branches.
- Reassess release-workflow trust boundaries if CI later gains secrets,
  persistent runners, package-signing authority, or artifact publication; the
  current pull-request build has none of those authorities.

## Optional Plasma widget

Provide a Plasma 6 widget for status and common connection actions. It should
reuse the resident agent and current authenticated backend path instead of
embedding Python or Proton Core in `plasmashell`. The agent and Control Center
must remain complete without the widget.

## Upstream opportunities

After the Plasma public release, prepare the existing API Core changes for
upstream consideration: the dependency-ordered string-sharing series,
independent deprecated-FIDO2-query cleanup, and a separate Protun
secret-ownership proposal. The [overlay handoff checklist](../packaging/fedora/api-core-overlay/README.md#patch-scope-and-upstream-handoff)
records their provenance, current test evidence, source-format conversion,
attribution review, and remaining baseline/performance and desktop-compatibility
checks. Recorded local source commits are not claims of Proton acceptance.
Do not add speculative Core refactoring to those proposals.

Provider-neutral Secret Service compatibility belongs in Proton's keyring
repository, independently of the Core series. Each submission should include
focused tests, preserve its actual authorship, and avoid depending on this
Plasma frontend. Publication or submission requires separate maintainer approval.

A distinct future Core opportunity is to pass the public FIDO2 cancellation
event through multi-key selection and expose an explicit capability only after
selection, assertion, and PIN workers all quiesce on cancellation. That is not
implemented by the existing capability-query cleanup. Only a verified upstream
implementation would let the Plasma client re-enable its security-key flow.
