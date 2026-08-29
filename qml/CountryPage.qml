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

    title: countryFlag + "  " + countryName

    Component.onCompleted: vpnController.loadServerGroups(countryCode)

    actions: [
        Kirigami.Action {
            text: page.countryAccessible
                  ? qsTr("Connect fastest in %1").arg(page.countryName)
                  : qsTr("Upgrade for %1").arg(page.countryName)
            icon.name: page.countryAccessible
                       ? "network-connect" : "internet-web-browser"
            enabled: !page.countryUnderMaintenance
                     && (page.countryAccessible
                         ? vpnController.primaryActionEnabled : true)
            onTriggered: {
                if (page.countryAccessible) {
                    vpnController.connectCountry(page.countryCode)
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

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: groupList.count === 0
            text: vpnController.locationsBusy
                  ? qsTr("Loading locations…")
                  : qsTr("No locations available")
            icon.name: vpnController.locationsBusy ? "view-refresh" : "network-offline"
        }

        delegate: Controls.ItemDelegate {
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

            width: ListView.view.width
            horizontalPadding: Kirigami.Units.largeSpacing
            opacity: groupDelegate.accessible
                     && !groupDelegate.underMaintenance ? 1.0 : 0.65

            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Icon {
                    source: groupDelegate.secureCore
                            ? "security-high"
                            : "mark-location"
                    implicitWidth: Kirigami.Units.iconSizes.medium
                    implicitHeight: implicitWidth
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    RowLayout {
                        Controls.Label {
                            text: groupDelegate.secureCore
                                  ? qsTr("Via Secure Core")
                                  : groupDelegate.name
                            font.bold: true
                        }
                        Controls.Label {
                            visible: groupDelegate.tor
                            text: qsTr("Tor")
                            color: Kirigami.Theme.neutralTextColor
                        }
                        Controls.Label {
                            visible: groupDelegate.p2p
                            text: qsTr("P2P")
                            color: Kirigami.Theme.positiveTextColor
                        }
                        Controls.Label {
                            visible: groupDelegate.streaming
                            text: qsTr("Streaming")
                            color: Kirigami.Theme.linkColor
                        }
                    }

                    Controls.Label {
                        text: groupDelegate.underMaintenance
                              ? qsTr("Under maintenance")
                              : !groupDelegate.accessible
                                ? qsTr("VPN Plus location")
                                : groupDelegate.smartRouting
                                  ? qsTr("%n server(s) · Smart Routing", "", groupDelegate.serverCount)
                                  : qsTr("%n server(s)", "", groupDelegate.serverCount)
                        color: groupDelegate.underMaintenance
                               ? Kirigami.Theme.negativeTextColor
                               : Kirigami.Theme.disabledTextColor
                    }
                }

                Controls.Button {
                    text: groupDelegate.accessible ? qsTr("Fastest")
                                                   : qsTr("Upgrade")
                    icon.name: groupDelegate.accessible
                               ? "network-connect" : "internet-web-browser"
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
                }

                Kirigami.Icon {
                    source: "go-next"
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: implicitWidth
                }
            }

            onClicked: applicationWindow().pushServers({
                    "countryCode": page.countryCode,
                    "countryName": page.countryName,
                    "countryFlag": page.countryFlag,
                    "groupKind": groupDelegate.kind,
                    "groupName": groupDelegate.name,
                    "groupAccessible": groupDelegate.accessible,
                    "groupUnderMaintenance": groupDelegate.underMaintenance
                })
        }
    }

    Component.onDestruction: vpnController.clearServerContext()
}
