# Plasma visual system

## Contract

The Control Center uses Qt 6, Kirigami, and KDE Frameworks as native desktop
facilities. Plasma owns color scheme, typography, icon theme, font scaling,
contrast, directionality, focus, and reduced-motion preferences.

Project UI uses:

- Kirigami spacing and heading levels;
- semantic theme colors;
- standard icons and controls;
- mirrored navigation and layout;
- visible keyboard focus and accessible names; and
- no fixed font sizes, literal palette colors, or custom animation timing.

## Progressive disclosure

The first layer of each page presents current state, the primary action, and
any required attention. Additional controls appear in the context they refine.

| Intent | First layer | Disclosed depth |
| --- | --- | --- |
| Connect | Protection state and Connect/Disconnect | Server, protocol, capabilities, protection |
| Select destination | Fastest suitable and active filters | Country, state/city, exact server, load |
| Configure | Settings grouped by outcome | DNS, split tunneling, conflicts, diagnostics |
| Authenticate | One active authentication step | TOTP, recovery code, Core-compatible FIDO2 |
| Diagnose | Plain-language state and recovery | Technical status and read-only Inspector |

Connection/protection state, action consequences, authentication requests,
destructive behavior, and actionable failures are never hidden as optional
detail.

## Connection scene

The home page is a graphical route from device through encrypted tunnel to VPN
destination. The device opens protection settings; destination opens server
browsing; tunnel facts open the Inspector or relevant settings; identity opens
Account.

Connected routes and the protection emblem use the positive semantic color.
Split tunneling adds a curved, arrow-free outside-VPN branch using the attention
color, a dashed stroke, an explicit `Outside VPN` label, and a split emblem.
Meaning must not depend on color alone. Exact server, protocol, Secure Core
entry, and forwarding facts sit beside the destination when relevant.

The gear menu exposes Inspector, Help and information, and Close. Destinations
use Kirigami's native back stack; the application has no permanent sidebar or
drawer.

## Shared components

| Component | Responsibility |
| --- | --- |
| `ConnectionScene.qml` | Protection state, route, destination, split branch |
| `ContentSizedWindow.qml` | App-owned dimensions within active work area; no manual resize/maximize |
| `IdentityStage.qml` | Sign-in and signed-in account hierarchy |
| `PageHeader.qml` | Theme-scaled icon, heading, description |
| `SectionCard.qml` | Related controls in a Kirigami card |
| `DetailRow.qml` | Stable label/value facts |
| `PlasmaListItem.qml` | Server/location rows, actions, mirrored drill-in |

Connection height follows active warnings and split-route content. Other pages
use bounded reading height and scrolling. Screen/work-area changes recompute
the size without exposing manual resizing.

The project ships color, light-symbol, and dark-symbol icons. The shared Plasma
preference updates the Control Center and tray agent; the desktop entry retains
the color mark.

## Editorial rules

- Keep in-app current-release notes to three to five user-facing highlights.
- Put technical detail in the changelog and engineering references.
- Keep actionable guidance at normal text contrast.
- Use disabled styling only for unavailable controls.
- Preserve page, tab, and focus position across asynchronous saves.
- Add shared components only for a real interaction or ownership contract.
- Label screenshots as deterministic demo captures and refresh them for visible
  release changes.

## Verification

| Gate | Coverage |
| --- | --- |
| `qml-diagnostics-smoke` | All primary/nested pages; application-authored QML diagnostics |
| `qml-layout-variants-smoke` | Wide, compact, 1.5x scale, RTL |
| `qml-ui-hygiene` | Semantic colors, mirroring, accessible controls/tooltips, motion policy |
| `presentation-layout-tests` | Connection, authentication, Settings, Help, release-note behavior |
| `qml-visual-matrix` | Light/dark, compact, scale, RTL, contrast stress, reduced motion, split route |

The visual matrix uses the KDE platform theme and deterministic demo backend.
Contrast stress uses an explicit synthetic palette rather than assuming a
named high-contrast theme is installed. Application diagnostics, binding loops,
JavaScript errors, component failures, detached visual objects, and teardown
errors fail the gate.

Capture a page with:

```bash
scripts/capture-qml-page.sh build PAGE OUTPUT.png
```

Useful environment controls:

```text
PROTON_KDE_CAPTURE_COLOR_SCHEME=BreezeDark
PROTON_KDE_CAPTURE_HIGH_CONTRAST=1
PROTON_KDE_CAPTURE_REDUCED_MOTION=1
```

Connected page names use only the demo adapter. Curve-renderer review uses an
isolated X server, `QT_QPA_PLATFORM=xcb`, `QSG_RHI_BACKEND=opengl`, and
`PLASMA_VPN_EXPECT_CURVE_RENDERER=1`.

Automated checks do not certify screen-reader usability or arbitrary
third-party themes. Installed keyboard, screen-reader, KWin sizing, and
multi-monitor behavior remain manual acceptance surfaces.
