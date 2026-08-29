# Roadmap

This roadmap records the prioritized follow-up from the holistic hostile,
subtractive, entropy, error-class, performance, and hardening review. Each
phase should remain independently reviewable and preserve Proton Core as the
owner of networking, authentication policy, protocol behavior, kill switch,
DNS, and split tunneling.

## Phase 1 — Sanitize observable error boundaries (complete)

- Route every exported D-Bus method through one typed sanitizer.
- Preserve only explicitly backend-authored validation guidance.
- Collapse unexpected Proton and third-party exceptions to fixed messages.
- Prevent raw reconnection exception text from entering observable state.
- Cover hostile inputs with real session-bus regression tests.

Deployed in the local Fedora `proton-vpn-kde-0.8.3-1.fc44` package.

## Phase 2 — Recover cleanly from transient lifecycle failures (complete)

- Let a failed backend initialization terminate or retry instead of remaining
  permanently alive with `ready=false`.
- Complete client registration asynchronously and retry transient D-Bus
  registration failures.
- Observe and classify replies from control operations that currently discard
  them.
- Restore reconnection behavior when the previous connection disappears.

Implemented and verified by the complete backend, native, staged-install, and
isolated D-Bus test matrix. Deployed in the local Fedora
`proton-vpn-kde-0.8.4-1.fc44` package. Live testing confirmed recovery after
both an orderly backend restart and a forced backend failure while the GUI was
open; the replacement backend remained registered past the idle timeout.

## Phase 3 — Remove the obsolete flat server endpoint (complete)

- Add an end-to-end navigation test proving grouped country/location loading
  does not require the legacy flat-country fallback.
- Remove `GetServers(countryCode)`, its frontend fallback, associated state,
  tests, and documentation without changing visible server browsing.

The frontend, D-Bus service, backend controller, and Proton Core adapter now
use only the grouped country/location path. An isolated session-bus regression
test proves country-to-group-to-server navigation against a backend that does
not expose the removed endpoint. The complete native, backend, staged-install,
and D-Bus test matrix passes. Deployed in the local Fedora
`proton-vpn-kde-0.8.5-1.fc44` package. Installed-package validation covered the
signed-out authentication path, a real signed-in Proton session, grouped Swiss
location/server navigation, and clean disconnected shutdown without the legacy
endpoint. The Fedora package check also now validates the staged backend when
`CMAKE_INSTALL_LIBEXECDIR` is absolute instead of accidentally importing an
older installed backend.

## Phase 4 — Make the API Core overlay reproducible (complete)

- Record the vendor package NEVRA and payload hash.
- Record every patch hash and resulting installed-file hash.
- Rebuild from one canonical source payload.
- Fail packaging when any file outside the intended representation-only patch
  set changes.

The overlay now reconstructs `python3-proton-vpn-api-core-5.6.10-5.codex1.fc44`
from Proton's exact signed Fedora `5.6.10-1.fc44` RPM. The build pins the
complete vendor RPM, header, payload, and patch hashes; deterministically
regenerates only bytecode derived from the three patched sources; and fails on
any unexpected path, mode, hardlink, dependency, conflict, obsolete, scriptlet,
or installed-file change. The installed package passed the manifest verifier,
the representation-only behavior checks, and the complete 23-test project
matrix with Proton's GTK client absent and the VPN disconnected.

## Phase 5 — Measure and optimize interactive search

Completed in `0.8.6`:

- Profiled representative country, city, exact-server, broad, and no-match
  searches against an 18,138-server Proton cache.
- Added a compact generation-scoped scalar projection after measurements showed
  repeated searches taking roughly 0.4 to 1.0 seconds.
- Reduced measured medians to 0.2 to 5.2 milliseconds after the initial lazy
  build, with about 2.6 MB of steady traced allocations.
- Rebuild only after Proton reports a topology or localized-location-name
  change. Load-only refreshes continue to resolve live official state without a
  rebuild.
- Verified exact result parity, no retention or mutation of official server
  objects, compatibility with older Core callback surfaces, and bounded result
  counts. See [Search performance](PERFORMANCE.md).

