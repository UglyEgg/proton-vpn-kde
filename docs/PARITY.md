# Feature coverage

User-workflow comparison baseline: Proton VPN GTK app v4.18.0,
commit `8e3897b6fe81840eef4762f2377c5a985754edea`. This is not a claim about
every later official release. Supported platform/Core versions are owned by
[Compatibility](COMPATIBILITY.md).

## Capability matrix

| Capability | Plasma implementation or limit |
| --- | --- |
| Sign-in | Native password, TOTP, and recovery codes; FIDO2 only with Core's complete cancellable-selection capability |
| Saved session | Proton SSO through the required provider-neutral Secret Service overlay |
| Account | Plan/connection-limit display, account links, sign-out, and permanent-kill-switch login recovery |
| Server browser | Country, state/city, Secure Core group, and exact server; free/paid availability; pinned tray targets |
| Fastest | Core-ranked global/country/group selection with saved P2P, Streaming, Tor, and Secure Core AND filters |
| Search / refresh | Global country/location/server search; separate topology/load updates; requests retained through backend readiness |
| Server facts | Load, maintenance, Smart Routing, capabilities, and Secure Core entry |
| Inspector | On-demand active-connection facts, effective settings, and local integration state; no traffic history |
| Address display | Core-reported connection-time exit/device addresses; not independent live IP probes |
| Connect / Cancel / Disconnect | Core public operations with owned cancellation and completion-unknown guidance |
| Recovery | Protected handoff and exponential retry; bounded selection-aware Fastest failover is unreleased |
| Protocols | Core-provided registry and feature flags |
| Connection settings | VPN Accelerator, moderate NAT, tunneled IPv6, and protocol |
| Protection | Kill switch, NetShield, and port forwarding, subject to Core plan/state constraints |
| Port forwarding | Active-port display/copy and background notification |
| Custom DNS | Validated IPv4/IPv6 entries; explicit NetShield conflict resolution |
| Split tunneling | Include/exclude modes, KService application discovery, and CIDR rules |
| Startup | Opt-in login launch, window/tray-only startup, and saved auto-connect target |
| Desktop | Native status notifier, shortcuts, KCM, notifications, and confirmation-gated KRunner actions |
| Quit | Window close preserves tunnel; background controls offer keep-connected or confirmed disconnect-and-quit |
| Capture | Core protocol capture with explicit consent and bounded stop/recovery |
| Diagnostics | Read-only local setup and allowlisted preview/copy report |
| Proton reporting | Support submission, automatic crash reports, and optional telemetry disabled in community packages |
| Repository channel | Exact-package Polkit action; no general system upgrade |
| Help / release notes | On-demand native pages and official account/support links |
| NPS | Explicit Core survey workflow with sealed optional comments |
| Localization | Pinned exact shared translations; untranslated Plasma-specific text falls back to English |

## Deliberate constraints

- The UI is native Qt/Kirigami. Upstream Core packaging can still install GTK
  libraries; dependency ownership is documented in Compatibility.
- Settings conflicts require explicit choice, never a silent second-setting
  change.
- Core's human-verification token is not exposed to the frontend; completion
  uses Proton's account flow.
- Public errors use fixed messages rather than account-specific provider text.
- Reporting capabilities are independent build gates; their runtime/privacy
  enforcement belongs in [Hardening](HARDENING.md#data-and-reporting).
- Startup never enables itself during installation or while viewing Settings.

## Updating coverage

Before claiming parity against a newer official tag:

1. Compare account, settings, main-window, notification, and reconnection flows.
2. Add regressions for changed behavior and update this matrix.
3. Run source, package, and installed gates from [Releasing](RELEASING.md).
4. Re-import exact shared translations only through the pinned
   [translation workflow](../translations/README.md).
