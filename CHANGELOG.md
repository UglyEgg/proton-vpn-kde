# Changelog

All notable user-visible changes are recorded here. The project follows
[Semantic Versioning](https://semver.org/) while it remains pre-1.0.

## [Unreleased]

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
