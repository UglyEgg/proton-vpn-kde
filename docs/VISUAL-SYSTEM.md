# Plasma visual system

Version `0.10.0` makes the Control Center a responsive Kirigami desktop
application. It changes presentation only. Proton Core remains the owner of
account policy, networking, protocols, NetworkManager, DNS, kill switch, and
split tunneling.

## Navigation

Wide windows keep the standard Kirigami global drawer open as a resizable
sidebar. Its current section is selected and its actions use the installed
Plasma icon theme. Compact windows use the same drawer as an overlay, so there
is one navigation model and one keyboard order across window sizes. Kirigami
places the drawer on the correct edge for a right-to-left desktop.

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

## Verification

`qml-diagnostics-smoke` opens every primary and nested page and rejects
application-authored QML diagnostics. `qml-layout-variants-smoke` repeats that
path at the compact minimum, at 1.5 scale, and in right-to-left mode.
`qml-ui-hygiene` guards the theme and directionality rules above.

For visual review, run `scripts/capture-qml-page.sh` inside an isolated session
bus with a page name and PNG path. The capture option starts the safe demo
adapter, skips normal Control Center and resident-agent registration, and quits
after one frame is saved. It cannot create or alter a real VPN connection.
