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
    required property bool countryAccessible
    required property bool countryUnderMaintenance
    property var requiredCapabilities: []

    title: countryFlag + "  " + countryName

    function groupSummary(serverCount, accessible, underMaintenance,
                          smartRouting, tor, p2p, streaming) {
        if (underMaintenance) {
            return qsTr("Under maintenance")
        }
        if (!accessible) {
            return qsTr("VPN Plus location")
        }
        const details = [qsTr("%n server(s)", "", serverCount)]
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
        vpnController.setServerGroupFeatureFilter(requiredCapabilities)
        vpnController.loadServerGroups(countryCode)
    }

    actions: [
        Kirigami.Action {
            text: page.countryAccessible
                  ? page.requiredCapabilities.length > 0
                    ? qsTr("Connect fastest match in %1").arg(page.countryName)
                    : qsTr("Connect fastest in %1").arg(page.countryName)
                  : qsTr("Upgrade for %1").arg(page.countryName)
            icon.name: page.countryAccessible
                       ? "network-connect" : "internet-web-browser"
            enabled: !page.countryUnderMaintenance
                     && (page.countryAccessible
                         ? vpnController.primaryActionEnabled : true)
            onTriggered: {
                if (page.countryAccessible) {
                    if (page.requiredCapabilities.length > 0) {
                        vpnController.connectCountryWithFeatures(
                            page.countryCode, page.requiredCapabilities)
                    } else {
                        vpnController.connectCountry(page.countryCode)
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
            onTriggered: vpnController.loadServerGroups(page.countryCode)
        }
    ]

    ListView {
        id: groupList
        model: vpnController.serverGroupModel
        spacing: Kirigami.Units.smallSpacing

        header: PageHeader {
            width: groupList.width
            heading: page.countryFlag + "  " + page.countryName
            description: qsTr("Choose a location or specialized server group.")
                         + (page.requiredCapabilities.length > 0
                            ? " " + qsTr("Only groups supporting every selected capability are shown.")
                            : "")
            iconName: "mark-location"
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: groupList.count === 0
            text: vpnController.locationsBusy
                  ? qsTr("Loading locations…")
                  : page.requiredCapabilities.length > 0
                    ? qsTr("No locations match the selected capabilities")
                    : qsTr("No locations available")
            icon.name: vpnController.locationsBusy ? "view-refresh" : "network-offline"
        }

        delegate: PlasmaListItem {
            id: groupDelegate
            required property string kind
            required property string name
            required property int serverCount
            required property bool accessible
            required property bool underMaintenance
            required property bool smartRouting
            required property bool secureCore
            required property bool tor
            required property bool p2p
            required property bool streaming
            property bool pinned: appSettings.isServerGroupPinned(
                                      page.countryCode,
                                      groupDelegate.kind,
                                      groupDelegate.name)

            Connections {
                target: appSettings
                function onPinnedServerGroupsChanged() {
                    groupDelegate.pinned = appSettings.isServerGroupPinned(
                        page.countryCode,
                        groupDelegate.kind,
                        groupDelegate.name)
                }
            }

            width: ListView.view.width
            text: groupDelegate.secureCore
                  ? qsTr("Via Secure Core") : groupDelegate.name
            icon.name: groupDelegate.secureCore ? "security-high" : "mark-location"
            subtitle: page.groupSummary(
                groupDelegate.serverCount, groupDelegate.accessible,
                groupDelegate.underMaintenance, groupDelegate.smartRouting,
                groupDelegate.tor, groupDelegate.p2p, groupDelegate.streaming)
            opacity: groupDelegate.accessible
                     && !groupDelegate.underMaintenance ? 1.0 : 0.65

            trailingContent: [
                Controls.ToolButton {
                    text: groupDelegate.accessible ? qsTr("Fastest")
                                                   : qsTr("Upgrade")
                    icon.name: groupDelegate.accessible
                               ? "network-connect" : "internet-web-browser"
                    display: Controls.AbstractButton.IconOnly
                    enabled: !groupDelegate.underMaintenance
                             && (groupDelegate.accessible
                                 ? vpnController.primaryActionEnabled : true)
                    onClicked: {
                        if (groupDelegate.accessible) {
                            vpnController.connectGroup(
                                page.countryCode, groupDelegate.kind,
                                groupDelegate.name)
                        } else {
                            Qt.openUrlExternally("https://protonvpn.com/pricing")
                        }
                    }

                    Controls.ToolTip.visible: hovered || activeFocus
                    Controls.ToolTip.text: text
                },

                Controls.ToolButton {
                    icon.name: groupDelegate.pinned
                               ? "window-unpin" : "window-pin"
                    text: groupDelegate.pinned ? qsTr("Unpin") : qsTr("Pin")
                    display: Controls.AbstractButton.IconOnly
                    onClicked: appSettings.togglePinnedServerGroup(
                        page.countryCode, groupDelegate.kind, groupDelegate.name)

                    Controls.ToolTip.visible: hovered || activeFocus
                    Controls.ToolTip.text: text
                }
            ]

            onClicked: applicationWindow().pushServers({
                    "countryCode": page.countryCode,
                    "countryName": page.countryName,
                    "countryFlag": page.countryFlag,
                    "groupKind": groupDelegate.kind,
                    "groupName": groupDelegate.name,
                    "groupAccessible": groupDelegate.accessible,
                    "groupUnderMaintenance": groupDelegate.underMaintenance,
                    "requiredCapabilities": page.requiredCapabilities
                })
        }
    }

    Component.onDestruction: {
        vpnController.setServerGroupFeatureFilter([])
        vpnController.clearServerContext()
    }
}
