# Plasma visual system

The Control Center is a responsive Kirigami desktop application. These rules
govern presentation only. Proton Core remains the owner of account policy,
networking, protocols, NetworkManager, DNS, kill switch, and split tunneling.

## Native Plasma contract

Qt 6, Kirigami, and KDE Frameworks are the interface toolkit, not a themed
compatibility layer. Use standard controls and semantic Plasma assets so the
desktop remains responsible for color scheme, typography, spacing, icon theme,
font scaling, contrast, right-to-left layout, accessibility, and reduced-motion
preferences. A custom visual treatment must still behave like a good Plasma
citizen in every supported system theme.

## Progressive disclosure

The first layer of each page answers three questions: what is the current
state, what is the primary action, and what—if anything—requires attention.
Additional controls appear only where they refine that task. The preferred
patterns are:

- summary, then optional details;
- fastest suitable connection, then visible criteria, then an exact server;
- common setting, then its contextual exceptions;
- plain-language error, then a safe recovery action, then technical details;
- current connection summary, then the on-demand Inspector.

Progressive disclosure is not synonymous with hiding useful facts behind a
dialog. The Connection surface uses a graphical route from this device, through
the encrypted tunnel, to the VPN destination. Its protection emblem, route
state, and destination make the outcome readable before supporting text. Exact
server, protocol, Secure Core entry, and forwarded-port facts remain compact,
icon-led, and visible on the surface only when relevant. Selecting one opens the
appropriate settings, copy action, or richer on-demand Inspector.

An established VPN keeps its protection emblem and route in the positive theme
color, including during split tunneling. Only the outside-VPN branch uses the
neutral/attention color. A dashed path and the explicit “Outside VPN” label
carry the distinction without relying on color. The status summary remains
readable body text, not disabled text. Review fixtures must use the same state
colors as the real Overview, rather than the component's neutral default.

Server discovery follows the same visual grammar without forcing list data
into decorative cards. A single icon-led fastest-suitable surface states the
current capability requirements and owns the primary connect action. Native
checkboxes keep P2P, Streaming, Tor, and Secure Core requirements explicit;
search and ordinary Plasma list rows then provide country, group, pin, load,
and exact-server depth.

Settings uses one native, keyboard-accessible tab bar organized by user intent:
Connection, Protection, Plasma, and Diagnostics. Icon-led tabs replace the
undifferentiated full-page scroll while leaving the existing controls, active
warnings, validation, and asynchronous save behavior in place. Selecting or
saving a setting must not reset the chosen intent or navigate away.

Authentication uses one graphical stage and exactly one active step. Service
preparation, credentials, desktop Secret Service approval, two-factor code,
security-key interaction, security-key PIN, and authoritative-state recovery
are mutually exclusive presentations of the existing authentication state
machine. Safety warnings may remain above the stage, but an inactive form may
not compete with a pending approval or recovery action. The signed-in Account
surface uses the same centered identity cue before plan and session depth.

Revealed content must not unexpectedly move the user to another page, reorder
unrelated controls, or require memorizing a hidden choice. Preserve focus when
content expands and give disclosure controls explicit accessible names and
states.

Progressive disclosure never applies to whether the VPN is connected, whether
protection is active, the consequence of connecting or disconnecting, an
authentication request, destructive behavior, or a failure requiring action.
Do not accumulate uncommon controls in a generic Advanced page, stack nested
accordions, or replace discoverable native controls with unlabelled custom
gestures.

## Navigation

The Connection surface is the application home, not one destination competing
inside a permanent sidebar. Its device node opens protection settings, its VPN
destination opens server browsing, its central encrypted-tunnel control and
server-capability facts open the Inspector, and the signed-in identity opens
Account. The protocol fact opens settings; the forwarded-port fact copies its
value.
An icon-only gear in the upper-right opens the contextual Inspector, one Help
& information destination, and the close action. The information destination
makes community status and reporting availability visible before disclosing
release history, attribution, licensing, and Proton service links. These are
native buttons, menu items, and list rows with visible focus, tooltips where
labels are hidden, and explicit accessible names.

Pages opened from the home surface use Kirigami's ordinary back stack. Initial
deep links create the same home-backed stack, so every non-authentication page
has a visible route back to Connection. There is no application sidebar or
drawer, and the window's standard close control plus the gear menu retain
explicit exit paths. Kirigami places back navigation on the correct edge for
right-to-left desktops.

## Shared components

- `PageHeader.qml` supplies a theme-scaled icon, heading, and description.
- `ConnectionScene.qml` presents protection state and the device-to-destination
  route with semantic Plasma colors and icons.
- `ContentSizedWindow.qml` gives the app exclusive ownership of window size;
  it exposes neither manual resizing nor maximizing. Connection measures its
  content, including warnings and toolbar space. Split routing adds a curved
  outside-VPN branch below the VPN endpoint without shifting the primary
  horizontal nodes; server facts and capabilities belong to that endpoint.
  Other pages use a bounded reading height and scroll. Per-monitor work-area
  limits leave space for native decorations, including after screen changes.
  Explicit diagnostic capture dimensions do not change the interactive policy.
- `IdentityStage.qml` supplies the shared graphical sign-in and account
  identity hierarchy.
- `SectionCard.qml` groups related controls in a native Kirigami card.
- `DetailRow.qml` presents stable label/value pairs without a custom table.
- `PlasmaListItem.qml` standardizes server and location rows, icon-only
  contextual actions, accessible tooltips, and mirrored drill-in direction.

The components use Kirigami spacing units, heading levels, theme fonts,
semantic colors, standard icons, and ordinary Qt Quick Controls. They contain
no fixed font sizes, literal colors, or custom animation, so Plasma remains in
control of font scaling, contrast, color scheme, and reduced motion.

