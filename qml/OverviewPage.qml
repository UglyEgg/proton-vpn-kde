// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    objectName: "overviewPage"
    title: qsTr("Connection")
    property bool portCopied: false
    property bool connectionDetailsExpanded: false
    property var splitSettings: vpnController.splitTunneling
    readonly property bool connected: vpnController.state === "connected"
    readonly property bool connectionDetailsVisible:
        connectionDetailsCard.visible
    readonly property bool graphicalRouteVisible: connectionScene.routeVisible
    readonly property bool homeNavigationVisible:
        connectionScene.homeNavigationVisible

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

    Timer {
        id: copiedTimer
        interval: 1500
        onTriggered: page.portCopied = false
    }

    ColumnLayout {
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
            visible: page.connected && page.splitSettings.loaded
                     && page.splitSettings.enabled
            type: Kirigami.MessageType.Information
            text: qsTr("Split tunneling enabled. Remember to restart affected apps.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnController.ready
                     && vpnController.coreVersion.length > 0
                     && !vpnController.coreMemoryOptimized
            type: Kirigami.MessageType.Warning
            text: qsTr("The verified server-list memory optimizations are not active for Proton Core %1. VPN functionality is unaffected, but memory use may be higher until the overlay is refreshed or Proton includes the fixes.").arg(vpnController.coreVersion)
        }

        ConnectionScene {
            id: connectionScene

            objectName: "connectionScene"
            Layout.fillWidth: true
            connectionState: vpnController.state
            stateText: page.connected ? qsTr("Protected")
                                      : page.stateLabel(vpnController.state)
            summaryText: page.connected
                         ? qsTr("Your traffic is using an encrypted VPN route")
                         : vpnController.loggedIn
                           ? qsTr("Connect to protect this device")
                           : qsTr("Sign in to connect with your Proton account")
            stateColor: page.stateColor(vpnController.state)
            connected: page.connected
            busy: vpnController.busy
            loggedIn: vpnController.loggedIn
            ready: vpnController.ready
            accountName: vpnController.accountName
            destinationFlag: page.countryFlag(vpnController.exitCountry)
            destinationName: vpnController.serverLocation.length > 0
                             ? vpnController.serverLocation
                             : vpnController.exitCountry
            serverName: vpnController.serverName
            primaryText: vpnController.busy ? qsTr("Working…")
                                            : vpnController.primaryActionText
            primaryIcon: page.connected
                         || vpnController.state === "connecting"
                         || vpnController.state === "error"
                         ? "network-disconnect" : "network-connect"
            primaryEnabled: vpnController.primaryActionEnabled
            secureCore: vpnController.secureCore
            tor: vpnController.tor
            p2p: vpnController.p2p
            streaming: vpnController.streaming
            smartRouting: vpnController.smartRouting
            onPrimaryActionRequested: vpnController.activatePrimaryAction()
            onSignInRequested: applicationWindow().showSignIn()
            onNavigateRequested: destination => {
                applicationWindow().openOverviewDestination(destination)
            }
        }

        Controls.Button {
            id: connectionDetailsToggle

            objectName: "connectionDetailsToggle"
            Layout.alignment: Qt.AlignLeft
            visible: page.connected
            checkable: true
            checked: page.connectionDetailsExpanded
            flat: true
            text: checked ? qsTr("Hide connection details")
                          : qsTr("Show connection details")
            icon.name: checked ? "go-up-symbolic" : "go-down-symbolic"
            Accessible.description: qsTr("Expand or collapse the current server and forwarded-port details")
            onToggled: page.connectionDetailsExpanded = checked
        }

        SectionCard {
            id: connectionDetailsCard

            objectName: "connectionDetailsCard"
            visible: page.connected && page.connectionDetailsExpanded
            title: qsTr("Connection details")
            iconName: "network-server"

            DetailRow {
                label: qsTr("Location")
                value: page.countryFlag(vpnController.exitCountry) + " "
                       + (vpnController.serverLocation.length > 0
                          ? vpnController.serverLocation
                          : vpnController.exitCountry)
                iconName: "mark-location"
            }

            DetailRow {
                label: vpnController.secureCore
                       && vpnController.entryCountry.length > 0
                       ? qsTr("Server and entry") : qsTr("Server")
                value: vpnController.secureCore
                       && vpnController.entryCountry.length > 0
                       ? qsTr("%1 via %2").arg(vpnController.serverName)
                             .arg(vpnController.entryCountry)
                       : vpnController.serverName
                iconName: "network-server-database"
            }

            RowLayout {
                Layout.fillWidth: true
                visible: vpnController.forwardedPort > 0
                spacing: Kirigami.Units.largeSpacing

                Controls.Label {
                    Layout.fillWidth: true
                    text: qsTr("Forwarded port")
                    color: Kirigami.Theme.disabledTextColor
                }
                Controls.Label {
                    text: vpnController.forwardedPort.toString()
                }
                Controls.ToolButton {
                    icon.name: page.portCopied ? "dialog-ok" : "edit-copy"
                    text: page.portCopied ? qsTr("Copied") : qsTr("Copy")
                    display: Controls.AbstractButton.IconOnly
                    onClicked: {
                        vpnController.copyForwardedPort()
                        page.portCopied = true
                        copiedTimer.restart()
                    }

                    Controls.ToolTip.visible: hovered || activeFocus
                    Controls.ToolTip.text: text
                }
            }

            RowLayout {
                Layout.fillWidth: true

                Item {
                    Layout.fillWidth: true
                }

                Controls.Button {
                    text: qsTr("Open Connection Inspector")
                    icon.name: "view-statistics"
                    flat: true
                    onClicked: applicationWindow().openOverviewDestination(
                        "inspector")
                }
            }
        }
    }
}
