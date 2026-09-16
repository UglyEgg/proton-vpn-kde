// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Local setup")
    readonly property real maximumContentWidth: Kirigami.Units.gridUnit * 30
    leftPadding: Math.max(Kirigami.Units.largeSpacing,
                          (width - maximumContentWidth) / 2)
    rightPadding: leftPadding

    function secretServiceLabel() {
        switch (desktopReadiness.secretServiceState) {
        case "running": return qsTr("Provider is running")
        case "activatable": return qsTr("Provider can start on demand")
        case "missing": return qsTr("No provider advertised")
        case "checking": return qsTr("Checking…")
        default: return qsTr("Could not check")
        }
    }

    function packageLabel(state) {
        switch (state) {
        case "present": return qsTr("Capability found")
        case "missing": return qsTr("Capability missing")
        case "checking": return qsTr("Checking…")
        default: return qsTr("Could not check")
        }
    }

    Component.onCompleted: desktopReadiness.refresh()

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        PageHeader {
            heading: qsTr("Local setup")
            description: qsTr("Read-only checks before or after sign-in")
            iconName: "view-list-details"
        }

        SectionCard {
            title: qsTr("Client and Proton Core")
            iconName: "applications-system"

            DetailRow {
                label: qsTr("Backend service")
                value: vpnController.ready ? qsTr("Ready")
                       : !vpnController.snapshotHealthy
                         || vpnController.state === "error"
                         || !vpnController.backendRestartAllowed
                         ? qsTr("Needs attention")
                         : qsTr("Starting or waiting for account storage")
            }

            DetailRow {
                label: qsTr("Proton Core")
                value: vpnController.coreVersion.length > 0
                       ? vpnController.coreVersion : qsTr("Not reported yet")
            }

            DetailRow {
                label: qsTr("Core startup check")
                value: !vpnController.ready ? qsTr("Not complete")
                       : vpnController.startupCompatible
                         ? qsTr("Compatible") : qsTr("Needs attention")
            }

            DetailRow {
                label: qsTr("Core package")
                value: page.packageLabel(desktopReadiness.coreCapabilityState)
            }

            DetailRow {
                label: qsTr("Keyring package")
                value: page.packageLabel(desktopReadiness.keyringCapabilityState)
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: desktopReadiness.coreCapabilityState === "missing"
                         || desktopReadiness.keyringCapabilityState === "missing"
                type: Kirigami.MessageType.Warning
                text: qsTr("A required Plasma VPN overlay capability was not found. Install the matching Core and keyring packages through your distribution's package manager before signing in.")
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: (!vpnController.snapshotHealthy
                          || vpnController.state === "error"
                          || (vpnController.ready
                              && !vpnController.startupCompatible))
                         && vpnController.message.length > 0
                type: Kirigami.MessageType.Warning
                text: vpnController.message
            }
        }

        SectionCard {
            title: qsTr("Desktop Secret Service")
            iconName: "dialog-password"

            DetailRow {
                label: qsTr("Availability")
                value: page.secretServiceLabel()
            }

            Kirigami.InlineMessage {
                objectName: "secretServiceMissingMessage"
                Layout.fillWidth: true
                visible: desktopReadiness.secretServiceState === "missing"
                type: Kirigami.MessageType.Warning
                text: qsTr("Start or configure a Freedesktop Secret Service provider, then refresh this check. KeePassXC, KWallet, and other providers can be used when configured to offer this interface.")
            }

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("The Secret Service check only asks the session bus whether a provider is running or can be started. It does not open, unlock, or test a collection. A provider may still request your approval during normal sign-in.")
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    objectName: "readinessRefreshButton"
                    text: qsTr("Refresh checks")
                    icon.name: "view-refresh"
                    enabled: desktopReadiness.secretServiceState !== "checking"
                    onClicked: desktopReadiness.refresh()
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Controls.Button {
                text: qsTr("Compatibility guide")
                icon.name: "help-contents"
                onClicked: Qt.openUrlExternally(
                    "https://github.com/UglyEgg/proton-vpn-kde/blob/main/docs/COMPATIBILITY.md")
            }
            Item { Layout.fillWidth: true }
            Controls.Button {
                text: vpnController.loggedIn ? qsTr("Back to connection")
                                             : qsTr("Back to sign-in")
                onClicked: vpnController.loggedIn
                           ? applicationWindow().showOverview()
                           : applicationWindow().showSignIn()
            }
        }
    }
}
