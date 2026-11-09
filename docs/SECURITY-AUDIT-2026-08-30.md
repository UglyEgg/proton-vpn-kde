# Security and engineering assessment

Last updated: 2026-11-09
Release: 0.14.4
Release target: 0.14.5

## Status

This checkout's `feature/secret-service-unlock-prompt` is a separate source-only
follow-up to the accepted startup baseline below. It permits one provider-owned
unlock request during normal admission, while keeping cleanup/retries passive.
It is not independently reviewed, packaged, installed, or accepted by live UAT;
the accepted source seal has not been refreshed to admit it.

Follow-up evidence: 587 backend cases (555 pass, 32 opt-in skips), 87% coverage,
32 source files passing Mypy, 25 isolated actual Core/SSO cases, and seven private-bus
wire cases. Tests cover signal-first completion, a missing RPC reply, cancellation,
timeout/dismissal, owner replacement, forged signals, and the JSON fallback barrier.
Missing/stale aliases use the actual advertised collection as the unlock target.
Private-wire runs retain the installed dbus-fast closed-socket ResourceWarnings
already observed on the baseline; no test fails or pending task is reported.
No live faults, desktop-provider calls, installed-package or network changes were
performed. Review, package and normal provider UAT are the next qualification gates.

### Accepted startup baseline

Version 0.14.5 remains pending; 0.14.4 remains public. The working branch
`fix/startup-credential-recovery` passes native/Fedora package validation and
source tests. Seven isolated reviews and affected rechecks cover the pre-admission
delta; focused reviews and control rechecks cover the admission correction below.
Its unsigned Fedora RPM is installed and integrity-checked. The maintainer accepted
clean-boot UAT on November 9 with KeePassXC 2.8.0, API Core 5.8.11 and keyring
0.2.3-10. Signed source and commit-bound distribution builds still block release.

### Startup-admission correction

- The backend started at 06:40:22 CST; Core activated protection/tunnel profiles
  at 06:40:24, entered `ExpiredCertificate` at 06:40:25, and stopped certificate
  refresh twice. No startup `KeyringLocked` wait was logged. Unlocking the store
  did not recover the attempt. The maintainer restored operation after cycling
  the wired connection; logs also show a fresh backend at 06:43:34 and successful
  connection at 06:43:40. Adapter cycling is not the proposed recovery contract.
- The failed November 8 validation build gated only after a startup keyring exception. Core's Loader
  can instead choose its JSON fallback while Secret Service is unavailable;
  SSO can then report a saved session as logged in and reject a later backend
  change. The preceding validation did not cover this success path.
- A disposable user/network-namespace reproduction using installed SSO, Loader,
  VPN session and Core logged-in getter with synthetic data confirms success through the file backend,
  followed by backend-mismatch RuntimeError when the provider becomes available.
  The public `keyring=secret_service` selector rejects fallback in that fixture.
  Actual backend identity and the first refresh exception were not logged during
  boot; the historical fallback selection remains an evidence-backed hypothesis.
- Local source now requires Secret Service admission before constructing its Core
  API or looking up a session. Initial admission permits one standard activation
  request; existing default/sole collections must be unlocked. An identified
  provider with no collections proceeds to keyring-owned default creation.
  Subsequent lock retries remain passive. Proton's public Secret
  Service selector remains enforced for the process lifetime, preventing JSON
  fallback during startup or subsequent SSO rechecks. Other component overrides
  retain their meaning. Admission/restoration share one deadline; pending cleanup
  retains its shorter bound and record. Owner/collection barriers and Core-owned
  protection remain unchanged. Legacy fallback files are not migrated or deleted.
- Actual SSO/Loader regressions use pinned Base Core 0.7.4, API Core 5.8.11 and
  synthetic storage. They cover blocked cached success, provider loss before
  lookup and during later reads/writes, empty secure storage with legacy data
  present, and the registered selector name. These tests inject no live faults
  and make no installed-package changes. Release qualification remains open.

Focused independent error-class and compatibility/maintainability reviews found
two P2 regressions: dormant-provider activation and zero-collection first use.
Both are closed after one bounded correction and acceptance by both reviewers.
Security diff scan `73d72ad8-fb0a-4329-9cfc-ad2e0f4fc964` covers all 11 original
admission paths with no confirmed in-policy finding. A separate affected-control
recheck accepted the activation/empty-store correction; it is not a second full
scan. Neither review establishes desktop prompting or installed acceptance.

