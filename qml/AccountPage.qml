// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Account")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        PageHeader {
            heading: vpnController.accountName
            description: qsTr("Proton account")
            iconName: "user-identity"
        }

        SectionCard {
            title: qsTr("Subscription")
            iconName: "emblem-favorite"

            DetailRow {
                label: qsTr("VPN plan")
                value: vpnController.planTitle.length > 0
                       ? vpnController.planTitle : qsTr("Free")
            }

            DetailRow {
                label: qsTr("Connections")
                value: qsTr("Up to %1 devices").arg(vpnController.maxConnections)
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    text: qsTr("Manage Proton account")
                    icon.name: "internet-web-browser"
                    onClicked: Qt.openUrlExternally(
                        "https://account.protonvpn.com/account")
                }
            }
        }

        SectionCard {
            title: qsTr("Session")
            description: qsTr("Manage the saved account session on this device.")
            iconName: "document-encrypt"

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                type: Kirigami.MessageType.Warning
                visible: vpnController.state !== "disconnected"
                text: vpnController.settings.killSwitch > 0
                      ? qsTr("Signing out will disconnect the active VPN tunnel and disable the kill switch.")
                      : qsTr("Signing out will disconnect the active VPN tunnel.")
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    text: vpnController.busy ? qsTr("Signing out…") : qsTr("Sign out")
                    icon.name: "system-log-out"
                    enabled: !vpnController.busy
                    onClicked: logoutDialog.open()
                }
            }
        }
    }

    Controls.Dialog {
        id: logoutDialog
        anchors.centerIn: parent
        title: qsTr("Sign out of Proton VPN?")
        modal: true
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.Cancel

        Controls.Label {
            width: Kirigami.Units.gridUnit * 20
            wrapMode: Text.WordWrap
            text: vpnController.settings.killSwitch > 0
                  ? qsTr("The VPN tunnel will be disconnected, the kill switch will be disabled, and the saved Proton session will be removed from your Secret Service provider.")
                  : vpnController.state === "disconnected"
                    ? qsTr("The saved Proton session will be removed from your Secret Service provider.")
                    : qsTr("The VPN tunnel will be disconnected and the saved Proton session will be removed from your Secret Service provider.")
        }

        onAccepted: vpnController.logout()
    }
}
