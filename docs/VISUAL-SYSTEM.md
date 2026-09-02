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

Progressive disclosure is not synonymous with a stack of cards. The Connection
surface uses a graphical route from this device, through the encrypted tunnel,
to the VPN destination. Its protection emblem, route state, and destination
make the outcome readable before supporting text; the exact identifiers and
Inspector remain available on request.

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

Wide windows keep the standard Kirigami global drawer open as a resizable
sidebar. Connection, Browse servers, and Settings form the primary task group;
Account remains directly reachable, while diagnostics, release history,
reporting status, About, and the explicit close action use one native More
drill-in. Its current section is selected and its actions use the installed
Plasma icon theme. Compact windows use the same drawer as an overlay, so there
is one navigation model and one keyboard order across window sizes. Kirigami
places the drawer on the correct edge for a right-to-left desktop. A user's
wide-layout collapsed state survives a compact-window transition; returning to
the wide layout restores both the icon sidebar and its expand control. The
compact overlay always exposes Kirigami's standard open handle.

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
application-authored QML diagnostics. It also exercises expanded, collapsed,
compact-overlay, and restored sidebar states. `qml-layout-variants-smoke`
repeats that path at the compact minimum, at 1.5 scale, and in right-to-left mode.
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
`inspector-connected`). Use `overview-details-connected` to capture the
explicitly disclosed connection-detail state. Capture mode cannot create or
alter a real VPN connection.
