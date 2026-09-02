// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Column {
    id: root

    required property var controller
    required property string loadError

    spacing: loadErrorMessage.visible && connectionFeedback.visible
             ? Kirigami.Units.smallSpacing : 0
    height: childrenRect.height

    function beginForState(state) {
        connectionFeedback.beginForState(state)
    }

    Kirigami.InlineMessage {
        id: loadErrorMessage
        objectName: "serverBrowserLoadError"
        width: root.width
        visible: root.loadError.length > 0
        height: visible ? implicitHeight : 0
        type: Kirigami.MessageType.Error
        text: root.loadError
    }

    ConnectionActionFeedback {
        id: connectionFeedback
        width: root.width
        controller: root.controller
    }
}
