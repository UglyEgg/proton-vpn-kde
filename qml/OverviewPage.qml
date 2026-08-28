import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: page
    title: qsTr("Connection")
    property bool portCopied: false
    property var splitSettings: vpnController.splitTunneling

    Component.onCompleted: {
        if (vpnController.loggedIn && !splitSettings.loaded) {
            vpnController.loadSplitTunneling()
        }
    }

    function countryFlag(code) {
        let upper = code.toUpperCase()
        if (upper === "UK") {
            upper = "GB"
        }
        if (upper.length !== 2) {
            return ""
        }
        return String.fromCodePoint(
            0x1F1E6 + upper.charCodeAt(0) - 65,
            0x1F1E6 + upper.charCodeAt(1) - 65)
    }

    Timer {
        id: copiedTimer
        interval: 1500
        onTriggered: page.portCopied = false
    }

    function stateLabel(state) {
        const labels = {
            "connected": qsTr("Connected"),
            "connecting": qsTr("Connecting…"),
            "disconnecting": qsTr("Disconnecting…"),
            "disconnected": qsTr("Not connected"),
            "error": qsTr("Connection error"),
            "starting": qsTr("Starting backend…"),
            "unavailable": qsTr("Backend unavailable")
        }
        return labels[state] ?? state
    }

    function stateColor(state) {
        if (state === "connected") {
            return Kirigami.Theme.positiveTextColor
        }
        if (state === "error" || state === "unavailable") {
            return Kirigami.Theme.negativeTextColor
        }
        return Kirigami.Theme.neutralTextColor
    }

    function connectionErrorText(code) {
        const messages = {
            "tunnel_setup_failed": qsTr("Tunnel setup failed"),
            "authentication_denied": qsTr("Authentication denied"),
            "timeout": qsTr("The connection attempt timed out"),
            "device_disconnected": qsTr("The VPN device disconnected"),
            "maximum_sessions_reached": qsTr("Session limit reached"),
            "certificate_expired": qsTr("Refreshing the VPN certificate…"),
            "certificate_not_yet_valid": qsTr("Your system clock appears to be out of sync. Update the system time and try again."),
            "two_factor_required": qsTr("Additional account authentication is required"),
            "unexpected_error": qsTr("An unexpected connection error occurred")
        }
        return messages[code] ?? ""
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !vpnController.backendAvailable
                     || vpnController.message.length > 0
                     || vpnController.errorCode.length > 0
            type: vpnController.state === "error"
                  ? Kirigami.MessageType.Error
                  : Kirigami.MessageType.Information
            text: vpnController.errorCode.length > 0
                  ? page.connectionErrorText(vpnController.errorCode)
                    + (vpnController.message.length > 0
                       ? "\n" + vpnController.message : "")
                  : vpnController.message.length > 0
                    ? vpnController.message
                    : qsTr("Start the backend service to manage Proton VPN")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnController.state === "connected"
                     && page.splitSettings.loaded
                     && page.splitSettings.enabled
            type: Kirigami.MessageType.Information
            text: qsTr("Split tunneling enabled. Remember to restart affected apps.")
        }

        Item { Layout.fillHeight: true }

        Kirigami.Icon {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: Kirigami.Units.gridUnit * 7
            implicitHeight: implicitWidth
            source: vpnController.state === "connected"
                    ? "security-high"
                    : "network-vpn"
            color: page.stateColor(vpnController.state)
        }

        Kirigami.Heading {
            Layout.alignment: Qt.AlignHCenter
            level: 1
            text: page.stateLabel(vpnController.state)
            color: page.stateColor(vpnController.state)
        }

        Controls.Label {
            Layout.alignment: Qt.AlignHCenter
            visible: vpnController.serverName.length > 0
            text: vpnController.serverName
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.15
        }

        Controls.Label {
            Layout.alignment: Qt.AlignHCenter
            visible: vpnController.ready && !vpnController.loggedIn
            text: qsTr("Sign in to connect with your Proton account")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.Button {
            Layout.alignment: Qt.AlignHCenter
            visible: vpnController.ready && !vpnController.loggedIn
            text: qsTr("Sign in")
            icon.name: "system-log-in"
            highlighted: true
            onClicked: applicationWindow().showPage(
                Qt.resolvedUrl("SignInPage.qml"))
        }

        Controls.Button {
            Layout.alignment: Qt.AlignHCenter
            Layout.minimumWidth: Kirigami.Units.gridUnit * 12
            text: vpnController.busy ? qsTr("Working…")
                                     : vpnController.primaryActionText
            icon.name: vpnController.state === "connected"
                       || vpnController.state === "connecting"
                       || vpnController.state === "error"
                       ? "network-disconnect"
                       : "network-connect"
            enabled: vpnController.primaryActionEnabled
            highlighted: vpnController.state === "disconnected"
            onClicked: vpnController.activatePrimaryAction()
        }

        Controls.BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            running: vpnController.busy
            visible: running
        }

        Item { Layout.fillHeight: true }

        Kirigami.Card {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing

                Controls.Label {
                    text: vpnController.state === "connected"
                          ? qsTr("Connection details")
                          : qsTr("Server selection")
                    font.bold: true
                }
                RowLayout {
                    visible: vpnController.state === "connected"
                    spacing: Kirigami.Units.smallSpacing

                    Controls.Label {
                        text: page.countryFlag(vpnController.exitCountry)
                        font.pixelSize: Kirigami.Units.gridUnit * 1.4
                    }
                    ColumnLayout {
                        spacing: 0
                        Controls.Label {
                            text: vpnController.serverLocation.length > 0
                                  ? vpnController.serverLocation
                                  : vpnController.exitCountry
                            font.bold: true
                        }
                        Controls.Label {
                            text: vpnController.secureCore
                                  && vpnController.entryCountry.length > 0
                                  ? qsTr("%1 · Via %2")
                                        .arg(vpnController.serverName)
                                        .arg(vpnController.entryCountry)
                                  : vpnController.serverName
                            color: Kirigami.Theme.disabledTextColor
                        }
                    }
                }
                RowLayout {
                    visible: vpnController.state === "connected"
                             && (vpnController.secureCore
                                 || vpnController.tor
                                 || vpnController.p2p
                                 || vpnController.streaming
                                 || vpnController.smartRouting)
                    Controls.Label {
                        visible: vpnController.secureCore
                        text: qsTr("Secure Core")
                        color: Kirigami.Theme.positiveTextColor
                    }
                    Controls.Label {
                        visible: vpnController.tor
                        text: qsTr("Tor")
                        color: Kirigami.Theme.neutralTextColor
                    }
                    Controls.Label {
                        visible: vpnController.p2p
                        text: qsTr("P2P")
                        color: Kirigami.Theme.positiveTextColor
                    }
                    Controls.Label {
                        visible: vpnController.streaming
                        text: qsTr("Streaming")
                        color: Kirigami.Theme.linkColor
                    }
                    Controls.Label {
                        visible: vpnController.smartRouting
                        text: qsTr("Smart Routing")
                        color: Kirigami.Theme.linkColor
                    }
                }
                RowLayout {
                    visible: vpnController.state === "connected"
                             && vpnController.forwardedPort > 0
                    Controls.Label {
                        text: qsTr("Active forwarded port: %1").arg(
                            vpnController.forwardedPort)
                    }
                    Controls.Button {
                        flat: true
                        icon.name: page.portCopied ? "dialog-ok" : "edit-copy"
                        text: page.portCopied ? qsTr("Copied") : qsTr("Copy")
                        onClicked: {
                            vpnController.copyForwardedPort()
                            page.portCopied = true
                            copiedTimer.restart()
                        }
                    }
                }
                Controls.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    visible: vpnController.state !== "connected"
                    text: vpnController.userTier === 0
                          ? qsTr("The fastest free server is selected automatically from available free locations.")
                          : qsTr("Choose the fastest available server, or browse countries and locations.")
                    color: Kirigami.Theme.disabledTextColor
                }
                Controls.Button {
                    Layout.alignment: Qt.AlignRight
                    text: qsTr("Browse servers")
                    icon.name: "network-server"
                    enabled: vpnController.loggedIn
                    onClicked: {
                        applicationWindow().pageStack.clear()
                        applicationWindow().pageStack.push(
                            Qt.resolvedUrl("LocationsPage.qml"))
                    }
                }
            }
        }
    }
}
