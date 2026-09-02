// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.InlineMessage {
    id: root

    required property var controller
    property bool awaitingResult: false
    property bool observedBusy: false
    property string expectedState
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
        awaitingResult = true
        observedBusy = controller.busy
        clearCompletedMessage()
    }

    function reconcileSnapshot() {
        if (messageActive
                && (controller.state === expectedState
                    || controller.message !== sourceMessage)) {
            clearCompletedMessage()
        }
        if (!awaitingResult) {
            return
        }
        if (controller.busy) {
            observedBusy = true
            return
        }
        if (!observedBusy) {
            return
        }
        if (controller.state === expectedState
                || controller.state === "error"
                || controller.state === "unresponsive") {
            awaitingResult = false
            return
        }
        const resultMessage = controller.message.trim()
        if (resultMessage.length === 0) {
            return
        }
        awaitingResult = false
        completedMessage = resultMessage
        sourceMessage = controller.message
    }

    Connections {
        target: root.controller
        function onSnapshotChanged() {
            root.reconcileSnapshot()
        }
    }
}
