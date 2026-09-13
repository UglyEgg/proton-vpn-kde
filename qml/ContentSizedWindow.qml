// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    property real preferredWidth: Kirigami.Units.gridUnit * 48
    property real preferredHeight: Kirigami.Units.gridUnit * 36
    property real availableWidth: Screen.width
    property real availableHeight: Screen.height
    property int captureWidth: 0
    property int captureHeight: 0

    // The app owns its geometry. Leave room for native window decorations;
    // pages scroll when their content cannot fit on the current monitor.
    readonly property int fittedWidth: captureWidth > 0 ? captureWidth
        : Math.max(1, Math.floor(Math.min(preferredWidth,
            availableWidth - Kirigami.Units.gridUnit * 2)))
    readonly property int fittedHeight: captureHeight > 0 ? captureHeight
        : Math.max(1, Math.ceil(Math.min(preferredHeight,
            availableHeight - Kirigami.Units.gridUnit * 3)))

    width: fittedWidth
    height: fittedHeight
    minimumWidth: fittedWidth
    maximumWidth: fittedWidth
    minimumHeight: fittedHeight
    maximumHeight: fittedHeight
    flags: Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint
           | Qt.WindowSystemMenuHint | Qt.WindowMinimizeButtonHint
           | Qt.WindowCloseButtonHint
}
