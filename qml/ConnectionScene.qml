// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.AbstractCard {
    id: root

    property string connectionState
    property string stateText
    property string summaryText
    property color stateColor: Kirigami.Theme.neutralTextColor
    property bool connected: false
    property bool busy: false
    property bool loggedIn: false
    property bool ready: false
    property string accountName
    property string destinationFlag
    property string destinationName
    property string serverName
    property string primaryText
    property string primaryIcon
    property bool primaryEnabled: false
    property bool secureCore: false
    property bool tor: false
    property bool p2p: false
    property bool streaming: false
    property bool smartRouting: false
    readonly property bool routeVisible: routeDiagram.visible
    readonly property bool homeNavigationVisible:
        deviceNode.visible && destinationNode.visible
        && moreAction.visible
        && (!root.loggedIn || accountAction.visible)

    signal primaryActionRequested()
    signal signInRequested()
    signal navigateRequested(string destination)

    Accessible.name: qsTr("VPN connection status: %1").arg(root.stateText)

    component RouteNode: Controls.Button {
        id: node

        property string iconName
        property string symbol
        property string heading
        property string detail
        property color accentColor: Kirigami.Theme.textColor

        flat: true
        Layout.preferredWidth: Kirigami.Units.gridUnit * 8
        Layout.maximumWidth: Kirigami.Units.gridUnit * 11
        Accessible.name: node.heading
        Accessible.description: node.detail

        contentItem: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: Kirigami.Units.iconSizes.huge
                implicitHeight: implicitWidth
                radius: width / 2
                color: Kirigami.Theme.backgroundColor
                border.width: 2
                border.color: node.accentColor

                Kirigami.Icon {
                    anchors.centerIn: parent
                    visible: node.symbol.length === 0
                    source: node.iconName
                    color: node.accentColor
                    implicitWidth: Kirigami.Units.iconSizes.large
                    implicitHeight: implicitWidth
                }

                Controls.Label {
                    anchors.centerIn: parent
                    visible: node.symbol.length > 0
                    text: node.symbol
                    color: node.accentColor
                    font.bold: true
                    Accessible.ignored: true
                }
            }

            Kirigami.Heading {
                Layout.fillWidth: true
                level: 4
                text: node.heading
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }

            Controls.Label {
                Layout.fillWidth: true
                text: node.detail
                color: Kirigami.Theme.linkColor
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
            }
        }
    }

    component CapabilityChip: Kirigami.Chip {
        closable: false
        interactive: false
    }

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        RowLayout {
            Layout.fillWidth: true

            Item { Layout.fillWidth: true }

            Controls.ToolButton {
                id: moreAction

                text: qsTr("More options")
                icon.name: "configure"
                display: Controls.AbstractButton.IconOnly
                onClicked: moreMenu.open()

                contentItem: Kirigami.Icon {
                    source: "configure"
                    color: Kirigami.Theme.textColor
                    implicitWidth: Kirigami.Units.iconSizes.smallMedium
                    implicitHeight: implicitWidth
                }

                Controls.ToolTip.visible: hovered || activeFocus
                Controls.ToolTip.text: moreAction.text

                Controls.Menu {
                    id: moreMenu

                    y: moreAction.height

                    Controls.MenuItem {
                        text: qsTr("Connection Inspector")
                        icon.name: "view-statistics"
                        enabled: root.loggedIn
                        onTriggered: root.navigateRequested("inspector")
                    }

                    Controls.MenuSeparator { }

                    Controls.MenuItem {
                        text: qsTr("Release notes")
                        icon.name: "view-pim-notes"
                        onTriggered: root.navigateRequested("release-notes")
                    }

                    Controls.MenuItem {
                        text: qsTr("Report an issue")
                        icon.name: "tools-report-bug"
                        enabled: root.loggedIn
                        onTriggered: root.navigateRequested("report-issue")
                    }

                    Controls.MenuItem {
                        text: qsTr("About")
                        icon.name: "help-about"
                        onTriggered: root.navigateRequested("about")
                    }

                    Controls.MenuSeparator { }

                    Controls.MenuItem {
                        text: qsTr("Close Control Center")
                        icon.name: "application-exit"
                        onTriggered: root.navigateRequested("close")
                    }
                }
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: Kirigami.Units.gridUnit * 6

            Rectangle {
                anchors.centerIn: parent
                width: Kirigami.Units.gridUnit * 5
                height: width
                radius: width / 2
                color: Kirigami.Theme.backgroundColor
                border.width: 2
                border.color: root.stateColor

                Rectangle {
                    anchors.centerIn: parent
                    width: parent.width - Kirigami.Units.largeSpacing
                    height: width
                    radius: width / 2
                    color: Kirigami.Theme.alternateBackgroundColor
                }

                Image {
                    anchors.centerIn: parent
                    visible: !root.busy
                    source: "qrc:/data/plasma-vpn.svg"
                    width: Kirigami.Units.iconSizes.huge
                    height: width
                    sourceSize.width: width
                    sourceSize.height: height
                }

                Controls.BusyIndicator {
                    anchors.centerIn: parent
                    visible: root.busy
                    running: visible
                    implicitWidth: Kirigami.Units.iconSizes.huge
                    implicitHeight: implicitWidth
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            Kirigami.Heading {
                Layout.fillWidth: true
                level: 1
                text: root.stateText
                color: root.stateColor
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            Controls.Label {
                Layout.fillWidth: true
                text: root.summaryText
                color: Kirigami.Theme.disabledTextColor
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }

        RowLayout {
            id: routeDiagram

            objectName: "connectionRouteDiagram"
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 32
            Layout.alignment: Qt.AlignHCenter
            spacing: Kirigami.Units.smallSpacing
            Accessible.name: root.connected
                ? qsTr("Encrypted route from this device to %1").arg(root.destinationName)
                : qsTr("VPN route is inactive")

            RouteNode {
                id: deviceNode

                symbol: qsTr("You")
                heading: qsTr("This device")
                detail: qsTr("Protection settings")
                accentColor: root.connected
                    ? Kirigami.Theme.positiveTextColor
                    : Kirigami.Theme.disabledTextColor
                onClicked: root.navigateRequested("settings")
            }

            Item {
                Layout.fillWidth: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 5
                Layout.preferredHeight: Kirigami.Units.gridUnit * 5

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    height: 2
                    color: root.connected
                        ? Kirigami.Theme.positiveTextColor
                        : Kirigami.Theme.disabledTextColor
                }

                Rectangle {
                    id: tunnelStateBadge

                    anchors.centerIn: parent
                    width: Kirigami.Units.iconSizes.medium
                           + Kirigami.Units.largeSpacing
                    height: width
                    radius: width / 2
                    color: Kirigami.Theme.backgroundColor
                    border.width: 1
                    border.color: root.connected
                        ? Kirigami.Theme.positiveTextColor
                        : Kirigami.Theme.disabledTextColor

                    Rectangle {
                        anchors.centerIn: parent
                        width: Kirigami.Units.smallSpacing
                        height: width
                        radius: width / 2
                        color: root.connected
                            ? Kirigami.Theme.positiveTextColor
                            : Kirigami.Theme.disabledTextColor
                        Accessible.ignored: true
                    }
                }

                Controls.Label {
                    anchors.horizontalCenter: parent.horizontalCenter
                    anchors.top: tunnelStateBadge.bottom
                    anchors.topMargin: Kirigami.Units.smallSpacing
                    text: root.connected ? qsTr("Encrypted tunnel")
                                         : qsTr("VPN inactive")
                    color: Kirigami.Theme.disabledTextColor
                }
            }

            RouteNode {
                id: destinationNode

                symbol: root.connected ? root.destinationFlag : qsTr("VPN")
                heading: root.connected ? root.destinationName
                                        : qsTr("VPN server")
                detail: qsTr("Browse servers")
                enabled: root.loggedIn
                accentColor: root.connected
                    ? Kirigami.Theme.positiveTextColor
                    : Kirigami.Theme.disabledTextColor
                onClicked: root.navigateRequested("locations")
            }
        }

        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: capabilityFlow.visible
                                    ? capabilityFlow.childrenRect.height : 0
            visible: root.connected && (root.secureCore || root.tor || root.p2p
                     || root.streaming || root.smartRouting)

            Flow {
                id: capabilityFlow

                anchors.horizontalCenter: parent.horizontalCenter
                width: Math.min(parent.width, childrenRect.width)
                spacing: Kirigami.Units.smallSpacing

                CapabilityChip {
                    visible: root.secureCore
                    text: qsTr("Secure Core")
                    icon.name: "security-high"
                }
                CapabilityChip {
                    visible: root.tor
                    text: qsTr("Tor")
                    icon.name: "security-medium"
                }
                CapabilityChip {
                    visible: root.p2p
                    text: qsTr("P2P")
                    icon.name: "folder-network"
                }
                CapabilityChip {
                    visible: root.streaming
                    text: qsTr("Streaming")
                    icon.name: "applications-multimedia"
                }
                CapabilityChip {
                    visible: root.smartRouting
                    text: qsTr("Smart Routing")
                    icon.name: "network-wired-activated"
                }
            }
        }

        ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: Kirigami.Units.smallSpacing

            Controls.Button {
                objectName: "primaryConnectionAction"
                Layout.alignment: Qt.AlignHCenter
                Layout.minimumWidth: Kirigami.Units.gridUnit * 12
                visible: root.loggedIn
                text: root.primaryText
                icon.name: root.primaryIcon
                enabled: root.primaryEnabled
                highlighted: root.connectionState === "disconnected"
                onClicked: root.primaryActionRequested()
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                visible: root.ready && !root.loggedIn
                text: qsTr("Sign in")
                icon.name: "system-log-in"
                highlighted: true
                onClicked: root.signInRequested()
            }

            Controls.Button {
                id: accountAction

                Layout.alignment: Qt.AlignHCenter
                visible: root.loggedIn
                text: root.accountName.length > 0
                      ? root.accountName : qsTr("Account")
                icon.name: "user-identity"
                flat: true
                onClicked: root.navigateRequested("account")
            }
        }
    }
}
