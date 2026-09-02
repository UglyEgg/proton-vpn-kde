# Changelog

All notable user-visible changes are recorded here. The project follows
[Semantic Versioning](https://semver.org/) while it remains pre-1.0.

## [Unreleased]

- Begin the 0.13.0 presentation-led cycle with a documented progressive-
  disclosure model grounded in native Qt 6, Kirigami, and system theming.
- Freeze backend, networking, service, integration, and Proton-overlay mechanics
  against the accepted 0.12.0 revision in CI. Admit only exact-reviewed,
  presentation-facing native-controller state, and seal the complete reviewed
  QML delta as well, with a negative fixture proving that changed connection
  arguments are rejected.
- Replace the in-app release-note walls of text with scannable grouped bullets
  and keep older release history collapsed until requested.
- Make Connection the graphical application home: its route links directly to
  protection settings and server browsing, identity opens Account, and an
  upper-right gear groups diagnostics and project information. Replace the
  application sidebar with native back navigation from every destination.
- Replace Overview's conventional status card with a graphical, system-themed
  route from this device through the encrypted tunnel to the VPN destination.
  Present the exact server, protocol, Secure Core entry, and forwarded port as
  compact icon-led facts on that surface; facts and capability badges open the
  relevant settings or Inspector depth without a redundant details modal. This
  does not change connection behavior.
- Lead server discovery with one graphical fastest-suitable action, keep its
  active capability requirements visible, and present the existing P2P,
  Streaming, Tor, and Secure Core requirements as native icon-led checkboxes
  before country, location, and exact-server browsing.
- Group Settings into native icon-led Connection, Protection, Plasma, and
  Diagnostics intents instead of presenting every control in one long scroll.
  Preserve the selected intent across asynchronous setting saves.
- Present authentication as one graphical active step at a time: service
  preparation, credentials, Secret Service approval, two-factor, security key,
  PIN, or safe recovery. Give the signed-in Account surface the same native
  identity hierarchy without changing authentication behavior.
- Keep the specific backend diagnostic visible during failed startup, expose
  restart recovery for unavailable or unresponsive services, and suppress a
  futile restart after terminal client-identity rejection.
- Preserve the backend's exact safety guidance when authentication, settings,
  or protection state cannot be confirmed instead of replacing it with a
  generic recovery message.
- Describe the complete authentication operation as sign-in progress rather
  than assuming every wait belongs to Secret Service, stop its progress
  indicator when completion becomes unknown, and keep any authoritative
  backend guidance visible. Present rejected client identity as a terminal
  failure instead of continued startup.
- Keep backend-unresponsive recovery visible above every signed-in page and
  disable cached Proton-dependent settings until the service is ready again;
  local Plasma preferences and navigation remain available.
- Keep ordinary connection failures visible at every request origin, including
  server search, KRunner, tray, and global shortcuts, while retaining focused
  dialogs for failures that require a specific response. Keep completed
  operation guidance visible when Core correctly leaves the connection
  disconnected, prevent server-browser actions from re-entering while another
  connection operation is active, and avoid duplicate status surfaces on the
  Connection page.
- Give connection and foreground authentication requests explicit operation
  identities. A delayed reply from an older same-backend attempt can no longer
  clear busy state, replace guidance, or complete the feedback owned by a
  newer retry; one controller signal now establishes that ownership for every
  request origin.
- Distinguish failed country, search, location, server, and load reads from a
  valid empty server-browser result, with errors scoped to their owning view
  and cleared when that read is retried. Explain whether an empty exact-server
  list comes from the available topology, capability requirements, text search,
  or both active filters.
- Keep the last verified connection snapshot visible while presenting snapshot
  validation or read failures globally. Pause Proton-dependent changes until a
  valid state is confirmed and offer an explicit state refresh, so stale data
  cannot be mistaken for newly confirmed state.
- Give packet-capture validation, start, and stop failures a dedicated result
  channel. Keep failures visible in Diagnostics and globally after navigation,
  finish a deferred stop when Diagnostics closes during a pending start, and
  defer application exit until an accepted capture start has been stopped.
- Preserve operation ownership when packet-capture signals arrive before method
  replies, keep risk-reducing Stop available after a malformed snapshot, and
  offer service restart for recoverable snapshot failures while treating an
  unsupported interface version as an update or reinstall condition.
- Let packet-capture Stop preempt an accepted but unfinished Start, wait for
  Core's existing cancellation compensation, and require affirmative inactive
  confirmation before application shutdown. A temporary busy/inactive snapshot
  can no longer allow an unconfirmed capture to outlive the Control Center.
- Fence browser replies and protected NPS submissions to the account session
  that created them. Report survey success only after the backend accepts it,
  and retire old page cleanup synchronously before a replacement Settings page
  can start a new capture.
- Serialize destructive NPS retrieval and submission with account transitions,
  generation-fence both protected submission stages, and permit retry only
  after a definitive same-session rejection. Completion-unknown submissions
  are reported explicitly and are never retried automatically.
- Consolidate release history, reporting availability, project status,
  attribution, and licensing behind one graphical Help & information
  destination. Keep the connection Inspector contextual and remove redundant
  project routes from the home gear menu.
- Add an on-demand Connection Inspector for live server capabilities,
  protection configuration, and local runtime state using only existing
  non-sensitive Core snapshots.
- Replace the backend's repeating client-ownership poll with authoritative
  D-Bus owner-loss events and a one-shot idle deadline, eliminating periodic
  wakeups while preserving active tunnel and packet-capture supervision.
- Scope asynchronous settings and protection snapshots to the active account
  session so replies completed after sign-out cannot repopulate cleared state.
- Keep reconnect work cancellable through network and session readiness
  checks, and require the resident agent to apply the current recovery policy
  successfully before it dispatches a connection request.
- Coalesce repeated Inspector refreshes, reload its lazily owned settings on an
  explicit refresh, and reuse the backend authorization owner check when
  acquiring a frontend lifetime lease.
- Bind every asynchronous Control Center and resident-agent reply to the exact
  authenticated backend generation, preventing delayed replies from a replaced
  service from corrupting its healthy successor.
- Keep transient network and session readiness-probe failures retryable instead
  of leaving drop recovery enabled but inert.
- Cap pathological reconnect backoff without evaluating an overflowing
  exponential, and close a partially initialized logind bus when cancellation
  interrupts setup.
- Fence countries, groups, servers, load, search, and NPS reads to the account
  session that requested them; make post-login refresher and reconnector startup
  transactional so a partial failure cannot publish a signed-in state.
- Retry a transient same-owner snapshot timeout without falsely marking the
  authenticated backend offline.
- Route tray and global-shortcut connection changes through the same validated,
  explicit Control Center confirmation used by KRunner; confirm the combined
  disconnect-and-quit action locally before it can reach the VPN controller.
- Select the desktop's same-user Secret Service provider before sending session
  material, pin calls and prompt signals to its unique D-Bus owner, reject
  owner replacement, and require that explicit overlay capability from the
  Fedora package.
- Accept a provider that already owns the Secret Service name after desktop
  autostart even when it has no D-Bus activation service, while still requiring
  same-user ownership and current-owner continuity before every operation.
- Add a repeatable same-process Inspector retention measurement; three
  two-open samples show one bounded warm-up allocation and no repeated retained
  growth.
- Roll back Proton Core authentication when post-login session services cannot
  start, and reconcile the visible account state with Core when a late logout
  failure occurs instead of presenting a false signed-out or signed-in state.
- Reload the open Connection Inspector after a backend generation changes so
  its lazily owned protection models recover with the rest of the interface.
- Generate strict Python and C++ snapshot validators from one versioned schema,
  and reject missing, extra, or incorrectly typed snapshot fields.
- Bind translation imports and all three Fedora package identities,
  capabilities, source packages, and dependency resolution to machine-checked
  manifests and exact artifact metadata.
- Reconcile late login, two-factor, security-key, and cancellation failures
  with Proton Core before publishing account state, and serialize reconnect
  preference changes with sign-out.
- Treat a long-running same-owner operation as completion-unknown instead of
  declaring the backend dead; refresh the authoritative snapshot and preserve
  bounded recovery guidance across the D-Bus boundary.
- Bind the complete Fedora binary/source artifact set and generated translation
  catalogs to the exact reviewed commit, and identify the modified API-Core RPM
  with its community downstream vendor.
- Make logout and backend shutdown cancellation-safe so a partially completed
  sign-out cannot silently persist a disabled kill switch or tear down session
  services around a still-authenticated Core session. Serialize Core's
  executor-backed protection write before compensation, and enforce any
  unconfirmed protection or authentication state at both the D-Bus authority
  boundary and the interface until the backend is restarted.
- Reconcile a cancelled security-key submission after Core may have persisted
  authentication, and guarantee that an expired Core session reaches the
  signed-out interface even when observer cleanup fails.
- Pause sign-in and offer an explicit backend restart whenever account or kill
  switch state cannot be confirmed; bound same-owner snapshot recovery before
  declaring the local backend unresponsive.
- Generate source archives through one commit-stamping release path with
  normalized metadata and a two-build reproducibility gate.
- Keep local build-tree translation paths out of installed native artifacts,
  and compare every RPM from two clean builds under a normalized build path.
- Remove native-loader, OpenSSL-provider, GIO/GI, Python, Qt-plugin, and QML
  search overrides before backend and Core imports, with one generated contract
  shared by systemd, the launcher, both authorization directions, and package
  checks. Document these checks as defense-in-depth rather than same-UID process
  attestation.
- Invoke the packaged `ip` and `journalctl` tools by absolute path instead of
  inheriting executable selection from the desktop environment, and reserve the
  adjustable backend idle deadline for explicit demo/test mode.
- Route Control Center D-Bus activation through its own environment-sanitized
  systemd user service, and pin desktop, System Settings, resident-agent, and
  Control Center fallback launches to configured absolute executable paths.
- Reserve packet-capture state before asking Core to start, compensate a
  cancelled or completion-unknown start, and keep its watchdog bounded from
  the original request deadline.
- Commit automatic reconnection only after observer registration succeeds,
  keep failed registration retryable, and always close its session probe when
  observer removal fails.
- Bound every Core packet-capture stop attempt so a non-returning Core reply
  cannot retain startup or block backend shutdown indefinitely.
- Preserve packet-capture recovery ownership and its original safety deadline
  across backend replacement, retry an unconfirmed stop before the replacement
  reports ready, and continue bounded stop attempts after the deadline until
  Core confirms completion.
- Retain backend initialization while a durable packet-capture recovery entry
  exists so the ordinary no-client idle deadline cannot orphan recovery.
- Prewarm Core's Secret Service session before connector construction and,
  while durable packet-capture recovery is pending, bound that provider wait
  so an unanswered prompt exits nonzero with the recovery record retained for
  systemd retry. Also retain the record when no session is restored rather
  than trusting Core's intentionally synthetic logged-out disconnected state,
  and bound connector construction so a stalled system D-Bus dependency also
  returns recovery ownership to systemd.
- Suppress connector, recovery, and reconnector snapshot callbacks until Core
  initialization has completed, so clients receive one authoritative ready
  state instead of a transient partially initialized session.
- Keep capture setup inactive and retryable when Core rejects the selected
  destination before it receives a start request.
- Teach Git that unified-diff context markers are patch syntax while retaining
  a dedicated check against trailing whitespace in added target lines.
- Parse declared hunk sizes so the patch checker distinguishes file headers
  from added target content beginning with `++`.
- Parse patch bytes on LF boundaries so embedded carriage returns cannot hide
  trailing whitespace while ordinary CRLF patches remain valid.
- Reject mixed patch line endings and terminal-delimiter pseudo-content.
- Reapply kill-switch state after a partially persisted Core settings failure.
- Remove the Control Center's public D-Bus shutdown method, authorize the
  agent's retained shutdown path, and explicitly allowlist exported slots.
- Publish the backend's D-Bus name only after authorization and object export
  are ready, preventing startup races from stranding automatic connection.
- Derive failed sign-in cleanup state from Core's authoritative session probe,
  never from whether the cleanup call itself returned successfully.
- Make user-initiated settings writes transactional: compensate a possibly
  committed failure, and block further VPN operations when the persisted or
  live protection state cannot be confirmed.
- Reconcile completion-unknown connection and settings mutations from a fresh
  backend snapshot before releasing the agent's transient lifetime lease or
  presenting settings as final.
- Normalize RPM header time and host metadata, then require complete binary and
  source package sets from two independent builds to match byte for byte.
- Reject authorization if a D-Bus client loses its unique name while identity
  checks are still in flight, preventing a dead frontend lease from retaining
  an otherwise idle backend.
- Preserve the ordinary signed-out recovery path when a Proton session expires
  during a settings write or its compensation instead of replacing it with a
  restart-only settings error.

## [0.11.3] - 2026-08-31

- Keep Protun's transient WireGuard key in its existing unsaved NetworkManager
  profile so Plasma reconnects do not depend on a missing Protun secret-agent
  plugin.
- Clear cached account and tunnel metadata when the backend stops instead of
  continuing to present a stale signed-in state.
- Offer an explicit service retry after Secret Service session restoration
  remains incomplete, without imposing an automatic prompt timeout.
- Build, verify, transaction-test, and retain the API-Core overlay's binary and
  source RPMs with the client and provider-neutral keyring artifacts.

## [0.11.2] - 2026-08-30

- Run Fedora CI and RPM builds as an unprivileged builder and retain the exact
  client and provider-neutral keyring binary/source package set from one
  verified release-artifact directory.
- Run GUI smoke tests through the offscreen software backend with an explicit
  UTF-8 locale and pin GitHub Actions to their Node 24-based releases.
- Decompose the official-Core adapter into focused compatibility, protocol,
  server, settings, snapshot, support, and packet-capture modules while
  preserving the established `ProtonCoreAdapter` API.
- Keep the QML application window and Settings page focused on orchestration by
  extracting dialogs and independent settings sections with explicit inputs.
- Split native location models and controller lifecycle/snapshot handling into
  cohesive implementation units without changing their QML-facing types.
- Add a reproducible, isolated demo-stack PSS measurement and refresh the
  search benchmark after the maintainability decomposition.
- Reactivate the backend after an unexpected service exit and explain when a
  Control Center left open across an RPM upgrade must be restarted.
- Make tray shutdown explicit and wait for Proton Core to confirm a disconnect
  before quitting background controls.
- Keep server-browser cleanup scoped to the page that owns the active context
  and retry transiently empty country-group snapshots without manual refresh.
- Respect `TMPDIR` in the Python analysis gate so constrained or isolated RPM
  builders do not silently fall back to the host temporary filesystem.
- Test the full backend on Python 3.11 with hash-pinned minimum dependencies
  and validate its consumed public API against Proton's pinned Core 5.5.6 RPM.
- Split the native controller implementation into lifecycle, action, location,
  and settings units without changing its QML or D-Bus behavior.
- Separate immutable backend state and payload validation from asynchronous
  orchestration while retaining the existing Python import surface.
- Isolate the deterministic demo adapter from the official Core adapter while
  preserving the established adapter import facade.
- Reconcile the public documentation with the installed `0.11.2-26`
  acceptance evidence and repository-built provider-neutral keyring package.
- Keep Clang-Tidy focused on project source regardless of build-directory name
  by excluding Qt-generated `_autogen` headers explicitly.
- Add a reproducible Fedora rebuild of Proton's keyring adapter with the
  provider-neutral Secret Service alias and stable-client fixes used for
  KeePassXC acceptance.
- Require the adapter's explicit virtual capability from the client RPM and
  build both source and binary packages in release CI.
- Clarify that the Plasma frontend has no direct GTK dependency while Proton's
  Fedora API Core package retains its upstream `NetworkManager-openvpn-gnome`
  dependency.
- Remove the prescriptive upstream-engagement guide and let GitHub flow README
  prose without a fixed source-column width.
- Build, inspect, transaction-test, and retain Fedora source and binary RPMs in
  a dedicated CI workflow with an independently visible README status badge.
- Enforce static Python type analysis and a measured 75% backend branch-
  coverage floor in source CI and RPM `%check`.
- Add blocking Clang-Tidy and address/leak/undefined-behavior sanitizer CI,
  removing the avoidable Qt container conversions and implicit size narrowing
  it found.
- Add enforced SPDX copyright and license identifiers to every project-authored
  source and build file without relabeling Proton-derived materials.
- Make installed D-Bus introspection XML the checked-in source of truth for
  endpoint, method, signal, error, and authorization policy constants, with
  generated native/Python definitions and runtime-signature drift tests.
- Consolidate the public documentation, make the security assessment
  unambiguous about current versus historical findings, and record the exact
  downstream keyring dependency used for KeePassXC acceptance.
- Recast the README as a concise public introduction with project-status badges,
  engineering evidence, and a linked gallery of reproducible demo screenshots.
- Remove the shared KRunner plug-in host from backend trust and require an
  explicit Control Center confirmation for its validated connection requests.
- Disable Proton crash-report submission in unofficial builds, normalize the
  stored Core preference off, and explain the community reporting policy in
  Settings.
- Prioritize the deepest pending server-browser request, reject obsolete
  same-target replies, and automatically retry short-lived empty Core snapshots.
- Keep native pin actions visible in global search and use Plasma pin artwork
  consistently instead of favorite stars.
- Add persistent state, city, and Secure Core group pins with direct fastest-in-
  group actions in the Plasma tray.
- Retain country, location-group, and exact-server requests made while the
  backend is still initializing, removing the need for a manual refresh.
- Add combinable P2P, Streaming, Tor, and Secure Core browser checkboxes; every
  selected feature must be present on the same official Core server.
- Persist optional default fastest filters for the overview, tray, global
  shortcut, KRunner, and auto-connect while retaining Proton's scoring.
- Accept immutable root-owned systemd user-service drop-ins, including
  Fedora's global shutdown-timeout policy, without accepting per-user or
  writable overrides during backend identity verification.
- Preserve production D-Bus executable authorization on Fedora/SELinux by
  removing mount-namespace directives that deny the required procfs peer
  identity reads from the otherwise unprivileged user services.
- Keep the sidebar collapse control recoverable across compact-window
  transitions and preserve the user's wide-layout collapsed state.

- Authenticate and pin the packaged backend's unique D-Bus owner before native
  clients send commands, subscribe to signals, or retrieve encryption keys.
- Authorize every state-changing backend call from its actual sender and bind
  one-use secret keys to that sender and intended operation.
- Restore the prior official-Core kill-switch setting whenever sign-out fails
  after the temporary logout transition.
- Close all rejected or unexpected Unix descriptors and verify descriptor
  stability on an isolated session bus.
- Bound optional support logs by bytes and time while keeping direct Proton
  submission disabled in unofficial builds.
- Require Core's reviewed packet-capture byte limit, enforce a 15-minute
  community watchdog, and serialize every stop path.
- Publish the complete third-party-style security and engineering audit with
  post-remediation evidence.
- Add selectable color, light-symbol, and dark-symbol interface icons.
- Apply icon changes immediately to the Control Center and resident tray agent.
- Expose the shared icon preference in both application Settings and Plasma
  System Settings while retaining the color application-menu mark.
- Disable direct Proton support-report submission in unofficial builds at the
  page, native-controller, and backend D-Bus boundaries while preserving the
  reviewed workflow as an inactive proof of concept.
- Give Release Notes a distinct bound-notebook icon that remains recognizable
  when the navigation sidebar is collapsed.

## [0.11.1] - 2026-08-29

- Embed the application mark in the Control Center and resident agent so a
  missing or stale desktop icon cache cannot produce a generic icon.
- Let Kirigami own dynamically created pages and destroy them on removal.
- Prevent inactive sign-in pages from reacting to later settings snapshots.
- Adopt an original Plasma VPN identity and explicit community-client status.
- Move private session services into the maintainer-owned
  `quest.entropy.PlasmaVPN` namespace.
- Add public-release CI, provenance, contribution, support, and release
  guidance.
- Preserve the Settings route after successful Core configuration changes.

## [0.10.2] - 2026-08-29

- Keep Settings active after successful VPN configuration changes.
- Limit automatic Overview navigation to completion of the sign-in flow.
- Add end-to-end settings-navigation regression coverage.

## [0.10.1] - 2026-08-29

- Route signed-out startup directly to Sign in.
- Prevent authentication from racing Proton connector initialization.
- Explain delayed desktop Secret Service approval during sign-in.

## [0.10.0] - 2026-08-29

- Introduce responsive desktop and compact Kirigami navigation.
- Standardize page headers, cards, rows, semantic colors, typography, and RTL
  behavior across the Control Center.
- Add compact, scaled-text, RTL, UI-hygiene, and screenshot checks.

## [0.9.0] - 2026-08-29

- Split resident tray, shortcut, and notification behavior into a lean native
  Plasma agent.
- Make the full Kirigami Control Center on-demand.
- Release disconnected idle Python backends without losing active-tunnel
  supervision.

Earlier development milestones remain recorded in the Fedora package
changelog and Git history. The [roadmap](docs/ROADMAP.md) is intentionally
forward-looking.
