# Security and engineering assessment

Last updated: 2026-09-13
Release: 0.13.1

The unreleased 0.14.0 preview is outside this release assessment. Its new
connection-address presentation, local setup checks, and community diagnostic
preview have focused tests, but have not completed the seven-perspective
release review or installed acceptance.

## Status

No open release-blocking finding is recorded for the 0.13.1 package
update. The 0.13.0 runtime review found no P0 or P1 issue; its six findings were
corrected and have regression coverage. Later Fedora and Ubuntu packaging,
Core-overlay, provenance, CI, and documentation changes are covered by their
own policy and compatibility tests.

This is a maintainer-directed, AI-assisted assessment. It is not an independent
third-party audit, penetration test, certification, or warranty.

## Scope and assurance boundary

The assessment covers project-owned C++, QML, Python, D-Bus interfaces,
systemd user services, Fedora and Ubuntu packaging, and the two downstream
overlay families. It evaluates the interaction boundary with Proton VPN API
Core but does not audit Proton's service, NetworkManager, the Secret Service
provider, or unmodified Proton packages.

The local attacker is an ordinary or sandboxed process in the same graphical
session that can reach D-Bus but cannot already execute arbitrary native code
as the desktop user. The design does not claim to defend against root, a
debugger, or arbitrary same-UID native code. A stronger same-UID boundary would
require a privileged or MAC-enforced service architecture.

Official Proton Core remains authoritative for:

- VPN protocols and credentials;
- NetworkManager profiles, routing, and DNS;
- kill switch and IPv6 leak protection;
- split tunneling and server scoring; and
- account-session persistence.

Community code owns desktop presentation, input validation, D-Bus policy,
operation ownership, process lifetime, and downstream package integration.
The distribution API-Core packages contain declared, version-pinned patches
and must not be represented as unmodified Proton binaries.

## 0.13.0 review result

Seven isolated reviewers assessed frozen source
`0912144793b8a149b8b2e2933bd8c78b71470214` on 2026-09-09. Findings were
consolidated only after every reviewer reported.

| Perspective | Result | Finding IDs |
| --- | --- | --- |
| Hostile | Corrections required | RC1, RC2; corroborated RC4 |
| Subtractive | Pass | None |
| Entropy | Corrections required | RC3, RC4 |
| Error-Class | Pass | Two non-blocking cached-projection notes |
| HPC/Performance | Correction required | RC6 |
| Hardening/Security | Low-severity correction required | RC5 |
| Cognitive Load/Maintainability | Pass | Two non-blocking reuse notes |

All required corrections are in
`17791c7df59c6a2e3d5404999a2d1044dbb3023a`.

| ID | Priority | Finding | Resolution |
| --- | --- | --- | --- |
| RC1 | P2 | Busy first startup could consume and lose auto-connect intent | Startup retains the one-shot intent until admissible; busy-to-idle regression added |
| RC2 | P2 | Tray-owned startup intent could later replay from the window | Startup owner is selected once; preference/refresh replay regressions added |
| RC3 | P2 | Tray-only launch could exit before activation or fallback settled | A bounded launch transaction owns activation and fallback through completion |
| RC4 | P2 | KConfig write failure could be displayed as accepted state | Writes require persistence/readback before publication; immutable/unwritable cases covered |
| RC5 | P3 / low | Broker-controlled rich text could trigger pre-consent image loading | Confirmation data is plain text; denied-I/O and markup regressions added |
| RC6 | P2 | Offline search benchmark was unauthenticated and measured no search | The fixture uses an explicit offline authenticated cache and prohibits login/network I/O |

The review's security scan covered 71 of 333 tracked paths. That coverage is
not an exhaustive repository audit and is not combined with older partial
scans to manufacture a higher figure.

## Release-specific engineering corrections

