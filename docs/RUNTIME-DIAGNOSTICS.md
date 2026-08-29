# Native runtime diagnostics

The `qml-diagnostics-smoke` test opens every primary and nested page against
the non-networking demo backend, tears down the current page, and quits while
disconnected. It captures Qt messages on stderr and rejects every unexpected
line. This includes application-authored QML warnings, detached graphical
objects, binding loops, uncaught JavaScript errors, and component-load errors.

The offscreen test environment does not provide a Plasma status-notifier host
or the KGlobalAccel session service. Its private session bus has no activation
directories, so navigating a declarative file-dialog component cannot launch
unrelated host portal daemons inside the test sandbox. The demo backend is
started explicitly. Kirigami 6.29.0 with Qt 6.11.1 emits three fixed
diagnostics for the remaining missing test-only services:

- `A connection to the bus can't be made`
- `KDE platform plugin is loaded but SNI unavailable`
- the fixed `org.kde.kglobalaccel.service` `ServiceUnknown` message

Those lines are accepted only for that exact Kirigami/Qt version pair. A
framework update disables the allowance and requires the output to be reviewed
before the tested versions are updated. The installed Plasma acceptance check
uses the real status-notifier, global-shortcut, portal, and graphics services
and therefore must not produce any of the offscreen allowances.

Page components are created with the visible page stack as their QObject and
visual owner before insertion. Kirigami's desktop overlay drawer supplies
navigation without the action-menu binding cycle triggered by its desktop
dropdown mode on the tested framework versions. The custom About layout has no
latent overlay sheet, so clearing it during navigation or application shutdown
cannot evaluate a binding through a destroyed window.

The overview also reports whether both API Core server-string sharing paths
are active. The backend applies them to synthetic dictionaries only and checks
object identity; it never reads or mutates the live server list. If either the
fresh-response or cache-decoding optimization is absent, the UI displays Core's
installed Python package version and a non-blocking memory-usage warning. VPN
networking and authentication behavior remain unchanged.
