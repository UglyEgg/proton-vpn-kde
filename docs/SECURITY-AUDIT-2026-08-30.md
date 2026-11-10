# Security and engineering assessment

Last updated: 2026-11-10
Release: 0.14.4
Release target: 0.14.5

## Current status

No unresolved validated client finding remains from this review battery.
Seven isolated reviewers assessed `3670df6..e7b4956`; two related P2 findings
were corrected in one bounded patch and accepted by affected reviewers. The
P3 EOF cleanup passes aggregate whitespace checks. The approved Ubuntu 5.8.11
rebase passed focused compatibility, consistency and security-control rechecks.

The reviewed corrections extend beyond the installed source. Normal UAT
covers signed `e7b4956`, accepted November 10, not every later correction or
final package. Signed-source client builds, distribution transactions, final
reproducibility, CI and publication remain release gates.

## Current evidence

| Gate | Result and scope |
| --- | --- |
| Backend | 590 registered cases: 558 general passes and 32 opt-in skips; 88% general-suite coverage; 32 modules pass Mypy |
| Actual Core/SSO | 25 cases pass on each Fedora/Ubuntu 5.8.11 fixture with Base Core 0.7.4; both original Ubuntu and installed single-read SSO hashes are pinned |
| Private-bus wire | Seven cases pass on Fedora dbus-fast 2.45.1 and Ubuntu 4.0.0; synthetic providers, no desktop Secret Service calls |
| Protection handoff | Actual Core state/dispatcher fixtures assert the complete permanent-mode protection-call trace, including intermediate handoffs; routing replay uses dummy interfaces in isolated user/network namespaces |
| Client correction | Three added regression methods cover seven-route failed/cancelled preflight, accepted-selector retention and rejected Up while certificate refresh is live; red-before/green-after; affected Entropy/Error-Class rechecks pass |
| Native | Installed baseline RPM passed 46 archive groups; refreshed release-note layout, hygiene and metadata groups pass; final full source/package run pending |
| Ubuntu Core package | `5.8.11-1plasmavpn1` from authenticated APT input; six declared Python body changes and one pinned unit relocation; all compiled bytes preserved; 13 boundary/mutation cases pass |
| Ubuntu repeatability | Core DEB/original archive/Debian delta/DSC repeat byte-for-byte; buildinfo differs only in Build-Date, changes only in corresponding checksums |
| Ubuntu hooks/policy | Generated default/saved-enable/upgrade/remove/purge paths pass with mocked commands; Lintian error gate passes; two inherited vendor warnings remain |
| Keyring | Ubuntu `0.2.3-10plasmavpn1` rebuilt from unchanged pinned inputs; Fedora revision 11 is the earlier documentation-only package identity |
| Installed UAT | Fedora client `0.14.5-1.fc44` from `e7b4956`: root RPM integrity and all 32 backend files verified; maintainer accepted normal operation November 10 |

The installed stack is Fedora 44, KeePassXC `2.8.0-2.fc44`, API Core
`5.8.11-1.plasmavpn1.fc44`, and keyring `0.2.3-10.plasmavpn1.fc44`.
Its API-Core input came from beta. Ubuntu uses Proton's authenticated stable
5.8.11 input. Live KWallet prompting and Ubuntu Plasma lifecycle remain unqualified.

## Review disposition

| Perspective | Disposition |
| --- | --- |
| Hostile | No behavioral finding |
| Subtractive | No P1/P2; EOF-only P3 removed and whitespace gate passes |
| Entropy | Premature loss of accepted Fastest policy corrected; affected recheck accepted |
| Error-Class | Premature certificate re-arm corrected; affected recheck accepted |
| HPC/Performance | No finding; bounded selection and transport-retention probes pass |
| Hardening/Security | No reportable finding in initial immutable aggregate diff; later client/Ubuntu affected controls accepted |
| Cognitive Load/Code Maintainability | No finding; supplemental metadata/doc consolidation accepted; optional simplifications deferred |

Initial security scan `50d6b729-1342-4e94-a52e-dfec10feea58` is sealed: all
47 changed paths accounted for, zero candidates/deferred work. It covers
`e7b4956`, not later edits. Client correction SHA-256:
`c41b75ec79831d2b3abec3281fa6d6052d689bb2a2840adb081e57d50b6bcc2e`.
Ubuntu rebase SHA-256:
`26fd846b23427faf0bf8810ba87a5abd37beacfc6035445ede637472fd076007`.
These bounded rechecks are separate from the sealed scan and require human
release review; no automatic merge is approved.

The old Ubuntu 5.6.10 permanence difference is a pre-existing vendor limitation,
not an observed leak or introduced client regression. Raising the required
baseline to 5.8.11 closes that target qualification gap. Old 5.6.10 is not newly
qualified. Boot-unit usrmerge relocation preserves content/mode/hash and
Proton's disabled default, saved enablement and removal behavior.

## Remaining release gates

1. Final metadata/source-seal checks and signed local preparation commits.
2. Immutable-source Fedora/Ubuntu client builds, full package policy,
   transactions and reproducibility; retain the Ubuntu package-validated tier.
3. Focused installed acceptance for any changed runtime, then authorized PR/CI,
   merge, signed tag/artifacts, publication and download verification.

## Scope and assurance limits

Scope covers project-owned native/QML/Python, D-Bus, services, packaging and
declared overlays. Unmodified Proton components, NetworkManager and the selected
Secret Service remain trusted dependencies. [SECURITY.md](../SECURITY.md) owns
the attacker model, invariants and exclusions; this record changes none of them.
This is maintainer-directed source/package assessment, not third-party certification.

Normal UAT and synthetic traces do not establish packet confidentiality,
prolonged outage, suspend/roaming or resource-exhaustion recovery. No live fault
tests occurred. [Performance](PERFORMANCE.md) distinguishes component probes from
whole-client budgets. dbus-fast transport-cycle warnings match its bare baseline;
no production global-GC workaround is added.

Qt/Python secret-copy lifetime, initial provider trust, session-bus snapshots and
deployment limits retain the [hardening](HARDENING.md) bounds. NetworkManager may
materialize the unsaved Protun profile in a root-only mode-0600 file under /run;
root and process-memory access remain outside the confidentiality claim.
The temporary recovery harness is excluded from source/packages. Historical
review details remain in Git, separate from the current issue disposition above.
