// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.InlineMessage {
    id: root

    required property var vpnController
    readonly property bool recoveryActive:
        vpnController.state === "unresponsive"
        && vpnController.backendRestartAllowed

    objectName: "applicationBackendRecovery"
    visible: recoveryActive
    height: visible ? implicitHeight : 0
    type: Kirigami.MessageType.Error
    text: vpnController.message.length > 0
          ? vpnController.message
          : qsTr("The local Proton VPN service is not responding.")

    function requestRestart() {
        vpnController.restartBackend()
    }

    actions: [
        Kirigami.Action {
            objectName: "restartUnresponsiveBackendAction"
            text: qsTr("Restart service")
            icon.name: "view-refresh"
            onTriggered: root.requestRestart()
        }
    ]
}
