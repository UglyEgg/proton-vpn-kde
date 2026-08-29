import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    title: qsTr("Connection")
    property bool portCopied: false
    property var splitSettings: vpnController.splitTunneling
    readonly property bool connected: vpnController.state === "connected"

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

        SectionCard {
            title: page.stateLabel(vpnController.state)
            description: page.connected
                         ? (vpnController.serverLocation.length > 0
                            ? vpnController.serverLocation : vpnController.serverName)
                         : vpnController.loggedIn
                           ? qsTr("Ready to protect this device")
                           : qsTr("Sign in to connect with your Proton account")
            iconName: page.connected ? "security-high" : "network-vpn"
            iconColor: page.stateColor(vpnController.state)

            Flow {
                Layout.fillWidth: true
                visible: page.connected && (vpnController.secureCore
                         || vpnController.tor || vpnController.p2p
                         || vpnController.streaming
                         || vpnController.smartRouting)
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Chip {
                    visible: vpnController.secureCore
                    text: qsTr("Secure Core")
                    icon.name: "security-high"
                    closable: false
                    interactive: false
                }
                Kirigami.Chip {
                    visible: vpnController.tor
                    text: qsTr("Tor")
                    icon.name: "security-medium"
                    closable: false
                    interactive: false
                }
                Kirigami.Chip {
                    visible: vpnController.p2p
                    text: qsTr("P2P")
                    icon.name: "folder-network"
                    closable: false
                    interactive: false
                }
                Kirigami.Chip {
                    visible: vpnController.streaming
                    text: qsTr("Streaming")
                    icon.name: "applications-multimedia"
                    closable: false
                    interactive: false
                }
                Kirigami.Chip {
                    visible: vpnController.smartRouting
                    text: qsTr("Smart Routing")
                    icon.name: "network-wired-activated"
                    closable: false
                    interactive: false
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Controls.BusyIndicator {
                    running: vpnController.busy
                    visible: running
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: implicitWidth
                }

                Item {
                    Layout.fillWidth: true
                }

                Controls.Button {
                    visible: vpnController.ready && !vpnController.loggedIn
                    text: qsTr("Sign in")
                    icon.name: "system-log-in"
                    highlighted: true
                    onClicked: applicationWindow().showSignIn()
                }

                Controls.Button {
                    visible: vpnController.loggedIn
                    text: vpnController.busy ? qsTr("Working…")
                                             : vpnController.primaryActionText
                    icon.name: page.connected
                               || vpnController.state === "connecting"
                               || vpnController.state === "error"
                               ? "network-disconnect" : "network-connect"
                    enabled: vpnController.primaryActionEnabled
                    highlighted: vpnController.state === "disconnected"
                    onClicked: vpnController.activatePrimaryAction()
                }
            }
        }

        SectionCard {
            visible: page.connected
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
        }

        SectionCard {
            title: qsTr("Server selection")
            description: vpnController.userTier === 0
                         ? qsTr("Proton chooses the fastest available free server automatically.")
                         : qsTr("Use the fastest available server or choose a country, city, or exact server.")
            iconName: "network-server"

            RowLayout {
                Layout.fillWidth: true

                Item {
                    Layout.fillWidth: true
                }

                Controls.Button {
                    text: qsTr("Browse servers")
                    icon.name: "network-server"
                    enabled: vpnController.loggedIn
                    onClicked: applicationWindow().showLocations()
                }
            }
        }
    }
}