Local Fedora qualification uses unsigned snapshot
`5ea4d1724dc0e1fc4998805b0dd2c4cb9450cce5` (`0.14.5-1.fc44`). All 47 native
groups pass in aggregate after a documentation-only metadata recheck; all 46
archive groups pass with fresh XDG test storage. RPM/SRPM policy and source
identity, all 32 backend payload files, ELF hardening, dependency/conflict dry run,
and isolated payload install/reinstall/integrity/removal pass. Payload transactions
exclude scriptlets/triggers. The build resumed with `--noprep` after isolating
test preferences; this is not clean-root binary reproducibility. The corrected
RPM is installed: root-side RPM integrity passes and all 32 backend source files
match that snapshot. The maintainer accepted clean-boot UAT on November 9. The
backend started once at 02:14:23 CST; Proton profile activation began at 02:15:02,
without a recorded initialization failure or backend restart. Exact unlock timing
and user clicks are not independently observable from these logs. Launch-at-login,
minimized startup and Fastest auto-connect remain enabled. Ubuntu and signed
release builds remain open.

## Startup credential recovery follow-up

- November 4–6 boots repeated `ExpiredCertificate` followed by stopped refresh;
  November 4 also recorded `KeyringLocked` during a backend restart. The original
  unexpected refresh exception type was not logged; its precise trigger is not
  established.
- The patch bounds prewarm recovery, passively observes an already-running
  same-user store, and permits at most one subsequent credential request. It
  preserves account material and the durable-cleanup boundary.
- Unattributed callback failures never re-arm certificate work. One initial
  expired-certificate refresh is admitted per episode; repeated notices, Off/On
  and suspension preserve that admission. Background failures stay degraded with
  explicit restart guidance. Core/networking packages, protection, session
  persistence, and authentication transport are unchanged.
- General backend suite: 557 cases, 535 pass and 22 opt-in skips; 87% coverage.
  Real Core/SSO conformance: 21 pass in disposable user/network namespaces,
  with external I/O replaced and no live API or NetworkManager instance.
- Private D-Bus fixture: 23 cases pass, including stale-alias fallback and
  first-use admission; activation remains bounded to one initial request.
  Both native snapshot/agent CTest groups pass, including queued auto-connect
  across non-ready credential wait.
- Pre-admission snapshot validation: all 47 native CTest groups and all 46 archive-build
  groups pass; package policy, source identity, dependency dry run, and ELF
  PIE/RELRO/NOW/NX checks pass. Its 32 packaged backend files match that snapshot,
  not the new local admission correction.
- Private payload install/reinstall/integrity/removal passes in disposable
  user/network namespaces. Dependency checks use a copied installed RPM database;
  scriptlets and triggers are excluded from those payload transactions.
- RPM/SRPM identity: `0.14.5-1.fc44`, unsigned local-validation snapshot
  `f17f98ce69c9f454ba3943b329a3c4e2e95b5cbc`. The main checkout remains uncommitted.
  One fresh local build ran with one worker and disk-backed temporary storage;
  this is not clean-root distribution qualification or a reproducibility result.
  Ubuntu has not been rebuilt for this follow-up.
- Pre-admission Fedora installation: `proton-vpn-kde-0.14.5-1.fc44.x86_64`; root-side
  RPM integrity passes, the client reports 0.14.5, and all 32 installed backend
  sources match the validated snapshot. Launch-at-login, minimized startup,
  Fastest auto-connect and reconnection preferences are enabled. The November 8
  clean-boot failure above supersedes pending acceptance. The corrected installed
  snapshot is identified above; it requires its own clean-boot acceptance.
- The source seal now includes the accepted admission runtime/test delta after
  its focused reviews and affected rechecks. Qualification/status text does not
  extend source review to unbuilt or untested release packages.

### Pre-admission review scope

