# Roadmap

This roadmap contains planned work only. Completed user-visible changes belong
in the [changelog](../CHANGELOG.md), and closed security findings remain in the
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

Latest checkpoint: the separate seven-review battery at `4d6b5f2` found seven
P2 issues and one P3. The maintainer-authorized bounded series through `5a34639`
implements R1–R8 with regression cases. All 41 normal/sanitized test targets,
439 backend tests, 35 Clang-Tidy production files and static/candidate gates
pass; explicit environment and package-validation gaps remain in the register.
The [current correction register](SECURITY-AUDIT-2026-08-30.md#current-bounded-seven-review-correction-register--2026-09-08)
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
Next: validate its client RPM/SRPM and obtain approval for installed visual
acceptance; the existing Core/keyring packages are unchanged. This does not
replace the remaining release gates.

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

Provider-neutral Secret Service compatibility, small Core API hygiene fixes,
and terminology improvements should be proposed separately to the Proton
repository that owns each behavior. Each patch must stand on its own, include
focused tests, and avoid depending on this Plasma frontend.

The first Core proposal should pass the public FIDO2 cancellation event through
multi-key selection and expose an explicit capability only after selection,
assertion, and PIN workers all quiesce on cancellation. The Plasma client can
then re-enable its existing security-key flow without carrying a Core patch.
