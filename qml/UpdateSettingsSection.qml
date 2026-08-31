// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    required property var updateChannel
    signal confirmationRequested(bool enableBeta)

    visible: updateChannel.available
    title: qsTr("Updates")
    description: qsTr("Choose the Proton package channel used by Fedora.")
    iconName: "system-software-update"

    RowLayout {
        Layout.fillWidth: true
        visible: updateChannel.available

        Controls.Switch {
            text: qsTr("Beta access")
            checked: updateChannel.betaEnabled
            enabled: !updateChannel.busy
            onClicked: {
                checked = Qt.binding(function() {
                    return updateChannel.betaEnabled
                })
                confirmationRequested(!updateChannel.betaEnabled)
            }
        }

        Controls.BusyIndicator {
            visible: updateChannel.busy
            running: visible
            implicitWidth: Kirigami.Units.iconSizes.small
            implicitHeight: implicitWidth
        }
    }

    Controls.Label {
        Layout.maximumWidth: Kirigami.Units.gridUnit * 22
        wrapMode: Text.WordWrap
        visible: updateChannel.available
        text: qsTr("Selects Proton's Fedora package repository. Package installation remains managed by Discover or dnf.")
        color: Kirigami.Theme.disabledTextColor
    }

    Kirigami.InlineMessage {
        Layout.fillWidth: true
        visible: updateChannel.available && updateChannel.message.length > 0
        type: updateChannel.error ? Kirigami.MessageType.Error
                                  : Kirigami.MessageType.Information
        text: updateChannel.message
    }
}