## Phase 6 — Stage user-service hardening

Completed in `0.8.7`:

- Configured absolute backend paths in both systemd and D-Bus activation.
- Verified `NoNewPrivileges=true` and `PrivateTmp=true` independently and in a
  combined backend lifecycle.
- Retained `ProtectSystem=full` after checking official-Core startup, support
  logs, arbitrary capture-directory writes, Secret Service, NetworkManager, and
  split-tunneling D-Bus access.
- Rejected strict system/home allowlists and network/device isolation because
  they would remove supported account, cache, packet-capture, networking, or
  FIDO2 behavior. See [Backend service hardening](HARDENING.md).
- Passed the installed Plasma regression check with KeePassXC, server browsing,
  connect/disconnect, and the expected close-to-tray behavior.
- Verified a clean disconnected NetworkManager state, no backend restart or
  journal error, and automatic backend shutdown after the frontend exited.

## Phase 7 — Clean up upstream Core log and API hygiene

Completed locally as two small upstreamable patches in their owning Proton
packages; neither problem is hidden in the KDE frontend:

- `python-proton-keyring-linux` commit `4b2adc7` preserves `KeyError` for an
  absent credential without logging an exception traceback.
- `python-proton-vpn-api-core` commit `f39782e` reads the current session's
  FIDO2 capabilities directly without calling its deprecated public property.

### Idempotent missing-credential deletion

- Treat deletion of an already-absent keyring entry as the expected missing-key
  condition without logging a traceback.
- Keep genuine Secret Service activation, lock, transport, and provider errors
  observable and correctly classified.
- Keep the behavior provider-agnostic across KeePassXC, KWallet, GNOME Keyring,
  and other Freedesktop Secret Service implementations.
- Add focused `python-proton-keyring-linux` tests for an absent credential and
  for a real backend failure.

### Supported FIDO2 capability query

- Remove the internal call from `supports_fido2` to the deprecated
  `is_fido2_lib_available` API.
- Preserve security-key availability and registered-key semantics.
- Add API Core tests for available, unavailable, and registered-key states.

### Acceptance criteria

- Verified a collision-checked missing-entry deletion against KeePassXC's live
  Secret Service with no error log and no credential mutation.
- Verified all four platform-availability and registered-key FIDO2 outcomes,
  while a test guard rejects any internal use of the deprecated property.
- Preserved missing-entry `KeyError` behavior and exception reporting for
  genuine provider failures; authentication methods are otherwise untouched.
- Passed all 31 keyring tests and all 437 API Core tests, plus touched-file
  flake8 checks.
- Installed `0.2.3-4.codex1` and `5.6.10-6.codex1`, verified their RPM payloads,
  and completed a clean disconnected backend lifecycle with no new diagnostic
  signature, restart, residual process, or VPN connection.

## Phase 8 — Eliminate native UI runtime diagnostics (complete)

- Reproduce and remove the Kirigami action-button binding loops seen during
  normal page navigation.
- Ensure dynamically created pages are owned by the application window's page
  stack so QML does not report detached graphical objects.
- Make About and overlay-sheet teardown safe when the application closes.
- Add a navigation-and-close smoke test that fails on application-authored QML
  warnings, binding loops, or uncaught JavaScript errors while allowing known
  framework diagnostics only when they are documented and version-bounded.
- Verify the clean diagnostics path against the installed Fedora/Plasma build,
  including opening every primary page and quitting while disconnected.

Completed in `0.8.8`. Pages are explicitly created under the visible page
stack before insertion, the desktop navigation drawer no longer uses the
Kirigami action-menu path that produced a binding cycle, and About is a static
native page without a latent overlay sheet. A version-bounded, serial desktop
smoke test now opens every primary and nested page and rejects unexpected QML,
JavaScript, ownership, binding, or teardown diagnostics. See
[Native runtime diagnostics](RUNTIME-DIAGNOSTICS.md).

## Phase 9 — Make API Core memory-overlay drift visible (complete)

- Report the installed `python-proton-vpn-api-core` version in the bounded
  non-sensitive snapshot.