| ID | Class | Failure | Resolution and evidence |
| --- | --- | --- | --- |
| PKG-01 | Test isolation | Clean Fedora builds inherited desktop cache, translation, and theme assumptions | Tests own XDG/cache inputs; RPM builds declare Breeze and platform-theme fixtures; clean builds pass |
| START-01 | Authorization availability | KDE launchers could pass Qt search overrides that failed backend identity policy | Native entry points sanitize and re-exec before Qt initialization; cold-launch authorization passes |
| START-02 | Recovery availability | A manually disconnected protection profile could remain inactive and cause startup retry loops | Client holds a stable signed-in/not-ready error; Core overlay reuses and explicitly activates validated profiles; 14 overlay cases and installed recovery pass |

The START-02 patch changes protection-profile activation, not the protection
rules. It is isolated in the API-Core overlay manifest and exact-path policy.

## Historical security findings

The original 0.11 review found seven issues. All remain closed and covered by
regression tests.

| ID | Severity | Historical defect | Current control |
| --- | --- | --- | --- |
| PV-SEC-001 | High | Substituted backend could receive authentication secrets | Installed backend identity verification, unique-owner pinning, sender-bound one-use keys |
| PV-SEC-002 | Medium | Mutating D-Bus calls lacked caller authorization | Ingress sender capture, generated method classification, authorization recheck before dispatch |
| PV-SEC-003 | Medium | Failed logout could leave kill switch disabled | Transactional logout with protection-state compensation and fail-closed recovery |
| PV-SEC-004 | Medium | Rejected report calls leaked transferred descriptors | Connection-wide exactly-once descriptor ownership and rejection cleanup |
| PV-SEC-005 | Low | Optional support logs had no byte ceiling | Per-source and aggregate limits; direct Proton submission remains disabled |
| PV-SEC-006 | Low | Capture orchestration lacked duration enforcement | Positive Core byte-cap validation, 15-minute watchdog, serialized stop ownership |
| PV-SEC-007 | Medium | KRunner's shared process was trusted as a backend client | KRunner is untrusted; bounded requests require Control Center confirmation |

The 0.12/early-0.13 lifecycle work additionally closed classes involving stale
backend generations, cancellation-detached provider work, account-transition
races, completion-unknown writes, capture cleanup, unbounded read ownership,
and reconnect/manual-intent collisions. The current architecture expresses
those controls as generation-bound ownership and explicit evidence contracts;
the commit history retains the per-defect development record.

## Current controls

### Service and caller identity

- Backend, agent, and Control Center are D-Bus activated through dedicated
  systemd user services with root-owned absolute executable paths.
- Native clients resolve and verify the backend's unique owner before protected
  calls; calls, replies, and signals remain pinned to that owner generation.
- The backend captures the actual D-Bus sender at ingress and reauthorizes it
  immediately before protected dispatch.
- Authorization, leases, and pending secret keys are revoked on owner loss.
- Public desktop brokers expose explicit allowlists and cannot directly invoke
  an authenticated VPN controller.

### Authentication transport

- Secret fields are encrypted with an operation- and sender-bound X25519 /
  HKDF-SHA256 / AES-256-GCM key.
- Ciphertext crosses D-Bus in a sealed, rewound Linux `memfd`; plaintext is not
  placed in D-Bus arguments, snapshots, notifications, or logs.
- Keys are one-use, payloads are limited to 16 KiB, field sets are allowlisted,
  and descriptors close on every path.
- Provider exceptions are mapped to fixed public errors.

### Secret Service

- The keyring overlay activates or selects the desktop's Secret Service,
  requires the provider to run as the session user, and pins calls and prompt
  signals to its unique owner.
- Missing or stale `default` aliases are handled without provider-specific
  KeePassXC logic.
- The initially selected same-user provider is a trusted dependency; portable
  D-Bus APIs cannot attest its package provenance.

### Operation and lifecycle ownership

- Requests carry backend, account, foreground, and operation generations as
  applicable; stale replies cannot mutate current state.
- Transport timeout means completion unknown. Fresh state may release a wait
  but cannot synthesize acknowledgement of the timed-out mutation.
