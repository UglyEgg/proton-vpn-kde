// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    required property var vpnController
    required property var vpnSettings
    required property var customDns
    required property real pageWidth
    signal manageRequested()

    title: qsTr("Custom DNS")
    description: qsTr("Use numeric DNS server addresses on new VPN connections.")
    iconName: "network-server-database"

    Kirigami.FormLayout {
        Layout.fillWidth: true
        wideMode: pageWidth >= Kirigami.Units.gridUnit * 36

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.message.length > 0
            type: Kirigami.MessageType.Error
            text: customDns.message
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("DNS:")
            text: qsTr("Use custom DNS servers")
            checked: customDns.enabled
            enabled: customDns.loaded && customDns.paidFeaturesAvailable
                     && !customDns.busy
                     && (checked || vpnSettings.netShield === 0)
            onClicked: vpnController.updateCustomDns("enabled", checked)
        }

        Controls.Button {
            Kirigami.FormData.label: qsTr("Servers:")
            text: customDns.serverCount > 0
                  ? qsTr("Manage %n server(s)…", "", customDns.serverCount)
                  : qsTr("Add DNS servers…")
            icon.name: "network-server-database"
            enabled: customDns.loaded && customDns.paidFeaturesAvailable
                     && !customDns.busy
            onClicked: manageRequested()
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.restartRequired
            type: Kirigami.MessageType.Information
            text: qsTr("Reconnect the VPN to apply the custom DNS changes.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.loaded && vpnSettings.loaded
                     && vpnSettings.netShield !== 0
            type: Kirigami.MessageType.Warning
            text: qsTr("Disable NetShield before enabling custom DNS. Neither setting will be changed automatically.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.loaded && !customDns.paidFeaturesAvailable
            type: Kirigami.MessageType.Information
            text: qsTr("Custom DNS requires a paid Proton VPN plan.")
        }
    }
}