Seven reviewers used fresh contexts against the same 18-file working delta
from `8136ebd19af72ae2f2f4051fb21ae47742eb0800`, including untracked source/tests.
All file hashes matched throughout the initial review. Its compact, sorted changed-file
manifest SHA-256 is
`0d79441bdb179f13546665e7435a94df7f0bc99d8111525dcf906cbb5f953146`.
All five affected reviewers accepted the corrected source. Its 18-path manifest
also includes the relay restored byte-identical to the base; its SHA-256 is
`5ca10f5c7cc47dd80a74ae0b53e8369a4d8a24e73380b4c27eeb60897a5a4e3b`.
All hashes matched during those rechecks. This evidence does not cover the new
local startup-admission runtime/test delta.

| Perspective | Result |
| --- | --- |
| Hostile | Conservative worker-ownership correction accepted |
| Subtractive | Removed unsupported re-arm mechanism; correction accepted |
| Entropy | Episode-reset and single-admission behavior accepted |
| Error-Class | Cancellation-cleanup and provider-timeout corrections accepted |
| HPC/Performance | Bounded scope passes; nonblocking descriptor retention below |
| Hardening/Security | No confirmed security defect within SECURITY.md's boundary |
| Cognitive Load/Code Maintainability | All three findings closed; reduced policy accepted |

| Regression boundary | Accepted outcome |
| --- | --- |
| Delayed certificate failure | No callback-triggered re-arm or traceback-origin classification. Deferred handling, episode reset and old-worker cleanup cannot cancel a successor. |
| Stale default alias | Packaged keyring's missing-object fallback; owner, ambiguity and unrelated-error barriers retained. |
| Failure while recovery is Off/suspended | One initial request per episode; callbacks and policy replay cannot add automatic re-arms. |
| Provider-origin TimeoutError | Only the owned deadline's expiration becomes secret-store unavailability; provider timeouts before/after unlock remain unknown failures. |

The new Core regressions hold the successor active while delivering an old
failure, then verify no cancellation or extra fetch and a retained successful
periodic job. Provider and connector regressions use offline fixtures. Native
source is unchanged by these corrections; the earlier two passing native groups
cover the same startup readiness contract.

Nonblocking observations: readiness transports retain descriptors until cyclic
GC in the installed dbus-fast implementation (7 to 31 descriptors after 24
private-bus observations; collection restored 7). This is bounded delayed cleanup,
not an unbounded leak; avoid global GC or private transport access as a workaround.
Degraded-update guidance now names the existing Quit background controls action
and reopen operation. Degraded-background status remains conservative.

Security diff scan `f80f1537-8400-4867-a75e-42f5f755f4da` is complete: all 18
initial files accounted for, no confirmed security findings or deferred candidates.
It covers the original frozen delta, not a new scan of these corrections, a full
audit or live-recovery qualification. Five focused functional rechecks accepted
the corrected delta; no second full security scan is claimed. Signed source,
distribution/reproducibility builds remain
open. The unsigned validation installation above is not a signed release
qualification.

## Earlier candidate evidence

| Scope | Current evidence | Remaining gate |
| --- | --- | --- |
| Earlier candidate | Seven isolated reviews and affected rechecks accepted; backend/Core tests and both distributions' package checks passed | Does not cover the startup follow-up |
| Installed acceptance | Maintainer accepted normal Fedora UAT on the runtime-equivalent local build; Ubuntu remains package-validated | Ubuntu Plasma field acceptance and the limits below |
| Independent assurance | No independent third-party audit or penetration test | Not certified |

Review perspectives are Hostile, Subtractive, Entropy, Error-Class,
HPC/Performance, Hardening/Security, and Cognitive Load/Code Maintainability.
This document reports validation status; it is not a finding-history ledger.
Released review details remain in the corresponding Git tag.

## Earlier candidate branch review

All seven reviewers used fresh contexts and inspected the same 24-file delta
against `3670df64eebeb17be9c3423b623787312fb2773c`, including the new untracked
test and removed documentation text. Its changed-file manifest SHA-256 is
`43262ca40f92bcaa656213c2e7216af8d6e0b823d0fa17bcae64a3807399f26c`.

