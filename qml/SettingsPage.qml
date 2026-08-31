// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Dialogs as Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Settings")

    readonly property var controller: vpnController
    readonly property var integrationSettings: appSettings
    readonly property var packageChannel: updateChannel
    property var vpnSettings: vpnController.settings
    property var splitSettings: vpnController.splitTunneling
    property var customDns: vpnController.customDns
    property var packetCaptureFolderDialog: null

    Component {
        id: packetCaptureFolderDialogComponent

        Dialogs.FolderDialog {
            title: qsTr("Select packet capture folder")
            onAccepted: appSettings.setPacketCaptureDirectoryUrl(selectedFolder)
        }
    }

    function openPacketCaptureFolderDialog() {
        if (packetCaptureFolderDialog === null) {
            packetCaptureFolderDialog =
                packetCaptureFolderDialogComponent.createObject(page)
        }
        packetCaptureFolderDialog.open()
    }

    Controls.Dialog {
        id: updateChannelDialog
        property bool enableBeta: false
        anchors.centerIn: parent
        modal: true
        title: enableBeta ? qsTr("Enable Beta access?")
                          : qsTr("Disable Beta access?")
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.Cancel

        Controls.Label {
            width: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: updateChannelDialog.enableBeta
                  ? qsTr("This will replace Proton's stable Fedora repository package with its Beta repository package. Install the offered updates afterward to use Beta components.")
                  : qsTr("This will replace Proton's Beta Fedora repository package with its stable repository package. Install the offered updates afterward to return to stable components.")
        }

        onAccepted: updateChannel.setBetaEnabled(enableBeta)
    }

    Component.onDestruction: {
        if (vpnController.packetCaptureActive) {
            vpnController.stopPacketCapture()
        }
        if (packetCaptureFolderDialog !== null) {
            packetCaptureFolderDialog.destroy()
        }
    }

    Component.onCompleted: {
        if (vpnController.loggedIn && !vpnSettings.loaded) {
            vpnController.loadSettings()
        }
        if (vpnController.loggedIn && !splitSettings.loaded) {
            vpnController.loadSplitTunneling()
        }
        if (vpnController.loggedIn && !customDns.loaded) {
            vpnController.loadCustomDns()
        }
        updateChannel.refresh()
    }

    Connections {
        target: vpnController
        function onSnapshotChanged() {
            if (vpnController.loggedIn && !page.vpnSettings.loaded
                    && !page.vpnSettings.busy) {
                vpnController.loadSettings()
            }
            if (vpnController.loggedIn && !page.splitSettings.loaded
                    && !page.splitSettings.busy) {
                vpnController.loadSplitTunneling()
            }
            if (vpnController.loggedIn && !page.customDns.loaded
                    && !page.customDns.busy) {
                vpnController.loadCustomDns()
            }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        PageHeader {
            heading: qsTr("Settings")
            description: qsTr("Configure Proton VPN and its Plasma integration.")
            iconName: "settings-configure"
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !vpnController.loggedIn
            type: Kirigami.MessageType.Information
            text: qsTr("Sign in to change Proton VPN settings.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnSettings.message.length > 0
            type: Kirigami.MessageType.Error
            text: vpnSettings.message
        }

        RowLayout {
            Layout.fillWidth: true
            visible: vpnController.loggedIn && vpnSettings.busy

            Controls.BusyIndicator {
                running: parent.visible
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
            }

            Controls.Label {
                text: qsTr("Updating VPN settings…")
                color: Kirigami.Theme.disabledTextColor
            }
        }

        VpnConnectionSettingsSection {
            vpnController: page.controller
            vpnSettings: page.vpnSettings
            appSettings: page.integrationSettings
            pageWidth: page.width
        }

        FastestSettingsSection {
            appSettings: page.integrationSettings
        }

        ProtectionSettingsSection {
            vpnController: page.controller
            vpnSettings: page.vpnSettings
            pageWidth: page.width
        }

        CustomDnsSettingsSection {
            vpnController: page.controller
            vpnSettings: page.vpnSettings
            customDns: page.customDns
            pageWidth: page.width
            onManageRequested: applicationWindow().pushCustomDns()
        }

        SplitTunnelingSettingsSection {
            vpnController: page.controller
            vpnSettings: page.vpnSettings
            splitSettings: page.splitSettings
            pageWidth: page.width
            onManageRequested: applicationWindow().pushSplitTunneling()
        }

        PrivacySettingsSection {
            vpnController: page.controller
            vpnSettings: page.vpnSettings
            appSettings: page.integrationSettings
            pageWidth: page.width
            onBrowseRequested: page.openPacketCaptureFolderDialog()
        }

        PlasmaIntegrationSettingsSection {
            appSettings: page.integrationSettings
            pageWidth: page.width
        }

        UpdateSettingsSection {
            updateChannel: page.packageChannel
            onConfirmationRequested: function(enableBeta) {
                updateChannelDialog.enableBeta = enableBeta
                updateChannelDialog.open()
            }
        }
    }
}
