# Plasma visual system

The Control Center is a responsive Kirigami desktop application. These rules
govern presentation only. Proton Core remains the owner of account policy,
networking, protocols, NetworkManager, DNS, kill switch, and split tunneling.

## Navigation

Wide windows keep the standard Kirigami global drawer open as a resizable
sidebar. Its current section is selected and its actions use the installed
Plasma icon theme. Compact windows use the same drawer as an overlay, so there
is one navigation model and one keyboard order across window sizes. Kirigami
places the drawer on the correct edge for a right-to-left desktop. A user's
wide-layout collapsed state survives a compact-window transition; returning to
the wide layout restores both the icon sidebar and its expand control. The
compact overlay always exposes Kirigami's standard open handle.

## Shared components

- `PageHeader.qml` supplies a theme-scaled icon, heading, and description.
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

The diagnostics smoke runs against the non-networking demo backend on an
isolated session bus. Missing offscreen-only Plasma services may produce a
small version-bound framework allowance; application-authored warnings,
binding loops, JavaScript errors, component failures, detached visual objects,
and teardown errors always fail the test. A framework upgrade invalidates the
allowance until its output is reviewed.

For visual review, run `scripts/capture-qml-page.sh` inside an isolated session
bus with a page name and PNG path. The capture option starts the safe demo
adapter, skips normal Control Center and resident-agent registration, and quits
after one frame is saved. The special `overview-connected` page asks only the
deterministic demo adapter to enter its simulated connected state. Capture mode
cannot create or alter a real VPN connection.
