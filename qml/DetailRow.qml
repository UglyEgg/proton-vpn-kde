// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: root

    property string label
    property string value
    property string iconName

    Layout.fillWidth: true
    spacing: Kirigami.Units.largeSpacing

    Kirigami.Icon {
        visible: root.iconName.length > 0
        source: root.iconName
        implicitWidth: Kirigami.Units.iconSizes.small
        implicitHeight: implicitWidth
    }

    Controls.Label {
        Layout.fillWidth: true
        text: root.label
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.WordWrap
    }

    Controls.Label {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
        Layout.maximumWidth: Kirigami.Units.gridUnit * 20
        text: root.value
        horizontalAlignment: Text.AlignRight
        wrapMode: Text.Wrap
    }
}
