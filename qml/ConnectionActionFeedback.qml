// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.InlineMessage {
    id: root

    required property var controller
    property bool awaitingResult: false
    property double operationId: 0
    property string expectedState
    property string completedMessage
    readonly property bool messageActive: completedMessage.length > 0

    objectName: "connectionActionFeedback"
    visible: messageActive
    height: visible ? implicitHeight : 0
    type: Kirigami.MessageType.Warning
    text: completedMessage

    function clearCompletedMessage() {
        completedMessage = ""
    }

    function beginForOperation(id, state) {
        operationId = id
        expectedState = state
        awaitingResult = true
        clearCompletedMessage()
    }

    function reconcileSnapshot() {
        // State is presentation, not a receipt for this request. Only retire
        // local feedback when identity/availability is lost or a stronger
        // connection diagnostic takes over; a matching state proves no result.
        if (!controller.loggedIn || !controller.backendAvailable
                || !controller.ready || controller.state === "error"
                || controller.state === "unresponsive") {
            awaitingResult = false
            clearCompletedMessage()
        }
    }

    function completeOperation(id, targetState, acknowledged, resultMessage) {
        if (!awaitingResult || id !== operationId
                || targetState !== expectedState) {
            return
        }
        awaitingResult = false
        if (acknowledged
                || !controller.backendAvailable
                || !controller.ready
                || controller.state === "error"
                || controller.state === "unresponsive") {
            return
        }
        const displayMessage = resultMessage.trim()
        if (displayMessage.length === 0) {
            return
        }
        completedMessage = displayMessage
    }

    Connections {
        target: root.controller
        function onSnapshotChanged() {
            root.reconcileSnapshot()
        }
        function onConnectionOperationStarted(operationId, targetState) {
            root.beginForOperation(operationId, targetState)
        }
        function onConnectionOperationFinished(operationId, targetState,
                                               acknowledged, message) {
            root.completeOperation(operationId, targetState, acknowledged, message)
        }
    }
}