- Verify both server-string sharing paths by behavior without reading or
  mutating Proton's live server list.
- Display a non-blocking warning when either optimization is absent while
  making clear that VPN functionality remains available.
- Cover complete, missing, and no-op overlay implementations plus the native
  snapshot path.

Completed in `0.8.8`. This is deliberately stronger than a package-version
allowlist: an upstream release that incorporates equivalent behavior passes,
while an overlay replaced by an unoptimized package fails even if its release
label is unexpected. The installed Core version is included in the warning so
the user knows which overlay needs review.

## Phase 10 — Split resident Plasma integration from the Control Center (complete)

- Add a lean, windowless `proton-vpn-kde-agent` for the system tray, global
  shortcuts, notifications, favorites, auto-connect, and launching the Control
  Center.
- Observe the existing bounded backend snapshot without registering a native
  client lease, so a disconnected Python backend can still shut down while the
  Plasma agent remains available.
- Keep `proton-vpn-kde` as an on-demand Kirigami Control Center that exits when
  its window closes without disconnecting an active tunnel.
- Activate the agent through the user D-Bus and systemd session facilities and
  retain a development-tree fallback that does not depend on an installed
  service file.
- Prove single-instance behavior, command parity, backend idle shutdown, and a
  materially smaller resident memory footprint.
- Release an unanswered Secret Service startup after its activating frontend
  disappears, while protecting explicit tray actions with a transient lease.

Completed in `0.9.0`. The resident process is now a windowless native Plasma
agent while the Kirigami Control Center starts only on demand. The agent keeps
tray actions, shortcuts, notifications, favorites, and auto-connect available
without holding a native client lease or keeping the Python backend alive while
disconnected. A bounded transient lease protects explicit startup actions and
is released when an activating frontend disappears, including an abandoned
Secret Service prompt. Source, staged-package, isolated D-Bus, lifetime, and
installed-package checks passed. Live Plasma acceptance confirmed tray and
Control Center behavior, connection and disconnection, close behavior, and
clean shutdown.

## Phase 11 — Apply a KDE desktop-first visual system (in progress)

- Replace the remaining GTK-shaped page composition with native Kirigami
  navigation, spacing, typography, semantic colors, and inline status patterns.
- Prefer standard Plasma icons and controls, respecting system color schemes,
  font sizes, reduced motion, high contrast, and right-to-left layouts.
- Resolve the UI hygiene debt recorded during the review before adding visual
  novelty.

Implemented for `0.10.0` and awaiting installed Plasma acceptance. Version
`0.10.1` corrects the first acceptance regressions by routing signed-out
startup directly to Sign in, preventing credentials from racing Proton
connector initialization, and making delayed Secret Service approval visible.
Version `0.10.2` keeps Settings active across successful Core settings writes
and limits automatic Overview routing to completion of the sign-in flow.
Wide windows
now use a persistent, selected Kirigami navigation sidebar while compact
windows use its overlay form. Shared page-header, section-card, detail-row, and
navigation-row components give the connection, location, settings,
authentication, account, support, and informational pages one native visual
language. The implementation contains no literal colors, fixed font sizes, or
custom animations. Isolated tests render every page at desktop, compact,
scaled-text, and right-to-left layouts, and a screenshot harness captures
specific demo pages without contacting NetworkManager. See
[Plasma visual system](VISUAL-SYSTEM.md).

## Phase 12 — Add an on-demand Connection Inspector

- Move richer live connection details and bounded analytics into a Control
  Center page that consumes existing non-sensitive backend state.
- Keep collection off while the page is closed and avoid traffic inspection,
  history retention, or new networking ownership.
- Present useful tunnel, server, feature, and diagnostic information without
  keeping the full Control Center resident.

## Phase 13 — Add an optional Plasma widget

- Provide a pure-QML Plasma 6 widget for status and common connection actions.
- Reuse the resident agent and existing backend D-Bus contract instead of
  embedding Python or Proton Core in plasmashell.
- Treat the widget as optional; the agent and Control Center remain complete
  without it.
