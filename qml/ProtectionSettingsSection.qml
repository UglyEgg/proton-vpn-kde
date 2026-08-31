// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    required property var vpnController
    required property var vpnSettings
    required property real pageWidth

    title: qsTr("Protection and performance")
    description: qsTr("Control filtering, acceleration, NAT, and tunnel features.")
    iconName: "security-high"

    Kirigami.FormLayout {
        Layout.fillWidth: true
        wideMode: pageWidth >= Kirigami.Units.gridUnit * 36

        Controls.ComboBox {
            Kirigami.FormData.label: qsTr("NetShield:")
            Layout.fillWidth: true
            model: [
                { "id": 0, "name": qsTr("Off") },
                { "id": 1, "name": qsTr("Block malware") },
                { "id": 2, "name": qsTr("Block ads, trackers, and malware") }
            ]
            textRole: "name"
            valueRole: "id"
            currentIndex: vpnSettings.netShield
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.paidFeaturesAvailable
            onActivated: vpnController.updateSetting("netShield", currentValue)
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Performance:")
            text: qsTr("Enable VPN Accelerator")
            checked: vpnSettings.vpnAccelerator
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.paidFeaturesAvailable
            onClicked: vpnController.updateSetting("vpnAccelerator", checked)
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("NAT:")
            text: qsTr("Use moderate NAT")
            checked: vpnSettings.moderateNat
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.paidFeaturesAvailable
            onClicked: vpnController.updateSetting("moderateNat", checked)
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("P2P:")
            text: qsTr("Enable port forwarding")
            checked: vpnSettings.portForwarding
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.paidFeaturesAvailable
            onClicked: vpnController.updateSetting("portForwarding", checked)
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("IPv6:")
            text: qsTr("Tunnel IPv6 traffic")
            checked: vpnSettings.ipv6
            enabled: vpnSettings.loaded && !vpnSettings.busy
            onClicked: vpnController.updateSetting("ipv6", checked)
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnSettings.loaded && !vpnSettings.paidFeaturesAvailable
            type: Kirigami.MessageType.Information
            text: qsTr("NetShield, VPN Accelerator, moderate NAT, and port forwarding require a paid Proton VPN plan.")
        }
    }
}
