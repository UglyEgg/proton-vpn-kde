// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Dialogs as Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Plasma VPN")

    readonly property var settings: kcm.appSettings

    Dialogs.FolderDialog {
        id: packetCaptureFolderDialog
        title: qsTr("Select packet capture folder")
        onAccepted: page.settings.setPacketCaptureDirectoryUrl(selectedFolder)
    }

    Kirigami.FormLayout {
        wideMode: page.width >= Kirigami.Units.gridUnit * 28

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            type: Kirigami.MessageType.Information
            text: qsTr("Plasma integration settings are saved immediately. Account and tunnel settings remain in the authenticated Proton VPN client so their live safety constraints stay authoritative.")
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Startup and connection")
        }

        Controls.TextField {
            Kirigami.FormData.label: qsTr("Auto connect:")
            Layout.fillWidth: true
            text: page.settings.autoConnectTarget
            placeholderText: qsTr("Off, FASTEST, US, or CH#101")
            onEditingFinished: {
                page.settings.autoConnectTarget = text
                text = page.settings.autoConnectTarget
            }
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Recovery:")
            text: qsTr("Reconnect dropped VPN tunnels")
            checked: page.settings.reconnectEnabled
            onToggled: page.settings.reconnectEnabled = checked
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Startup:")
            text: qsTr("Open only the Plasma tray controls at startup")
            checked: page.settings.startMinimized
            onToggled: page.settings.startMinimized = checked
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Window:")
            text: qsTr("Keep Plasma tray controls available after closing")
            checked: page.settings.closeToTray
            onToggled: page.settings.closeToTray = checked
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Plasma integration")
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Notifications:")
            text: qsTr("Show connection notifications")
            checked: page.settings.notificationsEnabled
            onToggled: page.settings.notificationsEnabled = checked
        }

        Controls.ComboBox {
            Kirigami.FormData.label: qsTr("Interface icon:")
            Layout.fillWidth: true
            model: [
                { "label": qsTr("Color"), "value": "color" },
                { "label": qsTr("Light symbol"), "value": "light" },
                { "label": qsTr("Dark symbol"), "value": "dark" }
            ]
            textRole: "label"
            valueRole: "value"
            currentIndex: page.settings.iconStyle === "light" ? 1
                          : page.settings.iconStyle === "dark" ? 2 : 0
            Accessible.name: qsTr("Interface icon style")
            onActivated: page.settings.iconStyle = currentValue
        }

        Controls.TextField {
            Kirigami.FormData.label: qsTr("Tray favorites:")
            Layout.fillWidth: true
            text: page.settings.pinnedServersText
            placeholderText: qsTr("US, CH, CH#101")
            onEditingFinished: {
                page.settings.pinnedServersText = text
                text = page.settings.pinnedServersText
            }
        }

        Controls.Button {
            Kirigami.FormData.label: qsTr("Shortcuts:")
            text: qsTr("Configure Global Shortcuts…")
            icon.name: "configure-shortcuts"
            onClicked: kcm.openGlobalShortcuts()
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Troubleshooting")
        }

        RowLayout {
            Kirigami.FormData.label: qsTr("Packet captures:")
            Layout.fillWidth: true

            Controls.TextField {
                Layout.fillWidth: true
                readOnly: true
                text: page.settings.packetCaptureDirectory
            }

            Controls.Button {
                text: qsTr("Choose…")
                icon.name: "document-open-folder"
                onClicked: packetCaptureFolderDialog.open()
            }
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Proton VPN settings")
        }

        Controls.Button {
            text: qsTr("Open full VPN settings…")
            icon.name: "settings-configure"
            onClicked: kcm.openFullSettings()
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 24
            wrapMode: Text.WordWrap
            text: qsTr("Protocol, kill switch, NetShield, DNS, split tunneling, port forwarding, and account-dependent features open in the client because availability can change with the active connection and Proton plan.")
            color: Kirigami.Theme.disabledTextColor
        }
    }
}
