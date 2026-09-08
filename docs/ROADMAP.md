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
of `7d1f1b3`. Seven defects and a separate refresher-quiescence proof gap remain
open at that reviewed baseline. Implementation has now started in the working
tree; the checkpoint below separates local fixes from remaining obligations.
One coordinated design should
replace repeated symptom patches; implementation should still use small,
dependency-ordered commits with focused proofs.

#### Working-tree checkpoint — 2026-09-08

- Baseline discovery is frozen. Independent hostile, subtractive, entropy,
  error-class, performance and security perspectives have been collected;
  these are discovery inputs, not final release approvals.
- Implemented: shared task-scope ownership, explicit joined terminal outcomes,
  generated-policy enforcement at the D-Bus export boundary, typed Agent
  completion/reconciliation, completion-unknown control timeouts, browser
  retirement dispatch, and a single disconnect-and-quit completion predicate.
- EC-02, EC-04, EC-06 and EC-07 have local candidate fixes and focused tests.
  The security-boundary fix also received one fresh independent bypass/
  regression review. Full release review and installed validation are pending.
- Follow-up implemented with maintainer approval: account replacement requires
  a process handoff, old-process death verification, and fresh-process saved
  session cleanup before new credentials. Expiry preserves an established
  tunnel until explicit **Prepare sign-in**. The account journal stores no
  credentials. Native, provider-fake and process-liveness tests cover admission.
- EC-01 now has a local candidate fix: in-task public-Down completion evidence,
  another barrier after state changes, and explicit unconfirmed/terminal failure
  on stale Core connection identity. Three hash-checked actual-Core 5.6.10
  conformance cases supplement the existing route matrix. Installed recovery
  and exact-candidate independent review remain required.
- EC-03 now has a local candidate fix: a bounded, session-tagged callback relay
  installs Core's public error callback before enable and joins its own handler
  on close. Authentication failures use expiry; other failures surface degraded
  background updates without disconnecting or replaying failed jobs. Two
  actual-Core scheduler cases supplement provider-free lifecycle and UI tests.
- EC-05 now has a local candidate fix: one native capability policy separates
  Connect from Disconnect and is used by the window, browser, pins, tray,
  shortcuts and confirmations. Explicit cancellation covers busy connection
  lookup, expiry still permits tunnel cleanup, and confirmations recheck current
  permission. Matrix, private-bus and offscreen QML tests pass; no Core or wire
  contract changed. Installed surface acceptance remains pending.
- Retry ownership is consolidated locally: lifecycle callbacks are mandatory
  and the unused direct Core mutation/compensation fallback is removed. The
  production binding still uses the same shared connection owner. Policy tests
  forbid direct Core mutation; adapter tests cover stale account/intent at lock
  admission and after success. Retry policy and networking behavior are unchanged.
- Independent cleanup admission has a local candidate fix: one retained worker
  each for Disconnect and capture Stop, with duplicate requests coalesced.
  Stop bypasses unrelated foreground work; Disconnect waits for an accepted
  non-connect transaction so Core protection changes cannot race Down.
  Successor mutations cannot overtake cleanup, session checks follow waits,
  and busy derives from live ownership. Tests cover held settings saves, both
  cleanup kinds, cancellation, replacement accounts and shutdown failure;
  a combined controller/adapter test and offscreen capture-button matrix pass.
- Close deadline consolidation has a local candidate fix: service, controller
  and adapter share one absolute deadline. Controller and adapter cache the
  first close outcome; repeated/cancelled callers cannot restart teardown or
  refresh its budget. Capture attempts use remaining time without changing
  their durable safety deadline. Retry scheduling is fenced at close admission,
  and expired ownership waits cannot dispatch later teardown stages. Targeted
  tests cover deadline propagation, stuck stages, late completion and sticky
  failure; existing process/systemd retirement bounds are unchanged.
- Cleanup-request deadlines have a local candidate fix: Disconnect and capture
  Stop share one absolute 30-second admission-to-retirement budget per accepted
  owner. Expired pre-dispatch requests are withdrawn without cancelling the
  preceding transaction or running later. Duplicates cannot refresh the budget.
  Adapter ownership waits and provider retirement consume the remaining time;
  unconfirmed retirement uses the existing nonzero process boundary, retaining
  capture recovery state. Targeted controller, adapter, scope and D-Bus tests
  cover both expiry dispositions without live VPN mutation.
- Foreground deadlines now have a local candidate fix: one 180-second budget
  starts before controller admission and covers the complete transaction,
  provider joins, recovery and state publication. Pre-dispatch expiry withdraws
  only that request. Accepted auth/settings work is not cancelled with its
  caller; connection, capture Start and FIDO retain their explicit cancellation
  cleanup. Unconfirmed work at expiry uses the existing process boundary.
  Nested stage limits cannot extend this budget or detach a live provider.
  Independent review and installed acceptance remain separate gates.
- The process boundary resolves the account-replacement design decision without
  changing Core. It does not create a public refresher join capability or close
  installed acceptance gates.
- No new Core overlay, install, commit, publication, mechanics reseal, final
  six-reviewer approval, or soak completion is claimed by this checkpoint.

#### 1. Freeze discovery and specify the contract

- Finish collecting all six independent perspectives against the unchanged
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
