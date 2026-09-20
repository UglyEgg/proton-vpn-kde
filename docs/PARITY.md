# Official client parity

This matrix tracks user-visible parity with Proton VPN GTK app v4.18.0 at
commit `8e3897b6fe81840eef4762f2377c5a985754edea`. Parity means that a user can
complete the same VPN, account, settings, recovery, and support workflows. It
does not mean reproducing GTK widgets or moving networking behavior out of
Proton's official core.

## Capability matrix

| Area | Official behavior | Plasma implementation | Status |
| --- | --- | --- | --- |
| Password sign-in | Proton username and password login | Native Kirigami form with sealed one-use credential transport | Complete |
| Two-factor sign-in | Authenticator/recovery codes and FIDO2 security keys | TOTP and recovery codes are complete. FIDO2 touch, selection, and PIN are exposed only when Core guarantees cancellable multi-key selection; current Fedora Core 5.7.0 does not | Conditional on Core safety contract |
| Session storage | Proton SSO through Secret Service | Same Core session through a separately packaged provider-neutral keyring rebuild that requires the selected provider to run as the session user and pins traffic to its unique owner; KeePassXC is verified with the downstream build in the compatibility matrix | Complete on supported stack |
| Permanent kill switch before login | Requires disabling permanent mode before sign-in | Signed-out recovery action changes only the kill-switch setting | Complete |
| Account/session | Plan, connection limit, account link, and sign-out | Native account page and kill-switch-safe disconnect/sign-out lifecycle | Complete |
| Fastest connection | Connect to fastest available server | Official Core selection in the window and auto-connect, plus confirmation-gated tray, shortcut, and KRunner requests; optional saved P2P, Streaming, Tor, and Secure Core filters use AND semantics before Core scoring | Superset |
| Country/location/server selection | Browse and connect at each topology level | Native localized country, location, Secure Core, and exact-server models with combinable capability checkboxes and filtered scoped-fastest actions | Superset |
| Free-plan discovery | Free servers connect; paid rows remain upgrade-visible | Same accessibility model and ordering with native upgrade actions | Complete |
| Search | Search countries, cities, and exact servers | Bounded global search through a compact scalar projection; live state stays in official Core objects | Complete |
| Server metadata | Load, maintenance, P2P, streaming, Tor, Smart Routing, Secure Core | Native model roles and connection-detail presentation | Complete |
| Connection inspection | Connection status and selected-server details in the main view | On-demand read-only page combining active server capabilities, effective protection settings, and local integration status without traffic collection or history | Superset |
| Live refresh | Full topology and load-only updates | Separate Core callbacks; load changes update rows in place, and page requests made during backend startup are retained until readiness | Complete |
| Connect cancellation | Connecting and failed states can be cancelled | Connecting cancellation bypasses the normal operation lock; failed state never reconnects accidentally | Complete |
| Connection recovery | Retry nonfatal drops and react to network/session changes | Asyncio reconnector preserves server, protocol, and backend and observes network route and logind unlock | Complete |
| Connection errors | Specific summaries plus recovery dialogs for important fatal states | Stable non-sensitive error codes, official recovery text, and error-state cancellation | Complete |
| Startup compatibility | Warn when no compatible VPN backend is registered | Official validator when available; public protocol-registry fallback for Fedora's initial core 5.5.6 | Complete |
| Protun connection secret | Agent-owned transient key returned through a desktop NetworkManager secret agent | System-owned transient key remains in Core's unsaved NetworkManager profile, avoiding Plasma's missing Protun secret plugin | Native equivalent on packaged distributions |
| Memory-overlay awareness | No equivalent warning | Behavior-check both server-string sharing paths and identify an unoptimized installed Core without blocking VPN use | Superset |
| Quit/logout safety | Confirm active disconnect, preserve permanent kill switch on quit, disable it on logout | Closing the Control Center preserves the tunnel; tray shutdown offers explicit keep-connected and confirmed disconnect-and-quit paths; logout remains kill-switch safe | Native equivalent |
| Protocols | Generic protocols and feature-flagged Proton protocols | Lists core-provided protocols and honors the ProTun feature flag | Complete |
| Connection settings | Protocol, VPN Accelerator, moderate NAT, and IPv6 | Native conflict-aware controls saved through official Core. Disabling tunneled IPv6 does not disable Core's separate connection-scoped IPv6 leak protection | Complete |
| Protection settings | Kill switch, NetShield, and port forwarding | Native controls with plan and connected-state constraints | Complete |
| Port forwarding | Show/copy active port and notify when it changes in the background | Native clipboard action and Plasma notification | Complete |
| Custom DNS | Enable and edit IPv4/IPv6 servers with NetShield conflict handling | Native validated editor; both settings remain unchanged until the user explicitly resolves the conflict | Complete |
| Split tunneling | Include/exclude modes, applications, and IP ranges | Native KService application chooser plus validated IPv4/IPv6 CIDR rules | Complete |
| Auto-connect | Off, fastest, country, or exact server at application start | Same target syntax persisted through KConfig; shared Startup controls apply saved fastest-server capabilities independently of window/tray presentation, without bypassing authentication | Complete |
| Tray preferences | Start minimized and pinned targets | Lean native status-notifier agent, tray-only startup, pinned countries, state/city groups, and exact servers, plus an on-demand Control Center | Superset |
| Troubleshooting capture | Choose folder and start/stop capture for supported protocols | Native folder chooser, consent warning, and official protocol capture implementation | Complete |
| Issue reporting | Submit support form with optional logs | Reviewed Proton submission proof of concept retained behind a default-off build capability; a separate community flow previews and copies only allowlisted local diagnostics before opening the project tracker | Deliberately disabled for Proton; community flow available |
| Anonymous crash reporting | Optional automatic reports to Proton's Sentry endpoint | Default-off build capability; community builds disable the runtime sender, always present the preference as off, persist it during explicit settings writes, and direct client crashes to the project tracker | Deliberately disabled |
| Connection telemetry | Optional Core 5.7 connection-outcome events to Proton's stats endpoint | Visible default-off build capability and state; community builds lock the switch off, disable Core's live event queue after each settings load, and persist the preference as off during explicit settings writes. Telemetry-capable builds expose the user preference | Deliberately disabled in community packages |
| Release information | About and release-notes views | Native Help & information hub with on-demand Release Notes | Complete |
| Update channel | Stable/Beta repository choice | Exact-package Polkit action; Discover remains responsible for updates | Native equivalent |
| Account/help links | Create, manage, support, upgrade, and setup guidance | Official URLs opened through the desktop URL handler | Complete |
| NPS survey | Cached Proton survey, seen state, submit, and dismiss | Same official notification and response APIs with sealed optional comments | Complete |
| Localization | Ships Proton's supported locale catalogs | Native Qt loader in the app, KRunner, and System Settings; 24 Proton locale catalogs seed exact shared strings | Infrastructure complete |

