// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    id: section

    required property var vpnController
    required property var vpnSettings
    required property var splitSettings
    required property real pageWidth
    readonly property bool protocolCompatible:
        vpnSettings.protocol === "wireguard"
        || vpnSettings.protocol.indexOf("protun-") === 0
    readonly property bool configurationEditable:
        !splitSettings.enabled
        || (protocolCompatible && vpnSettings.killSwitch === 0)
    signal manageRequested()

    title: qsTr("Split tunneling")
    description: qsTr("Choose which applications and addresses use the VPN tunnel.")
    iconName: "applications-all"

    Kirigami.FormLayout {
        Layout.fillWidth: true
        wideMode: pageWidth >= Kirigami.Units.gridUnit * 36

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.message.length > 0
            type: Kirigami.MessageType.Error
            text: splitSettings.message
        }

        RowLayout {
            Layout.fillWidth: true
            visible: vpnController.loggedIn && splitSettings.busy

            Controls.BusyIndicator {
                running: parent.visible
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
            }

            Controls.Label {
                text: qsTr("Updating split-tunneling settings…")
                color: Kirigami.Theme.disabledTextColor
            }
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Applications:")
            text: qsTr("Enable split tunneling")
            checked: splitSettings.enabled
            enabled: splitSettings.loaded && splitSettings.available
                     && splitSettings.paidFeaturesAvailable
                     && !splitSettings.busy
                     && (checked || (vpnSettings.killSwitch === 0
                                     && section.protocolCompatible))
            onClicked: vpnController.updateSplitTunneling("enabled", checked)
        }

        Controls.ComboBox {
            Kirigami.FormData.label: qsTr("Mode:")
            Layout.fillWidth: true
            model: [
                { "id": "exclude", "name": qsTr("Exclude selected apps") },
                { "id": "include", "name": qsTr("Only include selected apps") }
            ]
            textRole: "name"
            valueRole: "id"
            currentIndex: splitSettings.modeIndex
            enabled: splitSettings.loaded && splitSettings.available
                     && splitSettings.paidFeaturesAvailable
                     && !splitSettings.busy
                     && section.configurationEditable
            onActivated: vpnController.updateSplitTunneling("mode", currentValue)
        }

        Controls.Button {
            Kirigami.FormData.label: qsTr("Rules:")
            text: qsTr("Choose applications and IP ranges…")
            icon.name: "applications-all"
            enabled: splitSettings.loaded && splitSettings.available
                     && splitSettings.paidFeaturesAvailable
                     && !splitSettings.busy
                     && section.configurationEditable
            onClicked: manageRequested()
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.loaded && !splitSettings.available
            type: Kirigami.MessageType.Information
            text: qsTr("The installed Proton VPN backend reports that split tunneling is unavailable on this system.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.loaded && splitSettings.available
                     && !splitSettings.paidFeaturesAvailable
            type: Kirigami.MessageType.Information
            text: qsTr("Split tunneling requires a paid Proton VPN plan.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.loaded && vpnSettings.loaded
                     && vpnSettings.killSwitch !== 0
            type: Kirigami.MessageType.Warning
            text: splitSettings.enabled
                  ? qsTr("Turn split tunneling off before editing its rules, or disable the kill switch first.")
                  : qsTr("Disable the kill switch before enabling split tunneling.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.loaded && vpnSettings.loaded
                     && !section.protocolCompatible
            type: Kirigami.MessageType.Warning
            text: splitSettings.enabled
                  ? qsTr("Turn split tunneling off before editing its rules, or select WireGuard first.")
                  : qsTr("Select WireGuard or a compatible protocol before enabling split tunneling.")
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: splitSettings.loaded
                     && splitSettings.selectedIpRangeCount > 0
            text: qsTr("%n IP rule(s) are configured in this mode.",
                       "", splitSettings.selectedIpRangeCount)
            color: Kirigami.Theme.disabledTextColor
        }
    }
}