Hostile, Entropy, Error-Class, and HPC/Performance accepted the bounded
corrections. The corrected review snapshot's seven-file manifest SHA-256 is
`b92cb058c1f1c650533dc9ad843405c50d6324cf308a09591708595f65cf197e`.
It hashes compact JSON of sorted `{path, sha256}` records for the seven reviewed
recovery source/test files, excluding version-only metadata. Final
publication-point changes affect only the adapter and its tests; the accepted
performance sources remain byte-identical. Release preparation changes version
metadata, release-note text, documentation, and release validation, and removes
one trailing blank line from the new regression file. The accepted runtime
files and connection behavior are unchanged.

| Perspective | Result |
| --- | --- |
| Hostile | Corrected replay, pinning, cancellation, and dispatch ownership accepted |
| Subtractive | Initial scope passed; documentation follow-up accepted |
| Entropy | Corrected episode/selection ownership and publication point accepted |
| Error-Class | Corrected preference and pre-dispatch cancellation classes accepted |
| HPC/Performance | Indexed eligibility and scoped projection accepted; independent probe corroborates results |
| Hardening/Security | Initial frozen diff: no reportable security regression within the policy boundary |
| Cognitive Load/Code Maintainability | Initial scope passed; documentation follow-up accepted; no broad refactor recommended |

Security diff scan `638492a5-aaa6-4bbf-a41d-e69fe78e6099` is complete. Its
security pass applies to the original frozen delta, not a new security scan of
the corrections. Protection ownership and the security policy are unchanged.

### Corrected runtime properties

- Preference replay and temporary suspension preserve outage history/backoff;
  healthy unchanged enable does not cancel an owned Up. Actual policy changes
  retain cancellation/join barriers and observer-enable recovery.
- A retained connection keeps its accepted selection across Off/On. New target,
  Disconnect, account retirement, and shutdown clear intent/episode state.
- Selection publishes only after serialized owner, account, and intent checks.
  Caller/policy cancellation of a queued adapter request cannot attach its
  constraints to a retained exact-server tunnel. Ordinary controller requests
  are serialized; this regression proves the adapter contract, not an observed
  native/D-Bus failure sequence.
