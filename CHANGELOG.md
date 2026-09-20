# Changelog

The project follows [Semantic Versioning](https://semver.org/) while pre-1.0.

## [0.14.1] - 2026-09-20

### Proton Core 5.7

- Rebase the verified Fedora API-Core overlay onto Proton's signed 5.7.0
  package while retaining all five bounded compatibility patches.
- Preserve Core's permanent firewall kill-switch service and final-removal
  cleanup contract.
- Keep Core 5.7's optional connection telemetry disabled by default in
  community builds, both in the live event queue and on explicit settings
  writes. Necessary Proton account, server, and VPN traffic is unchanged.
- Surface telemetry availability and state in Settings and copied community
  diagnostics. Telemetry-capable builds expose an explicit switch; fresh Core
  profiles remain off until the user opts in.
- Drain already queued telemetry events on opt-out and fail closed when the
  installed Core cannot enforce the requested policy.

### Connection insight

- Show the VPN exit address reported at connection time in the Connection
  view and Inspector. In split-tunnel mode, label the device-side address
  separately; these are observations, not a live external-IP probe.

### Setup and support

- Add a read-only local setup view for backend/Core readiness, required Fedora
  or Ubuntu package capabilities, and Secret Service advertisement. The check
  does not activate or open the secret provider.
- Add a previewable, allowlisted community diagnostics report with explicit
  clipboard copy and a separate issue-tracker link. Direct Proton submission
  remains disabled; its inactive form is retained behind disclosure.
- Preserve the previous settings and snapshot contracts across an in-place
  package upgrade, with explicit restart guidance for unknown future versions.
- Run package-capability inspection only from Local setup and keep its result
  independent from the Secret Service readiness signal.

## [0.13.1] - 2026-09-13

### Packaging

- Add Ubuntu 26.04 amd64 binary and source Debian packages for the client,
  provider-neutral keyring overlay, and API-Core overlay.
- Reconstruct Proton's SHA-256-pinned Ubuntu API Core 5.6.10 payload and reject
  changes outside the same six reviewed Python sources used by Fedora.
- Add clean-container build, artifact-policy, install/reinstall, autopkgtest,
  removal-boundary, and release-artifact gates for all three packages.

### Maintenance

- Raise the supported `cryptography` floor to 50.0.0, including its CFFI 2.0.0
  dependency, while retaining hash-pinned Python 3.11 Linux x86_64 coverage.

## [0.13.0] - 2026-09-13

### Plasma interface

- Replace sidebar navigation with a graphical Connection home, contextual
  actions, native back navigation, and an app-sized non-resizable window.
- Show split tunneling as a smooth, arrow-free route to separate VPN and
  outside-VPN destinations; keep server facts beside the VPN endpoint.
- Group Settings by Connection, Protection, Plasma, and Diagnostics while
  preserving page/tab position across asynchronous saves.
- Add progressive server discovery with combined P2P, Streaming, Tor, and
  Secure Core filters, state/city groups, exact servers, search, and pins.
- Present one authentication step at a time and route signed-out startup to
  Sign in. Keep delayed Secret Service and two-factor states explicit.
- Add an on-demand read-only Connection Inspector and concise in-app release
  notes. Keep unsupported Proton report/crash submission visibly disabled.
- Add color, light-symbol, and dark-symbol icons for the Control Center and tray.

### Plasma lifecycle

- Split the resident tray, shortcut, notification, pin, and auto-connect path
  into a lean native agent; keep the QML Control Center and Python backend
  on demand when disconnected.
- Add opt-in KDE login launch, window/tray startup, and saved auto-connect.
  Installation does not enable or overwrite autostart configuration.
- Require confirmation for KRunner, shortcut, and tray mutations. Closing the
  window preserves an active tunnel; disconnect-and-quit waits for Core.
- Make backend lifetime event-driven, preserve active-tunnel/capture
  supervision, and bound startup, retry, and shutdown ownership.

### Correctness and recovery

- Bind asynchronous requests to backend, account, foreground, operation,
  connection-intent, and capture generations as applicable. Stale replies
  cannot complete or overwrite replacement work.
- Distinguish request acknowledgement, observed state, retirement, and
  completion unknown. Reconcile timed-out mutations without replay.
- Serialize Core settings access, make KConfig publication depend on confirmed
  persistence, and retain write errors without navigating away.
- Keep Disconnect and capture Stop available as risk-reducing operations.
  Preserve capture deadlines and cleanup across backend replacement.
- Join cancelled Core connection work and compensate before releasing ownership;
  prevent automatic recovery from racing a newer manual target.
- Preserve authenticated state when connector initialization fails and expose
  explicit retry without repeated Secret Service prompts.
- Normalize inherited native loader/search overrides before Qt startup so KDE
  launcher environments do not fail backend authorization.

### Proton integration

- Ship a provider-neutral Proton keyring overlay that handles absent/stale
  Secret Service default aliases, reuses one connection, requires the selected
  provider to run as the session user, and pins its unique owner.
- Rebase the API-Core overlay onto Proton's signed Fedora 5.6.20 package with
  exact changed-path and provenance manifests.
- Keep Protun's transient key in Core's unsaved NetworkManager profile, preserve
  queued reconnect targets, and explicitly reactivate reusable validated
  protection profiles.
- Retain bounded server-string sharing and deprecated FIDO2-query cleanup.
  Disable the unsafe security-key route until Core provides complete cancellable
  multi-key selection.

### Security and performance

- Encrypt authentication fields with sender/method-bound one-use keys and pass
  only sealed ciphertext descriptors over D-Bus.
- Verify and pin packaged D-Bus peers, authorize actual senders at ingress and
  dispatch, revoke on owner loss, and sanitize loader/runtime environments.
- Bound descriptors, reads, support diagnostics, subprocesses, packet capture,
  and process retirement. Keep community support/crash submission disabled at
  independent UI, native, backend, and package gates.
- Replace per-query server-object expansion with a generation-scoped scalar
  search projection; retain current Core load and access data.
- Complete the seven-perspective release review and regression corrections with
  no substantiated P0/P1 finding.

### Build and release

- Generate D-Bus contracts and snapshot validators from authoritative schemas;
  enforce SPDX, provenance, patch manifests, exact source archives, and
  reproducible Fedora package metadata.
- Run Python minimum-version/type/coverage checks, Clang-Tidy, sanitizers, QML
  diagnostics/layout/visual gates, and complete RPM/SRPM policy checks in CI.
- Run source and package workflows once per pull request. Reserve repeated
  package reproducibility builds and retained artifacts for tags/manual runs;
  isolate retry attempts from their original concurrency group.

## 0.12.0 — internal development milestone

Completed 2026-09-01 and never tagged or published; included in 0.13.0.

- Established the on-demand Inspector and event-driven backend lifetime.
- Added account/backend generation fencing and completion-unknown recovery.
- Added owner-pinned Secret Service integration and fresh-process account
  replacement.
- Added reproducible package builds, environment sanitization, and durable
  packet-capture recovery.
- Established the accepted mechanics baseline used to scope the 0.13 UI work.

## [0.11.3] - 2026-08-31

- Keep Protun's transient key in its unsaved NetworkManager profile.
- Clear cached account/tunnel state when the backend stops.
- Add explicit recovery after incomplete saved-session restoration.
- Build and verify client, keyring, and API-Core RPM/SRPM pairs.

## [0.11.2] - 2026-08-30

- Add provider-neutral KeePassXC-compatible keyring packaging and explicit
  client capability dependencies.
- Add capability-aware server filters, group/server pins, and startup-safe
  browsing retries.
- Decompose native, QML, and Python concentration points without changing their
  public facades.
- Add backend identity/sender authorization, sealed secret transport, logout
  compensation, descriptor ownership, capture bounds, and KRunner confirmation.
- Add native analysis/sanitizers, Python typing/coverage, SPDX/provenance,
  generated D-Bus contracts, reproducible Fedora packaging, and demo memory
  measurements.
- Disable Proton support/crash submission in community builds.
- Add selectable tray/application symbols and Settings/System Settings sharing.

## [0.11.1] - 2026-08-29

- Embed the application mark and adopt the independent Plasma VPN identity.
- Correct dynamic page lifetime and inactive sign-in reactions.
- Move services into `quest.entropy.PlasmaVPN` and add public project policy.
- Preserve Settings navigation after Core writes.

## [0.10.2] - 2026-08-29

- Preserve Settings after successful VPN configuration changes.
- Limit automatic Overview navigation to sign-in completion.
- Add settings-navigation regressions.

## [0.10.1] - 2026-08-29

- Route signed-out startup to Sign in.
- Prevent authentication from racing connector initialization.
- Explain delayed Secret Service approval.

## [0.10.0] - 2026-08-29

- Add responsive Kirigami navigation and shared Plasma visual components.
- Add compact, scaled-text, RTL, UI-hygiene, and screenshot checks.

## [0.9.0] - 2026-08-29

- Split tray, shortcut, and notification behavior into a native agent.
- Make the Kirigami Control Center on demand.
- Retire disconnected idle backends while supervising active tunnels.

Earlier milestones remain in the Fedora spec changelog and Git history.
