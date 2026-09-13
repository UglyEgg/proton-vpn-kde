// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    property string iconSource
    property string heading
    property string description
    property color accentColor: Kirigami.Theme.highlightColor

    Layout.fillWidth: true
    spacing: Kirigami.Units.smallSpacing

    Item {
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 6

        Rectangle {
            anchors.centerIn: parent
            width: Kirigami.Units.gridUnit * 5
            height: width
            radius: width / 2
            color: Kirigami.Theme.backgroundColor
            border.width: 2
            border.color: root.accentColor

            Rectangle {
                anchors.centerIn: parent
                width: parent.width - Kirigami.Units.largeSpacing
                height: width
                radius: width / 2
                color: Kirigami.Theme.alternateBackgroundColor
            }

            Kirigami.Icon {
                anchors.centerIn: parent
                source: root.iconSource
                color: Kirigami.Theme.textColor
                implicitWidth: Kirigami.Units.iconSizes.huge
                implicitHeight: implicitWidth
                Accessible.ignored: true
            }
        }
    }

    Kirigami.Heading {
        Layout.fillWidth: true
        level: 1
        text: root.heading
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }

    Controls.Label {
        Layout.fillWidth: true
        text: root.description
        color: Kirigami.Theme.disabledTextColor
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }
}