The project identity ships as a color mark plus fixed light and dark symbols.
The shared Plasma setting updates the Control Center and resident tray agent
immediately; the application-menu entry retains the color mark so it stays
recognizable under any global color scheme.

## Editorial and maintenance rules

Keep the current in-app release to three to five user-facing highlights;
technical details belong in the changelog and earlier versions and milestones
remain collapsed. Setting explanations should appear beside the choice that
needs them. Keep actionable protection and authentication guidance visible; omit
implementation details such as process allocation from ordinary settings.
Use normal text contrast for instructions, reserving disabled styling for
unavailable controls rather than treating important guidance as unavailable.

Shared components should express an actual common interaction or ownership
boundary. Prefer existing Qt/KDE facilities and targeted regression cases to
new abstractions, duplicated state, or file splitting for a line-count target.
The README describes the product and links to dated evidence; it is not a
second live test-results ledger. Demo screenshots must be labeled with their
development version and refreshed when the visible design changes.

## Verification

`qml-diagnostics-smoke` opens every primary and nested page and rejects
application-authored QML diagnostics. It also exercises graphical home
navigation, native back-stack return, and connected-only inline facts.
`qml-layout-variants-smoke` repeats that path at explicit wide and compact
viewports, at 1.5 scale, and in right-to-left mode. `qml-ui-hygiene` guards
semantic theme use, mirrored navigation, focus-visible tooltips, accessible
native interaction controls, and the absence of custom motion that could
bypass Plasma's reduced-motion preference. One application-wide
`ConnectionActionFeedback` begins only from the controller's accepted
connection-operation identifier and finishes only for the matching identifier;
individual pages and buttons do not infer or duplicate that ownership.

`scripts/check-qml-visual-matrix.sh` retains an eight-image release-review set:
wide light Connection, compact dark server discovery, scaled Settings, RTL
Help & information, a contrast-stress two-factor prompt, and reduced-motion
Connection, plus dark and compact split-route views. The contrast-stress
palette is deliberately synthetic because
Plasma does not guarantee that a named high-contrast scheme is installed; it
uses the KDE platform theme with black backgrounds, white text, bright semantic
status colors, and explicit focus and hover colors. The matrix validates every
PNG header and minimum requested viewport before reporting success and runs as
the `qml-visual-matrix` CTest release gate. Keyboard
and screen-reader review uses the same native control text, explicit accessible
names and descriptions, focus-visible tooltips, and mirrored focusable rows
guarded by the source checks above.

The 0.13 release also carries a CI mechanics-freeze gate. It compares runtime,
service, integration, and Proton-overlay paths with the accepted, unpublished
0.12.0 milestone revision. Narrow presentation-facing state and review-discovered ownership or
recovery corrections are admitted only as exact-hashed, regression-tested
deltas. Any other change outside those sealed paths must leave the UX release
and receive an independent behavioral review.

The diagnostics smoke runs against the non-networking demo backend on an
isolated session bus. Missing offscreen-only Plasma services may produce a
small version-bound framework allowance; application-authored warnings,
binding loops, JavaScript errors, component failures, detached visual objects,
and teardown errors always fail the test. A framework upgrade invalidates the
allowance until its output is reviewed.

For visual review, run `scripts/capture-qml-page.sh` inside an isolated session
bus with a page name and PNG path. The capture option starts the safe demo
adapter, skips normal Control Center and resident-agent registration, and quits
after one frame is saved. Adding the `-connected` suffix to a page name asks
only the deterministic demo adapter to enter its simulated connected state
before rendering (for example, `overview-connected` or
`inspector-connected`). Set `PROTON_KDE_CAPTURE_COLOR_SCHEME` to an installed
Plasma color-scheme name such as `BreezeDark` when reviewing a non-default
theme. The `settings-protection`, `settings-plasma`, and
`settings-diagnostics` page names select each non-default Settings intent for
visual review. The `sign-in` page uses the demo backend's safe logged-out mode;
`sign-in-two-factor` stops the sealed-FD demo authentication exercise at its
two-factor challenge. `PROTON_KDE_CAPTURE_HIGH_CONTRAST=1` applies the
synthetic contrast-stress palette, while
`PROTON_KDE_CAPTURE_REDUCED_MOTION=1` sets Plasma's animation-duration factor
to zero. Capture mode cannot create or alter a real VPN connection.

Captures default to Qt's offscreen/software path. For curve-renderer review,
use an isolated X server with `QT_QPA_PLATFORM=xcb`, an explicitly empty
`QT_QUICK_BACKEND`, and `QSG_RHI_BACKEND=opengl`. The layout fixture can
require the actual curve renderer with `PLASMA_VPN_EXPECT_CURVE_RENDERER=1`;
requesting a renderer alone does not prove it was selected.

### Bounded polish acceptance

The 2026-09-08 presentation follow-up uses the existing gates, not a new
architecture or security-review cycle:

- `presentation-layout-tests`: compact, large-text and RTL startup/release
  layouts; contextual help; keyboard activation and focus traversal; three
  to five default release highlights with keyboard-expandable history.
- The same fixture checks the positive protected-route color against the VPN
  endpoint and distinguishes the attention-colored split branch. The normal
  app smoke also checks Overview's connected-state color mapping.
- `qml-ui-hygiene`: shared page descriptions and label/value facts do not use
  disabled text, and hover help remains available to keyboard focus.
- The visual matrix covers light, dark, fractional scale, RTL, synthetic
  contrast and reduced motion; the GPU fixture separately verifies curve
  renderer selection. README images are demo captures, not live VPN evidence.

These checks do not establish screen-reader usability or certify arbitrary
third-party themes. Installed keyboard/screen-reader review, KWin sizing and
monitor changes remain manual acceptance tasks. Packaging and release approval
are separate gates.
