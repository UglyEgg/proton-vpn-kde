# Security and engineering assessment

Last updated: 2026-10-21
Release: 0.14.4
Release target: 0.14.5

## Status

Version 0.14.5 is prepared for release on `fix/fastest-bounded-failover`.
Version 0.14.4 remains public. Seven isolated reviews and affected corrected-diff
rechecks are complete; no runtime finding remains open. Fedora native/package
checks and maintainer-observed normal UAT passed. Signed candidate `84016fe`
passes both distributions' clean-build/reproducibility and offline lifecycle
checks. The packaging-only identity correction is separately verified.
Publication requires signed, exact-source artifacts; final build evidence is
recorded alongside their artifact manifests.

| Scope | Current evidence | Remaining gate |
| --- | --- | --- |
| Public release | Seven isolated perspectives reviewed frozen runtime/overlay snapshot `fd1e3fef24f3277c075c6035d8083ca9a38205b5afd8bf920c1c53f94432812f`; no unresolved packaged-runtime finding was reported | New runtime changes require a new review |
| Release target | Seven isolated reviews and affected rechecks accepted; backend/Core tests, both distributions' candidate package checks, and normal Fedora UAT passed | Verified source/package signatures, exact-source artifacts, and publication |
| Independent assurance | No independent third-party audit or penetration test | Not certified |

Review perspectives are Hostile, Subtractive, Entropy, Error-Class,
HPC/Performance, Hardening/Security, and Cognitive Load/Code Maintainability.
This document reports validation status; it is not a finding-history ledger.
Released review details remain in the corresponding Git tag.

## Branch review

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

## Working-branch validation

Evidence below covers the final corrected runtime. Local UAT RPM
`proton-vpn-kde-0.14.4-2.fc44.x86_64` was built from disposable snapshot commit
`d28664955182f2b31eb716e60bfc421365bf8777`; only its package revision/changelog
differ from the reviewed recovery snapshot. It is unsigned and unpublished, not
a release candidate commit in the development checkout. The maintainer accepted
normal UAT on 2026-10-21. Version-only release preparation does not extend that
acceptance to a new failure mode or to unbuilt final artifacts.

Complete candidate package builds used signed commit `84016fe`. Subsequent
overlay identity checks cover the packaging-only follow-up;
client/Core runtime sources and patch series are unchanged.

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
| Overlay identities | Fedora keyring revision 11 has reproducible RPM/SRPM output; runtime source and bytecode bodies are unchanged. Ubuntu overlay binary/source artifacts retain their published identities. Nine boundary tests and a real-vendor changed-README rejection pass; signature and exact-source artifact checks remain release gates |
| Validation conditions | Disk-backed temporary storage and one build/test worker; one unchanged package-suite rerun passed after two visual timeouts under concurrent host load; no time limits relaxed or checks omitted |
| Native analysis limit | Native C++ behavior and QML mechanics are unchanged; release preparation updates version/display text. Clang-Tidy and sanitizer analysis were not repeated for the recovery correction |
| Inspector retention | Two-cycle isolated 0.14.5 probe completed; results and warm-up/whole-client limits are recorded in [Performance](PERFORMANCE.md#inspector-probe) |
| Local installation | RPM upgrade and root-side integrity check pass; installed version and three changed backend modules match the validated payload; Core/keyring packages unchanged |
| Live branch acceptance | Maintainer accepted normal UAT on the exact installed local RPM; no live fault injection performed |
| Review seal | Release-preparation seal covers the accepted deltas and metadata; the public tag/seal is unchanged |

## Installed acceptance

| Target | Established evidence | Limit |
| --- | --- | --- |
| Fedora with Core `5.8.11-1.plasmavpn1.fc44`, keyring revision 10 | Local client `0.14.4-2.fc44` installed, verified, and accepted for normal UAT on 2026-10-21 | No live Fastest failover, protocol, roaming, suspend/endurance, or packet-confidentiality qualification |
| Ubuntu 26.04 | Binary/source package build, payload/dependency policy, install/reinstall, autopkgtest, and client-removal checks | Live Plasma lifecycle and Secret Service UAT pending |

The public baseline's accepted native-plugin trial used an independent rescue
timer and deny-only fence. Its temporary harness is excluded from release source/packages;
[Hardening](HARDENING.md#fault-test-isolation) owns its reuse requirements.
No new live-fault claim is made.

## Open assurance work

- Before publication, verify the follow-up's source signature, reproducible
  complete artifacts, and package/checksum signatures; candidate evidence alone
  does not establish the final source identity.
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
