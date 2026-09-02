// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    title: qsTr("Connection Inspector")
    property var vpnSettings: vpnController.settings
    property var splitSettings: vpnController.splitTunneling
    property var dnsSettings: vpnController.customDns
    readonly property bool connected: vpnController.state === "connected"

    function ensureInspectorModels() {
        if (!vpnController.ready || !vpnController.loggedIn) {
            return
        }
        if (!page.vpnSettings.loaded && !page.vpnSettings.busy) {
            vpnController.loadSettings()
        }
        if (!page.splitSettings.loaded && !page.splitSettings.busy) {
            vpnController.loadSplitTunneling()
        }
        if (!page.dnsSettings.loaded && !page.dnsSettings.busy) {
            vpnController.loadCustomDns()
        }
    }

    function refreshInspector() {
        if (!vpnController.ready || !vpnController.loggedIn) {
            return
        }
        vpnController.refresh()
        if (!page.vpnSettings.busy) {
            vpnController.loadSettings()
        }
        if (!page.splitSettings.busy) {
            vpnController.loadSplitTunneling()
        }
        if (!page.dnsSettings.busy) {
            vpnController.loadCustomDns()
        }
    }

    function stateLabel(state) {
        const labels = {
            "connected": qsTr("Connected"),
            "connecting": qsTr("Connecting"),
            "disconnecting": qsTr("Disconnecting"),
            "disconnected": qsTr("Disconnected"),
            "error": qsTr("Connection error"),
            "starting": qsTr("Starting"),
            "unavailable": qsTr("Unavailable")
        }
        return labels[state] ?? state
    }

    function enabledLabel(enabled) {
        return enabled ? qsTr("Enabled") : qsTr("Disabled")
    }

    function modelValue(model, loadedValue) {
        if (model.loaded) {
            return loadedValue
        }
        if (model.busy) {
            return qsTr("Loading…")
        }
        return model.message.length > 0 ? model.message : qsTr("Unavailable")
    }

    function protocolLabel() {
        for (let index = 0;
             index < page.vpnSettings.protocolOptions.length; ++index) {
            const protocol = page.vpnSettings.protocolOptions[index]
            if (protocol.id === page.vpnSettings.protocol) {
                return protocol.name
            }
        }
        return page.vpnSettings.protocol.length > 0
               ? page.vpnSettings.protocol : qsTr("Unavailable")
    }

    function killSwitchLabel(mode) {
        return [qsTr("Off"), qsTr("Standard"), qsTr("Permanent")][mode]
               ?? qsTr("Unavailable")
    }

    function netShieldLabel(mode) {
        return [
            qsTr("Off"),
            qsTr("Block malware"),
            qsTr("Block ads, trackers, and malware")
        ][mode] ?? qsTr("Unavailable")
    }

    function dnsLabel() {
        if (!page.dnsSettings.loaded) {
            return qsTr("Unavailable")
        }
        if (!page.dnsSettings.enabled) {
            return qsTr("Default VPN DNS")
        }
        return qsTr("Custom · %n server(s)", "", page.dnsSettings.serverCount)
    }

    function splitTunnelingLabel() {
        if (!page.splitSettings.loaded) {
            return qsTr("Unavailable")
        }
        if (!page.splitSettings.enabled) {
            return qsTr("Disabled")
        }
        const mode = page.splitSettings.mode === "include"
                     ? qsTr("Include") : qsTr("Exclude")
        return qsTr("%1 · %2 app(s) · %n IP rule(s)",
                    "", page.splitSettings.selectedIpRangeCount)
               .arg(mode)
               .arg(page.splitSettings.selectedAppPaths.length)
    }

    Component.onCompleted: page.ensureInspectorModels()

    Connections {
        target: vpnController

        function onSnapshotChanged() {
            if (vpnController.ready && vpnController.loggedIn) {
                Qt.callLater(page.ensureInspectorModels)
            }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        PageHeader {
            heading: qsTr("Connection Inspector")
            description: qsTr("Live, read-only details from the current Proton Core session")
            iconName: "view-statistics"
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !page.connected
            type: Kirigami.MessageType.Information
            text: qsTr("Connect the VPN to inspect the selected server and active capabilities. Protection and runtime information remain available while disconnected.")
        }

        SectionCard {
            title: qsTr("Connection")
            description: page.connected
                         ? qsTr("Current tunnel and selected Proton server")
                         : qsTr("No VPN tunnel is currently active")
            iconName: page.connected ? "security-high" : "network-vpn"
            iconColor: page.connected
                       ? Kirigami.Theme.positiveTextColor
                       : Kirigami.Theme.neutralTextColor

            DetailRow {
                label: qsTr("State")
                value: page.stateLabel(vpnController.state)
            }

            DetailRow {
                visible: page.connected
                label: qsTr("Server")
                value: vpnController.serverName
                iconName: "network-server-database"
            }

            DetailRow {
                visible: page.connected
                label: qsTr("Exit location")
                value: vpnController.serverLocation.length > 0
                       ? vpnController.serverLocation
                       : vpnController.exitCountry
                iconName: "mark-location"
            }

            DetailRow {
                visible: page.connected && vpnController.secureCore
                         && vpnController.entryCountry.length > 0
                label: qsTr("Secure Core entry")
                value: vpnController.entryCountry
                iconName: "security-high"
            }

            DetailRow {
                label: qsTr("Protocol")
                value: page.modelValue(page.vpnSettings, page.protocolLabel())
            }

            DetailRow {
                visible: page.connected && vpnController.forwardedPort > 0
                label: qsTr("Forwarded port")
                value: vpnController.forwardedPort.toString()
            }

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
        }

        SectionCard {
            title: qsTr("Protection")
            description: qsTr("Effective client configuration reported by Proton Core")
            iconName: "security-high"

            DetailRow {
                label: qsTr("Kill switch")
                value: page.modelValue(
                    page.vpnSettings,
                    page.killSwitchLabel(page.vpnSettings.killSwitch))
            }

            DetailRow {
                label: qsTr("NetShield")
                value: page.modelValue(
                    page.vpnSettings,
                    page.netShieldLabel(page.vpnSettings.netShield))
            }

            DetailRow {
                label: qsTr("IPv6 tunnel")
                value: page.modelValue(
                    page.vpnSettings,
                    page.enabledLabel(page.vpnSettings.ipv6))
            }

            DetailRow {
                label: qsTr("VPN Accelerator")
                value: page.modelValue(
                    page.vpnSettings,
                    page.enabledLabel(page.vpnSettings.vpnAccelerator))
            }

            DetailRow {
                label: qsTr("NAT mode")
                value: page.modelValue(
                    page.vpnSettings,
                    page.vpnSettings.moderateNat
                        ? qsTr("Moderate") : qsTr("Strict"))
            }

            DetailRow {
                label: qsTr("DNS")
                value: page.modelValue(page.dnsSettings, page.dnsLabel())
            }

            DetailRow {
                label: qsTr("Split tunneling")
                value: page.modelValue(
                    page.splitSettings, page.splitTunnelingLabel())
            }

            DetailRow {
                label: qsTr("Drop recovery")
                value: page.enabledLabel(appSettings.reconnectEnabled)
            }
        }

        SectionCard {
            title: qsTr("Runtime")
            description: qsTr("Local client and official Core integration status")
            iconName: "utilities-system-monitor"

            DetailRow {
                label: qsTr("Control Center")
                value: qsTr("Version %1").arg(appVersion)
            }

            DetailRow {
                label: qsTr("Backend service")
                value: vpnController.backendAvailable
                       ? qsTr("Available") : qsTr("Unavailable")
            }

            DetailRow {
                label: qsTr("Proton Core")
                value: vpnController.coreVersion.length > 0
                       ? vpnController.coreVersion : qsTr("Unavailable")
            }

            DetailRow {
                label: qsTr("Core memory overlay")
                value: vpnController.coreMemoryOptimized
                       ? qsTr("Active") : qsTr("Not detected")
            }

            DetailRow {
                label: qsTr("Packet capture")
                value: vpnController.packetCaptureActive
                       ? qsTr("Active") : qsTr("Inactive")
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    text: qsTr("Refresh")
                    icon.name: "view-refresh"
                    enabled: vpnController.ready
                             && !vpnController.busy
                             && !vpnController.snapshotRefreshPending
                    onClicked: page.refreshInspector()
                }
            }
        }

        SectionCard {
            title: qsTr("Privacy boundary")
            iconName: "preferences-desktop-privacy"

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("The Inspector has no timer or background collector. It renders bounded state already exposed to the Control Center and requests fresh snapshots only while this page is open. It does not inspect traffic, retain connection history, contact remote telemetry, or move networking behavior out of Proton Core.")
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    text: qsTr("Diagnostics settings")
                    icon.name: "settings-configure"
                    onClicked: applicationWindow().openOverviewDestination(
                        "settings")
                }
            }
        }
    }
}
