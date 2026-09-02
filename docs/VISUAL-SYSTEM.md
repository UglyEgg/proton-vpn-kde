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

Server discovery follows the same visual grammar without forcing list data
into decorative cards. A single icon-led fastest-suitable surface states the
current capability requirements and owns the primary connect action. Native
checkboxes keep P2P, Streaming, Tor, and Secure Core requirements explicit;
search and ordinary Plasma list rows then provide country, group, pin, load,
and exact-server depth.

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
An icon-only gear in the upper-right opens Inspector, release, reporting,
About, and close actions. These are native buttons and menu items with visible
focus, tooltips where labels are hidden, and explicit accessible names.

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

## Verification

`qml-diagnostics-smoke` opens every primary and nested page and rejects
application-authored QML diagnostics. It also exercises graphical home
navigation, native back-stack return, and connected-only inline facts.
`qml-layout-variants-smoke` repeats that path at the compact minimum, at 1.5
scale, and in right-to-left mode.
`qml-ui-hygiene` guards the theme and directionality rules above.

The 0.13 release also carries a CI mechanics-freeze gate. It compares runtime,
service, backend, native-controller, integration, and Proton-overlay paths with
the accepted 0.12.0 revision. A presentation change that crosses that boundary
must leave the UX release and receive an independent behavioral review.

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
theme. Capture mode cannot create or alter a real VPN connection.