## Deliberate differences

- The client and System Settings share a Startup section for opt-in KDE login
  launch, window/tray startup, and auto-connect. Installation never enables
  login launch. Existing custom autostart entries are preserved, and explicit
  launcher requests still open the window. This native integration is covered
  by isolated tests; installed results are recorded in the
  [compatibility evidence](COMPATIBILITY.md#acceptance-evidence).
- The Plasma client has no direct GTK, PyGObject, Gio, GNOME Keyring, or GLib
  main-loop dependency. Qt/Kirigami, KConfig, KNotification, KService, KRunner,
  and Plasma's status-notifier APIs own desktop integration. Proton's current
  Fedora and Ubuntu API Core packages still require
  `NetworkManager-openvpn-gnome`; this project preserves that upstream package
  contract even though the Plasma frontend does not use the editor component.
- Settings conflicts are never resolved by silently changing another setting.
  The user sees the conflict and chooses the required change; the resulting
  core configuration is the same as the official client's accepted path.
- Repository-channel changes use an exact-package, no-shell privileged action.
  The application never performs a general system upgrade.
- Direct submission to Proton's support endpoint is compile-time disabled in
  unofficial builds. The QML page, native controller, and backend D-Bus method
  independently enforce the same default-off capability before report fields
  or diagnostic logs are collected. An approved distribution can deliberately
  enable it with `PROTON_VPN_KDE_ENABLE_SUPPORT_REPORT_SUBMISSION`.
- Anonymous crash-report submission to Proton is independently compile-time
  disabled in unofficial builds. The Settings switch, native controller, and
  backend reject re-enabling it. Pure settings reads never rewrite Core's
  settings object; the backend keeps the runtime sender disabled and persists
  the official Core preference as off during any explicit settings write. An approved
  distribution may enable it with
  `PROTON_VPN_KDE_ENABLE_CRASH_REPORT_SUBMISSION`.
- Optional Core connection telemetry is independently compile-time disabled.
  Core 5.7 enables its queue while loading a stored preference, so the adapter
  immediately disables that queue without writing during a read and persists
  the preference as off on the next explicit settings write. Settings and the
  copied community report disclose the effective policy. An approved
  distribution may enable the user-controlled switch with
  `PROTON_VPN_KDE_ENABLE_TELEMETRY`; fresh Core profiles still start off.
- A resident Plasma agent, global shortcuts, KRunner actions, a System Settings
  module, and native notifications extend rather than replace official behavior.

## Known content and upstream constraints

- Exact shared strings reuse Proton's GPLv3 translations. Plasma-specific text
  remains English until translators add it; no automatic or guessed
  translations are shipped.
- Proton's current Linux core reports human-verification challenges but does
  not expose a native completion callback. The client opens the Proton account
  flow instead of exporting or handling the verification token itself.
- Some API failures contain provider-supplied account-specific wording. The
  D-Bus boundary intentionally publishes fixed messages instead of raw
  exception text; this preserves the recovery capability without risking
  credential or account-detail disclosure.

## Release gate

Before claiming parity with a newer official release:

1. Compare its account, main-window, settings, notification, and reconnection
   sources with this matrix.
2. Add a regression test for every new or changed behavior before marking it
   complete.
3. Run the backend suite, native CTest suite, isolated authentication smoke,
   isolated full demo smoke, and a staged install on every supported package
   target.
4. Re-import exact shared translations from the audited official tag and
   record that tag and commit in `translations/README.md`.
