// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    required property string countryCode
    required property string countryName
    required property string countryFlag
    required property string groupKind
    required property string groupName
    required property bool groupAccessible
    required property bool groupUnderMaintenance
    property string initialServerFilter: ""
    property var requiredCapabilities: []

    title: groupKind === "secure-core"
           ? countryFlag + "  " + countryName + " · " + qsTr("Secure Core")
           : countryFlag + "  " + groupName

    function serverSummary(location, entryCountry, secureCore, smartRouting,
                           tor, p2p, streaming, underMaintenance) {
        if (underMaintenance) {
            return qsTr("Under maintenance")
        }
        const details = []
        if (secureCore && entryCountry.length > 0) {
            details.push(qsTr("Via %1").arg(entryCountry))
        } else if (location.length > 0) {
            details.push(location)
        }
        if (smartRouting) {
            details.push(qsTr("Smart Routing"))
        }
        if (tor) {
            details.push(qsTr("Tor"))
        }
        if (p2p) {
            details.push(qsTr("P2P"))
        }
        if (streaming) {
            details.push(qsTr("Streaming"))
        }
        return details.join(" · ")
    }

    Component.onCompleted: {
        vpnController.setServerFeatureFilter(requiredCapabilities)
        vpnController.loadGroupServers(countryCode, groupKind, groupName)
        if (initialServerFilter.length > 0) {
            serverSearch.text = initialServerFilter
        }
    }

    actions: [
        Kirigami.Action {
            text: !page.groupAccessible
                  ? qsTr("Upgrade for this location")
                  : page.groupKind === "secure-core"
                    ? page.requiredCapabilities.length > 0
                      ? qsTr("Connect fastest matching Secure Core route")
                      : qsTr("Connect fastest via Secure Core")
                    : page.requiredCapabilities.length > 0
                      ? qsTr("Connect fastest match in %1").arg(page.groupName)
                      : qsTr("Connect fastest in %1").arg(page.groupName)
            icon.name: page.groupAccessible
                       ? "network-connect" : "internet-web-browser"
            enabled: !page.groupUnderMaintenance
                     && (page.groupAccessible
                         ? vpnController.primaryActionEnabled : true)
            onTriggered: {
                if (page.groupAccessible) {
                    if (page.requiredCapabilities.length > 0) {
                        vpnController.connectGroupWithFeatures(
                            page.countryCode, page.groupKind, page.groupName,
                            page.requiredCapabilities)
                    } else {
                        vpnController.connectGroup(
                            page.countryCode, page.groupKind, page.groupName)
                    }
                } else {
                    Qt.openUrlExternally("https://protonvpn.com/pricing")
                }
            }
        },
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            enabled: !vpnController.locationsBusy
            onTriggered: vpnController.loadGroupServers(
                page.countryCode, page.groupKind, page.groupName)
        }
    ]

    ListView {
        id: serverList
        model: vpnController.serverModel
        spacing: Kirigami.Units.smallSpacing

        header: ColumnLayout {
            width: serverList.width
            spacing: Kirigami.Units.largeSpacing

            PageHeader {
                heading: page.groupKind === "secure-core"
                         ? page.countryFlag + "  " + page.countryName
                           + " · " + qsTr("Secure Core")
                         : page.countryFlag + "  " + page.groupName
                description: page.requiredCapabilities.length > 0
                             ? qsTr("Choose an exact server matching every selected capability.")
                             : qsTr("Choose an exact Proton server.")
                iconName: page.groupKind === "secure-core"
                          ? "security-high" : "network-server"
            }

            Kirigami.SearchField {
                id: serverSearch
                Layout.fillWidth: true
                placeholderText: qsTr("Search servers or locations")
                onTextChanged: vpnController.setServerFilter(text)
            }
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: serverList.count === 0
            text: vpnController.locationsBusy
                  ? qsTr("Loading servers…")
                  : page.requiredCapabilities.length > 0
                    ? qsTr("No servers match the selected capabilities")
                    : qsTr("No servers available")
            icon.name: vpnController.locationsBusy ? "view-refresh" : "network-offline"
        }

        delegate: PlasmaListItem {
            id: serverDelegate
            required property string name
            required property string location
            required property string entryCountry
            required property int load
            required property bool accessible
            required property bool underMaintenance
            required property bool smartRouting
            required property bool secureCore
            required property bool tor
            required property bool p2p
            required property bool streaming
            property bool pinned: appSettings.isServerPinned(name)

            Connections {
                target: appSettings
                function onPinnedServersChanged() {
                    serverDelegate.pinned = appSettings.isServerPinned(
                        serverDelegate.name)
                }
            }

            width: ListView.view.width
            text: serverDelegate.name
            icon.name: serverDelegate.secureCore ? "security-high" : "network-server"
            subtitle: page.serverSummary(
                serverDelegate.location, serverDelegate.entryCountry,
                serverDelegate.secureCore, serverDelegate.smartRouting,
                serverDelegate.tor, serverDelegate.p2p,
                serverDelegate.streaming, serverDelegate.underMaintenance)
            showChevron: false
            opacity: serverDelegate.accessible
                     && !serverDelegate.underMaintenance ? 1.0 : 0.65

            trailingContent: [
                ColumnLayout {
                    spacing: 0
                    Controls.Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: serverDelegate.underMaintenance
                              ? qsTr("Unavailable")
                              : qsTr("%1% load").arg(serverDelegate.load)
                        color: serverDelegate.load >= 90
                               ? Kirigami.Theme.negativeTextColor
                               : Kirigami.Theme.textColor
                    }
                    Controls.ProgressBar {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 5
                        from: 0
                        to: 100
                        value: serverDelegate.underMaintenance ? 0 : serverDelegate.load
                    }
                },

                Controls.ToolButton {
                    text: serverDelegate.accessible ? qsTr("Connect")
                                                    : qsTr("Upgrade")
                    icon.name: serverDelegate.accessible
                               ? "network-connect" : "internet-web-browser"
                    display: Controls.AbstractButton.IconOnly
                    enabled: !serverDelegate.underMaintenance
                             && (serverDelegate.accessible
                                 ? vpnController.primaryActionEnabled : true)
                    onClicked: {
                        if (serverDelegate.accessible) {
                            vpnController.connectServer(serverDelegate.name)
                        } else {
                            Qt.openUrlExternally("https://protonvpn.com/pricing")
                        }
                    }

                    Controls.ToolTip.visible: hovered || activeFocus
                    Controls.ToolTip.text: text
                },

                Controls.ToolButton {
                    icon.name: serverDelegate.pinned
                               ? "window-unpin" : "window-pin"
                    text: serverDelegate.pinned ? qsTr("Unpin") : qsTr("Pin")
                    display: Controls.AbstractButton.IconOnly
                    onClicked: appSettings.togglePinnedServer(serverDelegate.name)

                    Controls.ToolTip.visible: hovered || activeFocus
                    Controls.ToolTip.text: text
                }
            ]
        }
    }

    Component.onDestruction: {
        vpnController.setServerFilter("")
        vpnController.setServerFeatureFilter([])
        vpnController.clearGroupServerContext()
    }
}