- Indexed preferred checks do not enumerate the catalog; alternative grouping
  is country-scoped and never sorts the cached full list. Exhausted retries
  do not enumerate another candidate. Timing/allocation evidence and remaining
  linear global-ranking cost belong in [Performance](PERFORMANCE.md#fastest-retry-selection).

The documentation refactor's lifetime, harness-reuse, and upstream-contribution
clarifications passed the three affected factual rechecks. The release seal is
rebaselined only over those reviewed deltas and the release-preparation metadata;
the published tag and its assurance record are unchanged.

## Scope and assurance boundary

Assessment scope includes project-owned native/QML/Python code, D-Bus
interfaces, user services, distribution packaging, and declared downstream
overlays. Unmodified Proton components, NetworkManager, the selected Secret
Service provider, and Proton's service are trusted dependencies, not audited
components.

The authoritative attacker model, invariants, exclusions, and disclosure
process are in [SECURITY.md](../SECURITY.md). Implementations are specified in
[Architecture](ARCHITECTURE.md), [Authentication](AUTHENTICATION.md), and
[Hardening](HARDENING.md). These validation results do not change that policy.

## Earlier candidate package validation

Evidence below covers the final corrected runtime. Local UAT RPM
`proton-vpn-kde-0.14.4-2.fc44.x86_64` was built from disposable snapshot commit
`d28664955182f2b31eb716e60bfc421365bf8777`; only its package revision/changelog
differ from the reviewed recovery snapshot. It is unsigned and unpublished, not
a release candidate commit in the development checkout. The maintainer accepted
normal UAT on 2026-10-21. Version-only release preparation does not extend that
acceptance to a new failure mode or to unbuilt final artifacts.

Complete candidate package builds and signatures used signed commit `10d2b7f`,
including the packaging-only identity correction. Publication-point metadata
does not change client/Core runtime sources or overlay patch series.

| Check | Result and scope |
| --- | --- |
| Backend suite | 499 registered cases: 486 pass, 13 opt-in Core cases skipped in the general suite; 87% combined coverage |
| Core 5.8.3 / 5.8.11 | Each selected, hash-checked fixture passes 13 cases in disposable user/network namespaces; provider I/O is substituted |
| Fastest regressions | 24 selection/retry tests plus adapter replay-at-budget-stages, owned Up, concurrent policy changes, scoped Off/On, queued cancellation, account/target/shutdown retirement; actual-Core free/location/Secure Core and preferred work-bound checks |
| Protection ordering | Actual Core dispatcher/state tasks exercise two server changes with Off/On/Permanent modes; policy does not disable IPv6 leak protection |
| Source analysis | Mypy, Ruff, SPDX/provenance, generated contracts, compatibility metadata, release metadata, documentation links, and local section anchors pass for the frozen candidate |
| Native integration | Rebuilt 0.14.5 with GCC/KStatusNotifier; all 47 source-checkout CTest groups pass, including prepared/public metadata regressions, Git-history negative controls, staged install, and the eight-view visual matrix |
| Fedora RPM/SRPM | Two clean candidate builds pass all 46 archive-build CTest groups; all eight RPM/SRPM/debug outputs match byte-for-byte; artifact policy, offline install/reinstall/integrity/removal, demo startup, and ELF hardening pass |
| Ubuntu packages | Two clean candidate builds pass all 46 CTest groups and the backend suite; 13 binary/source/debug artifacts match byte-for-byte; six build records differ only by timestamps and their checksums; policy, offline install/reinstall/autopkgtest/removal, and actual-Core 5.6.10 selection checks pass |
| Overlay identities | Fedora keyring revision 11 has reproducible RPM/SRPM output; runtime source and bytecode bodies are unchanged. Ubuntu overlay binary/source artifacts retain their published identities. Nine boundary tests and a real-vendor changed-README rejection pass; source provenance and candidate package/checksum signatures verify |
| Validation conditions | Disk-backed temporary storage and one build/test worker; one unchanged package-suite rerun passed after two visual timeouts under concurrent host load; no time limits relaxed or checks omitted |
| Native analysis limit | Native C++ behavior and QML mechanics are unchanged; release preparation updates version/display text. Clang-Tidy and sanitizer analysis were not repeated for the recovery correction |
| Inspector retention | Two-cycle isolated 0.14.5 probe completed; results and warm-up/whole-client limits are recorded in [Performance](PERFORMANCE.md#inspector-probe) |
| Local installation | RPM upgrade and root-side integrity check pass; installed version and three changed backend modules match the validated payload; Core/keyring packages unchanged |
| Live branch acceptance | Maintainer accepted normal UAT on the exact installed local RPM; no live fault injection performed |
| Review seal | Release seal covers the accepted runtime deltas; publication-point changes are limited to status/documentation |

## Installed baseline acceptance

| Target | Established evidence | Limit |
| --- | --- | --- |
| Fedora with Core `5.8.11-1.plasmavpn1.fc44`, keyring revision 10 | Local client `0.14.4-2.fc44` installed, verified, and accepted for normal UAT on 2026-10-21 | No live Fastest failover, protocol, roaming, suspend/endurance, or packet-confidentiality qualification |
| Ubuntu 26.04 | Binary/source package build, payload/dependency policy, install/reinstall, autopkgtest, and client-removal checks | Live Plasma lifecycle and Secret Service UAT pending |

The public baseline's accepted native-plugin trial used an independent rescue
timer and deny-only fence. Its temporary harness is excluded from release source/packages;
[Hardening](HARDENING.md#fault-test-isolation) owns its reuse requirements.
No new live-fault claim is made.

## Open assurance work

- Obtain Ubuntu Plasma field acceptance and live Secret Service restart UAT.
- Qualify prolonged outage, suspend/roaming, and global resource-pressure
  recovery; a successful handshake alone does not prove usable browsing.
- Measure current-stack whole-client retention; component measurements in
  [Performance](PERFORMANCE.md) are not an application memory budget.
- Obtain independent review before using an independently audited or certified
  label.

Qt/Python secret-copy lifetime, initial Secret Service provider trust,
session-bus snapshot exposure, and deployment confinement limits remain as
documented in the policy and hardening references. NetworkManager may
materialize the unsaved Protun profile as a root-only mode-0600 file under
`/run`; this does not provide protection against root or process-memory access.

No unresolved validated packaged-runtime finding is recorded for the reviewed
public baseline. That is a bounded assessment result, not proof that the code
is free of defects.
