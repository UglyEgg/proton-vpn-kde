# Changelog

All notable user-visible changes are recorded here. The project follows
[Semantic Versioning](https://semver.org/) while it remains pre-1.0.

## [Unreleased]

- Respect `TMPDIR` in the Python analysis gate so constrained or isolated RPM
  builders do not silently fall back to the host temporary filesystem.

## [0.11.2] - 2026-08-30

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
