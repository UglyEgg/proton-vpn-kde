// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    required property var vpnController
    required property var vpnSettings
    required property var appSettings
    required property real pageWidth

    title: qsTr("VPN connection")
    description: qsTr("Choose how and when this device connects.")
    iconName: "network-vpn"

    Kirigami.FormLayout {
        Layout.fillWidth: true
        wideMode: pageWidth >= Kirigami.Units.gridUnit * 36

        Controls.ComboBox {
            Kirigami.FormData.label: qsTr("Protocol:")
            Layout.fillWidth: true
            model: vpnSettings.protocolOptions
            textRole: "name"
            valueRole: "id"
            currentIndex: vpnSettings.protocolIndex
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.protocolEditable
            onActivated: vpnController.updateSetting("protocol", currentValue)
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: vpnSettings.loaded && !vpnSettings.protocolEditable
            text: qsTr("Disconnect the VPN to change protocols.")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.TextField {
            Kirigami.FormData.label: qsTr("Auto connect:")
            Layout.fillWidth: true
            text: appSettings.autoConnectTarget
            placeholderText: qsTr("Off, FASTEST, US, or CH#101")
            onEditingFinished: {
                appSettings.autoConnectTarget = text
                text = appSettings.autoConnectTarget
            }
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: qsTr("Connect to the fastest server, a country, or an exact server when the app starts.")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.ComboBox {
            Kirigami.FormData.label: qsTr("Kill switch:")
            Layout.fillWidth: true
            model: [
                { "id": 0, "name": qsTr("Off") },
                { "id": 1, "name": qsTr("Standard") },
                { "id": 2, "name": qsTr("Permanent") }
            ]
            textRole: "name"
            valueRole: "id"
            currentIndex: vpnSettings.killSwitch
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.killSwitchEditable
            onActivated: vpnController.updateSetting("killSwitch", currentValue)
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: vpnSettings.loaded && !vpnSettings.killSwitchEditable
            text: qsTr("Disconnect the VPN to change kill-switch mode.")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Recovery:")
            text: qsTr("Reconnect dropped VPN tunnels")
            checked: appSettings.reconnectEnabled
            onToggled: appSettings.reconnectEnabled = checked
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: qsTr("Retries the same Proton server after an unexpected drop. This never connects a deliberately disconnected VPN.")
            color: Kirigami.Theme.disabledTextColor
        }
    }
}
