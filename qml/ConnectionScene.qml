// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Shapes
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
    property string entryCountry
    property string protocolName
    property int forwardedPort: 0
    property bool portCopied: false
    property string primaryText
    property string primaryIcon
    property bool primaryEnabled: false
    property bool secureCore: false
    property bool tor: false
    property bool p2p: false
    property bool streaming: false
    property bool smartRouting: false
    property bool splitTunneling: false
    readonly property bool splitRouteVisible: root.connected && root.splitTunneling
    readonly property bool routeVisible: routeDiagram.visible
    readonly property bool connectionFactsVisible: connectionFacts.visible
    readonly property bool homeNavigationVisible:
        deviceNode.visible && destinationNode.visible
        && moreAction.visible
        && (!root.loggedIn || accountAction.visible)

    signal primaryActionRequested()
    signal signInRequested()
    signal navigateRequested(string destination)
    signal copyPortRequested()

    Accessible.name: qsTr("VPN connection status: %1").arg(root.stateText)

    component RouteNode: Controls.Button {
        id: node

        property bool cloudSymbol: false
        property string symbol
        property string heading
        property string detail
        property color accentColor: Kirigami.Theme.textColor
        readonly property real routeCenterY:
            contentItem.y + nodeSymbol.y + nodeSymbol.height / 2
        readonly property real routeRadius: nodeSymbol.width / 2

        flat: true
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        Layout.minimumWidth: 0
        Accessible.name: node.heading
        Accessible.description: node.detail
        Controls.ToolTip.visible: hovered || activeFocus
        Controls.ToolTip.text: node.detail

        contentItem: ColumnLayout {
            spacing: Kirigami.Units.smallSpacing

            Rectangle {
                id: nodeSymbol
                Layout.alignment: Qt.AlignHCenter
                implicitWidth: Kirigami.Units.iconSizes.huge
                implicitHeight: implicitWidth
                radius: width / 2
                color: Kirigami.Theme.backgroundColor
                border.width: 2
                border.color: node.accentColor

                Shape {
                    anchors.centerIn: parent
                    visible: node.cloudSymbol
                    preferredRendererType: Shape.CurveRenderer
                    // Logical vector coordinates; scale with native icon sizes.
                    width: 32
                    height: 32
                    scale: Kirigami.Units.iconSizes.large / width
                    Accessible.ignored: true
                    ShapePath {
                        strokeWidth: 2
                        strokeColor: node.accentColor
                        fillColor: "transparent"
                        PathSvg {
                            path: "M9 25h15a6 6 0 0 0 1-11.9 9 9 0 0 0-17.3-1.8A7 7 0 0 0 9 25Z"
                        }
                    }
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
                wrapMode: Text.WordWrap
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
        width: Math.min(implicitWidth, parent.width)
        closable: false
        interactive: true
        Accessible.description: qsTr("Open connection inspector")
        Controls.ToolTip.visible: hovered || activeFocus
        Controls.ToolTip.text: qsTr("%1 · Open connection inspector").arg(text)
        onClicked: root.navigateRequested("inspector")
    }

    component ConnectionFact: Kirigami.Chip {
        width: Math.min(implicitWidth, parent.width)
        closable: false
        interactive: true
    }

    Controls.ToolButton {
        id: moreAction

        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: Kirigami.Units.largeSpacing
        z: 1
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
                text: qsTr("Help & information")
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

    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

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
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }
        }

        GridLayout {
            id: routeDiagram

            objectName: "connectionRouteDiagram"
            columns: 3
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 38
            Layout.alignment: Qt.AlignHCenter
            columnSpacing: Kirigami.Units.smallSpacing
            rowSpacing: Kirigami.Units.largeSpacing
            Accessible.name: root.splitRouteVisible
                ? qsTr("Split route: VPN traffic goes to %1; other traffic goes to the internet outside the VPN").arg(root.destinationName)
                : root.connected
                ? qsTr("Encrypted route from this device to %1").arg(root.destinationName)
                : qsTr("VPN route is inactive")

            RouteNode {
                id: deviceNode

                objectName: "deviceRouteNode"
                Layout.row: 0
                Layout.column: 0
                Layout.preferredWidth: Kirigami.Units.gridUnit * 12
                symbol: qsTr("You")
                heading: qsTr("This device")
                detail: qsTr("Protection settings")
                accentColor: root.connected
                    ? Kirigami.Theme.positiveTextColor
                    : Kirigami.Theme.disabledTextColor
                onClicked: root.navigateRequested("settings")
            }

            Item {
                id: routeLines

                objectName: "routeLines"
                Layout.row: 0
                Layout.column: 1
                Layout.rowSpan: root.splitRouteVisible ? 2 : 1
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.minimumWidth: Kirigami.Units.gridUnit * 3
                Layout.preferredWidth: Kirigami.Units.gridUnit * 14
                Layout.preferredHeight: Kirigami.Units.gridUnit * 5
                readonly property real deviceY:
                    deviceNode.y + deviceNode.routeCenterY - y
                readonly property real vpnY:
                    destinationGroup.y + destinationNode.y
                    + destinationNode.routeCenterY - y
                readonly property real internetY:
                    internetNode.y + internetNode.routeCenterY - y
                // Reach the actual symbols, not the edges of their wider
                // label columns. Keep the bypass fork left of the lock label.
                readonly property real startX: deviceNode.x
                    + deviceNode.width / 2 + deviceNode.routeRadius
                    + Kirigami.Units.smallSpacing - x
                readonly property real endX: destinationGroup.x
                    + destinationNode.x + destinationNode.width / 2
                    - destinationNode.routeRadius
                    - Kirigami.Units.smallSpacing - x
                readonly property real pathWidth: endX - startX
                readonly property color vpnColor: root.connected
                    ? Kirigami.Theme.positiveTextColor
                    : Kirigami.Theme.disabledTextColor

                Shape {
                    objectName: "connectionRouteShape"
                    preferredRendererType: Shape.CurveRenderer
                    x: routeLines.startX
                    width: routeLines.pathWidth
                    height: parent.height
                    Accessible.ignored: true

                    ShapePath {
                        strokeWidth: 2
                        strokeColor: routeLines.vpnColor
                        fillColor: "transparent"
                        startX: 0
                        startY: routeLines.deviceY
                        capStyle: ShapePath.RoundCap
                        PathCubic {
                            control1X: routeLines.pathWidth * 0.33
                            control1Y: routeLines.deviceY
                            control2X: routeLines.pathWidth * 0.67
                            control2Y: routeLines.vpnY
                            x: routeLines.pathWidth
                            y: routeLines.vpnY
                        }
                    }

                    ShapePath {
                        strokeWidth: 2
                        strokeStyle: ShapePath.DashLine
                        strokeColor: root.splitRouteVisible
                            ? Kirigami.Theme.neutralTextColor : "transparent"
                        fillColor: "transparent"
                        startX: routeLines.pathWidth * 0.16
                        startY: routeLines.deviceY
                        capStyle: ShapePath.RoundCap
                        PathCubic {
                            control1X: routeLines.pathWidth * 0.3
                            control1Y: routeLines.deviceY
                            control2X: routeLines.pathWidth * 0.18
                            control2Y: routeLines.internetY
                            x: routeLines.pathWidth
                            y: routeLines.internetY
                        }
                    }
                }

                Controls.ToolButton {
                    id: tunnelStateBadge

                    objectName: "tunnelStateBadge"
                    x: parent.width / 2 - width / 2
                    y: routeLines.vpnY - height / 2
                    width: Kirigami.Units.iconSizes.medium
                           + Kirigami.Units.largeSpacing
                    height: width
                    text: qsTr("Open connection inspector")
                    display: Controls.AbstractButton.IconOnly
                    enabled: root.connected
                    onClicked: root.navigateRequested("inspector")

                    background: Rectangle {
                        radius: width / 2
                        color: tunnelStateBadge.hovered
                               || tunnelStateBadge.activeFocus
                               ? Kirigami.Theme.alternateBackgroundColor
                               : Kirigami.Theme.backgroundColor
                        border.width: tunnelStateBadge.activeFocus ? 2 : 1
                        border.color: tunnelStateBadge.activeFocus
                            ? Kirigami.Theme.highlightColor
                            : routeLines.vpnColor
                    }

                    contentItem: Kirigami.Icon {
                        source: "network-vpn"
                        color: routeLines.vpnColor
                        Accessible.ignored: true
                    }

                    Controls.ToolTip.visible: hovered || activeFocus
                    Controls.ToolTip.text: text
                }

                Controls.Label {
                    anchors.horizontalCenter: tunnelStateBadge.horizontalCenter
                    anchors.top: tunnelStateBadge.bottom
                    anchors.topMargin: Kirigami.Units.smallSpacing
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.connected ? qsTr("Encrypted tunnel")
                                         : qsTr("VPN inactive")
                    color: root.connected ? Kirigami.Theme.linkColor
                                          : Kirigami.Theme.disabledTextColor
                }
            }

            ColumnLayout {
                id: destinationGroup

                objectName: "vpnEndpointGroup"
                Layout.row: 0
                Layout.column: 2
                Layout.preferredWidth: Kirigami.Units.gridUnit * 12
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.alignment: Qt.AlignTop
                spacing: Kirigami.Units.smallSpacing

                RouteNode {
                    id: destinationNode

                    objectName: "vpnRouteNode"
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

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: connectionFacts.visible
                                            ? connectionFacts.childrenRect.height : 0
                    visible: root.connected && (root.serverName.length > 0
                             || root.protocolName.length > 0
                             || (root.secureCore && root.entryCountry.length > 0)
                             || root.forwardedPort > 0)

                    Flow {
                        id: connectionFacts

                        objectName: "connectionFacts"
                        anchors.horizontalCenter: parent.horizontalCenter
                        readonly property int visibleFactCount:
                            (serverFact.visible ? 1 : 0)
                            + (protocolFact.visible ? 1 : 0)
                            + (entryFact.visible ? 1 : 0)
                            + (portFact.visible ? 1 : 0)
                        readonly property real idealWidth:
                            (serverFact.visible ? serverFact.implicitWidth : 0)
                            + (protocolFact.visible ? protocolFact.implicitWidth : 0)
                            + (entryFact.visible ? entryFact.implicitWidth : 0)
                            + (portFact.visible ? portFact.implicitWidth : 0)
                            + Math.max(0, visibleFactCount - 1) * spacing
                        width: Math.min(parent.width, idealWidth)
                        spacing: Kirigami.Units.smallSpacing

                        ConnectionFact {
                            id: serverFact

                            visible: root.serverName.length > 0
                            text: root.serverName
                            icon.name: "network-server-database"
                            Accessible.name: qsTr("Server %1").arg(root.serverName)
                            Accessible.description: qsTr("Open connection inspector")
                            onClicked: root.navigateRequested("inspector")

                            Controls.ToolTip.visible: hovered || activeFocus
                            Controls.ToolTip.text: qsTr("Server · %1").arg(root.serverName)
                        }

                        ConnectionFact {
                            id: protocolFact

                            visible: root.protocolName.length > 0
                            text: root.protocolName
                            icon.name: "network-vpn"
                            Accessible.name: qsTr("Protocol %1").arg(root.protocolName)
                            Accessible.description: qsTr("Open VPN settings")
                            onClicked: root.navigateRequested("settings")

                            Controls.ToolTip.visible: hovered || activeFocus
                            Controls.ToolTip.text: qsTr("Protocol · %1").arg(root.protocolName)
                        }

                        ConnectionFact {
                            id: entryFact

                            visible: root.secureCore && root.entryCountry.length > 0
                            text: qsTr("via %1").arg(root.entryCountry)
                            icon.name: "security-high"
                            Accessible.name: qsTr("Secure Core entry %1").arg(root.entryCountry)
                            Accessible.description: qsTr("Open connection inspector")
                            onClicked: root.navigateRequested("inspector")

                            Controls.ToolTip.visible: hovered || activeFocus
                            Controls.ToolTip.text: qsTr("Secure Core entry · %1").arg(root.entryCountry)
                        }

                        ConnectionFact {
                            id: portFact

                            visible: root.forwardedPort > 0
                            text: root.portCopied ? qsTr("Copied")
                                                  : root.forwardedPort.toString()
                            icon.name: root.portCopied ? "dialog-ok" : "edit-copy"
                            Accessible.name: root.portCopied
                                ? qsTr("Forwarded port copied")
                                : qsTr("Copy forwarded port %1").arg(root.forwardedPort)
                            onClicked: root.copyPortRequested()

                            Controls.ToolTip.visible: hovered || activeFocus
                            Controls.ToolTip.text: root.portCopied
                                ? qsTr("Copied")
                                : qsTr("Forwarded port · %1 · Click to copy")
                                      .arg(root.forwardedPort)
                        }
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
                        readonly property real idealWidth: {
                            let total = 0
                            let count = 0
                            for (const chip of children) {
                                if (chip.visible) {
                                    total += chip.implicitWidth
                                    count++
                                }
                            }
                            return total + Math.max(0, count - 1) * spacing
                        }
                        width: Math.min(parent.width, idealWidth)
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
            }

            RouteNode {
                id: internetNode

                objectName: "splitInternetRoute"
                Layout.row: 1
                Layout.column: 2
                Layout.preferredWidth: Kirigami.Units.gridUnit * 12
                visible: root.splitRouteVisible
                cloudSymbol: true
                heading: qsTr("Internet")
                detail: qsTr("Outside VPN")
                accentColor: Kirigami.Theme.neutralTextColor
                Accessible.description: qsTr("Open split-tunneling rules. Restart affected apps after changing rules.")
                onClicked: root.navigateRequested("split-tunneling")
                Controls.ToolTip.visible: hovered || activeFocus
                Controls.ToolTip.text: qsTr("Split tunneling follows your app and IP rules. Restart affected apps after changing rules.")
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
