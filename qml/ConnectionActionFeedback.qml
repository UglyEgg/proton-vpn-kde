// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.InlineMessage {
    id: root

    required property var controller
    property bool awaitingResult: false
    property string expectedState
    property string startingState
    property string completedMessage
    property string sourceMessage
    readonly property bool messageActive: completedMessage.length > 0

    objectName: "connectionActionFeedback"
    visible: messageActive
    height: visible ? implicitHeight : 0
    type: Kirigami.MessageType.Warning
    text: completedMessage

    function clearCompletedMessage() {
        completedMessage = ""
        sourceMessage = ""
    }

    function beginForState(state) {
        expectedState = state
        startingState = controller.state
        awaitingResult = true
        clearCompletedMessage()
    }

    function expectedStateReached() {
        return controller.state === expectedState
               && startingState !== expectedState
    }

    function reconcileSnapshot() {
        if (messageActive
                && (expectedStateReached()
                    || controller.state === "error"
                    || controller.state === "unresponsive"
                    || controller.message !== sourceMessage)) {
            clearCompletedMessage()
        }
        if (!awaitingResult) {
            return
        }
        if (expectedStateReached()
                || !controller.backendAvailable
                || !controller.ready
                || ((controller.state === "error"
                     || controller.state === "unresponsive")
                    && controller.state !== startingState)) {
            awaitingResult = false
        }
    }

    function completeOperation(targetState, success, resultMessage) {
        if (!awaitingResult || targetState !== expectedState) {
            return
        }
        awaitingResult = false
        if (success
                || expectedStateReached()
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
        sourceMessage = controller.message
    }

    Connections {
        target: root.controller
        function onSnapshotChanged() {
            root.reconcileSnapshot()
        }
        function onConnectionOperationFinished(targetState, success, message) {
            root.completeOperation(targetState, success, message)
        }
    }
}
