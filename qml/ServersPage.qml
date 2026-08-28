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

    title: groupKind === "secure-core"
           ? countryFlag + "  " + countryName + " · " + qsTr("Secure Core")
           : countryFlag + "  " + groupName

    Component.onCompleted: vpnController.loadGroupServers(
        countryCode, groupKind, groupName)

    actions: [
        Kirigami.Action {
            text: page.groupKind === "secure-core"
                  ? qsTr("Connect fastest via Secure Core")
                  : qsTr("Connect fastest in %1").arg(page.groupName)
            icon.name: "network-connect"
            enabled: vpnController.primaryActionEnabled
            onTriggered: vpnController.connectGroup(
                page.countryCode, page.groupKind, page.groupName)
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

        header: Kirigami.SearchField {
            width: serverList.width
            placeholderText: qsTr("Search servers or locations")
            onTextChanged: vpnController.setServerFilter(text)
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: serverList.count === 0
            text: vpnController.locationsBusy
                  ? qsTr("Loading servers…")
                  : qsTr("No servers available")
            icon.name: vpnController.locationsBusy ? "view-refresh" : "network-offline"
        }

        delegate: Controls.ItemDelegate {
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
            horizontalPadding: Kirigami.Units.largeSpacing

            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    RowLayout {
                        Controls.Label {
                            text: serverDelegate.name
                            font.bold: true
                        }
                        Controls.Label {
                            visible: serverDelegate.secureCore
                            text: qsTr("Secure Core")
                            color: Kirigami.Theme.positiveTextColor
                        }
                        Controls.Label {
                            visible: serverDelegate.tor
                            text: qsTr("Tor")
                            color: Kirigami.Theme.neutralTextColor
                        }
                        Controls.Label {
                            visible: serverDelegate.p2p
                            text: qsTr("P2P")
                            color: Kirigami.Theme.positiveTextColor
                        }
                        Controls.Label {
                            visible: serverDelegate.streaming
                            text: qsTr("Streaming")
                            color: Kirigami.Theme.linkColor
                        }
                    }

                    Controls.Label {
                        visible: serverDelegate.location.length > 0
                                 || serverDelegate.entryCountry.length > 0
                        text: serverDelegate.secureCore
                              && serverDelegate.entryCountry.length > 0
                              ? qsTr("Via %1").arg(serverDelegate.entryCountry)
                              : serverDelegate.location
                        color: Kirigami.Theme.disabledTextColor
                    }
                    Controls.Label {
                        visible: serverDelegate.smartRouting
                        text: qsTr("Smart Routing")
                        color: Kirigami.Theme.linkColor
                    }
                    Controls.Label {
                        visible: serverDelegate.underMaintenance
                        text: qsTr("Under maintenance")
                        color: Kirigami.Theme.negativeTextColor
                    }
                }

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
                }

                Controls.Button {
                    text: qsTr("Connect")
                    icon.name: "network-connect"
                    enabled: vpnController.primaryActionEnabled
                             && serverDelegate.accessible
                             && !serverDelegate.underMaintenance
                    onClicked: vpnController.connectServer(serverDelegate.name)
                }

                Controls.Button {
                    flat: true
                    icon.name: serverDelegate.pinned ? "favorite" : "non-starred-symbolic"
                    text: serverDelegate.pinned ? qsTr("Unpin") : qsTr("Pin")
                    onClicked: appSettings.togglePinnedServer(serverDelegate.name)
                }
            }
        }
    }

    Component.onDestruction: {
        vpnController.setServerFilter("")
        vpnController.clearGroupServerContext()
    }
}
