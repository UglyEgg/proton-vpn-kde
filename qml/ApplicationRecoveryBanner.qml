// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.InlineMessage {
    id: root

    required property var vpnController
    required property var dialogErrorCodes
    readonly property bool recoveryActive:
        vpnController.loggedIn
        && vpnController.state === "unresponsive"
        && vpnController.backendRestartAllowed
    readonly property bool connectionErrorActive:
        vpnController.loggedIn
        && vpnController.state === "error"
        && !dialogErrorCodes.includes(vpnController.errorCode)
    readonly property bool statusMessageActive:
        vpnController.loggedIn
        && !vpnController.busy
        && vpnController.message.length > 0
        && vpnController.state !== "error"
        && vpnController.state !== "unresponsive"
    readonly property bool bannerActive:
        recoveryActive || connectionErrorActive || statusMessageActive

    objectName: "applicationBackendRecovery"
    visible: bannerActive
    height: visible ? implicitHeight : 0
    type: recoveryActive || connectionErrorActive
          ? Kirigami.MessageType.Error
          : Kirigami.MessageType.Information
    text: {
        if (root.recoveryActive) {
            return vpnController.message.length > 0
                   ? vpnController.message
                   : qsTr("The local Proton VPN service is not responding.")
        }
        if (root.connectionErrorActive) {
            const summary = root.connectionErrorText(vpnController.errorCode)
            return summary
                   + (vpnController.message.length > 0
                      ? "\n" + vpnController.message : "")
        }
        return vpnController.message
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

    actions: [
        Kirigami.Action {
            objectName: "restartUnresponsiveBackendAction"
            text: qsTr("Restart service")
            icon.name: "view-refresh"
            visible: root.recoveryActive
            onTriggered: root.requestRestart()
        }
    ]
}