- Accepted provider work survives caller cancellation until it completes,
  compensates, or reaches the process-retirement boundary.
- Disconnect, capture Stop, logout, and shutdown retain independent
  risk-reducing paths.
- Backend shutdown uses one absolute deadline, drains admitted work, joins
  service-created threads, and exits nonzero if safe retirement is unconfirmed.
- Active tunnels and capture recovery keep the backend alive; disconnected idle
  state uses event-driven retirement rather than polling.

### Resource and privilege controls

- Services are unprivileged and use `NoNewPrivileges=true`.
- Generated environment policy removes dynamic-loader, OpenSSL-provider,
  GIO/GI, Python, Qt-plugin, and QML search overrides before imports.
- Project subprocesses use fixed packaged paths and bounded execution.
- Support collection is dormant in community builds and capped at 1 MiB per
  source, 2 MiB total, and 20 seconds.
- Capture requires Core's positive reviewed byte cap and an existing writable
  absolute destination; the client neither uploads nor rewrites PCAP data.
- Repository switching uses fixed package names and arguments through Polkit;
  no user-selected shell command reaches DNF.

## Verification record

| Evidence | Result |
| --- | --- |
| Frozen seven-review battery | Six bounded findings; all corrected; no P0/P1 |
| Native suite | 45 registered CTest targets, including D-Bus, QML, lifecycle, package-policy, and visual gates |
| Python/Core suite | 448 backend and Core-conformance cases at the release checkpoint |
| Native analysis | Full production set under Clang-Tidy and address/leak/undefined-behavior sanitizers |
| Python analysis | Mypy, Ruff, and branch-coverage floor |
| Fedora packaging | Client, keyring overlay, and API-Core overlay RPM/SRPM policy checks |
| Ubuntu packaging | Client, keyring overlay, and API-Core overlay binary/source `.deb` policy and lifecycle checks; live Plasma UAT pending |
| Reproducibility | Client and both overlay package pairs use normalized source/package metadata; tag workflow repeats release builds |
| Installed UAT | Authentication, server browsing, settings, connection/disconnection, tray behavior, START-01 launch, and START-02 recovery accepted on Fedora 44 |

Release CI also checks minimum Python dependencies, generated D-Bus contracts,
SPDX/provenance, documentation links, exact overlay path manifests, mechanics
scope, visual fixtures, and source-archive reproducibility. Package and source
checks are evidence for the exact revision they run against; they are not
transferable to later Proton Core, Fedora, Qt, KDE, or package revisions.

## Residual risk

- No independent security audit or penetration test has been completed.
- Same-UID native code, root, debuggers, and process-memory access are outside
  the threat boundary.
- Qt and Python may retain immutable secret copies until allocator reuse.
- Proton Core, NetworkManager, the selected Secret Service provider, and Proton
  services are trusted dependencies outside this assessment.
- The provider-neutral keyring and Protun fixes remain downstream overlays
  until equivalent upstream releases are verified.
- NetworkManager may materialize the unsaved Protun profile as a mode-0600 file
  below `/run`; root, NetworkManager, and disk-backed swap are outside the
  project's confidentiality boundary.
- Any session peer can request a bounded confirmation dialog through public
  desktop brokers. It cannot silently mutate VPN state through that path.
- `systemd-analyze security --offline=yes --user` rates both desktop services
  9.0, `UNSAFE`, chiefly because a functional desktop VPN adapter needs host
  networking, D-Bus, home-state, and device access. This heuristic is not a
  vulnerability finding. Candidate sandbox additions require live Core, FIDO2,
  capture, KRunner, KCM, tray, and procfs identity regression testing.

Security reports must follow [SECURITY.md](../SECURITY.md). Architecture,
authentication transport, and deployment controls are specified in
[Architecture](ARCHITECTURE.md), [Authentication](AUTHENTICATION.md), and
[Hardening](HARDENING.md).
