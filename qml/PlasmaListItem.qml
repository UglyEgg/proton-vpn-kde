// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Controls.ItemDelegate {
    id: root

    property string leadingText
    property string subtitle
    property bool showChevron: true
    property alias trailingContent: trailing.data

    horizontalPadding: Kirigami.Units.largeSpacing
    verticalPadding: Kirigami.Units.smallSpacing
    Accessible.description: subtitle

    contentItem: RowLayout {
        spacing: Kirigami.Units.largeSpacing

        Controls.Label {
            visible: root.leadingText.length > 0
            text: root.leadingText
            font: root.font
        }

        Kirigami.Icon {
            visible: root.icon.name.length > 0 || root.icon.source.toString().length > 0
            source: root.icon.name.length > 0 ? root.icon.name : root.icon.source
            implicitWidth: Kirigami.Units.iconSizes.medium
            implicitHeight: implicitWidth
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0

            Controls.Label {
                Layout.fillWidth: true
                text: root.text
                font: root.font
                elide: Text.ElideRight
            }

            Controls.Label {
                Layout.fillWidth: true
                visible: root.subtitle.length > 0
                text: root.subtitle
                color: Kirigami.Theme.disabledTextColor
                elide: Text.ElideRight
            }
        }

        RowLayout {
            id: trailing
            spacing: Kirigami.Units.smallSpacing
        }

        Kirigami.Icon {
            visible: root.showChevron
            source: root.mirrored ? "go-previous-symbolic" : "go-next-symbolic"
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: implicitWidth
        }
    }
}
