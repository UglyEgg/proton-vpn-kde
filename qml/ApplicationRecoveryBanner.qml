// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.InlineMessage {
    id: root

    required property var vpnController
    required property var dialogErrorCodes
    property bool showPacketCaptureError: true
    readonly property bool recoveryActive:
        vpnController.loggedIn
        && vpnController.state === "unresponsive"
        && vpnController.backendRestartAllowed
    readonly property bool connectionErrorActive:
        vpnController.loggedIn
        && vpnController.state === "error"
        && !dialogErrorCodes.includes(vpnController.errorCode)
    readonly property bool snapshotErrorActive:
        vpnController.snapshotError.length > 0
    readonly property bool packetCaptureErrorActive:
        showPacketCaptureError
        && vpnController.packetCaptureError.length > 0
    readonly property bool shutdownActive: vpnController.shutdownPending
    readonly property bool bannerActive:
        snapshotErrorActive || packetCaptureErrorActive
        || recoveryActive || connectionErrorActive || shutdownActive

    objectName: "applicationBackendRecovery"
    visible: bannerActive
    height: visible ? implicitHeight : 0
    type: shutdownActive
          && !snapshotErrorActive && !packetCaptureErrorActive
          && !recoveryActive && !connectionErrorActive
          ? Kirigami.MessageType.Information : Kirigami.MessageType.Error
    text: {
        if (root.snapshotErrorActive) {
            return vpnController.snapshotError
        }
        if (root.packetCaptureErrorActive) {
            return vpnController.packetCaptureError
        }
        if (root.recoveryActive) {
            return vpnController.message.length > 0
                   ? vpnController.message
                   : qsTr("The local Proton VPN service is not responding.")
        }
        if (root.shutdownActive) {
            return qsTr("Stopping the troubleshooting capture before closing…")
        }
        const summary = root.connectionErrorText(vpnController.errorCode)
        return summary
               + (vpnController.message.length > 0
                  ? "\n" + vpnController.message : "")
    }

    function connectionErrorText(code) {
        const messages = {
            "tunnel_setup_failed": qsTr("Tunnel setup failed"),
            "timeout": qsTr("The connection attempt timed out"),
            "device_disconnected": qsTr("The VPN device disconnected"),
            "certificate_expired": qsTr("Refreshing the VPN certificate…"),
            "unexpected_error": qsTr("An unexpected connection error occurred")
        }
        return messages[code] ?? qsTr("VPN connection failed")
    }

    function requestRestart() {
        vpnController.restartBackend()
    }

    function requestSnapshotRefresh() {
        vpnController.refresh()
    }

    actions: [
        Kirigami.Action {
            objectName: "restartUnresponsiveBackendAction"
            text: qsTr("Restart service")
            icon.name: "view-refresh"
            visible: root.recoveryActive
                     || (root.snapshotErrorActive
                         && root.vpnController.snapshotRestartAllowed)
            onTriggered: root.requestRestart()
        },
        Kirigami.Action {
            objectName: "refreshInvalidSnapshotAction"
            text: qsTr("Refresh state")
            icon.name: "view-refresh"
            visible: root.snapshotErrorActive
            enabled: !root.vpnController.snapshotRefreshPending
            onTriggered: root.requestSnapshotRefresh()
        }
    ]
}
