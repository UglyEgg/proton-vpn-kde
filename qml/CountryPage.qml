import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    required property string countryCode
    required property string countryName
    required property string countryFlag

    title: countryFlag + "  " + countryName

    Component.onCompleted: vpnController.loadServerGroups(countryCode)

    actions: [
        Kirigami.Action {
            text: qsTr("Connect fastest in %1").arg(page.countryName)
            icon.name: "network-connect"
            enabled: vpnController.primaryActionEnabled
            onTriggered: vpnController.connectCountry(page.countryCode)
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
                              : groupDelegate.smartRouting
                                ? qsTr("%n server(s) · Smart Routing", "", groupDelegate.serverCount)
                                : qsTr("%n server(s)", "", groupDelegate.serverCount)
                        color: groupDelegate.underMaintenance
                               ? Kirigami.Theme.negativeTextColor
                               : Kirigami.Theme.disabledTextColor
                    }
                }

                Controls.Button {
                    text: qsTr("Fastest")
                    icon.name: "network-connect"
                    enabled: vpnController.primaryActionEnabled
                             && groupDelegate.accessible
                             && !groupDelegate.underMaintenance
                    onClicked: vpnController.connectGroup(
                        page.countryCode, groupDelegate.kind, groupDelegate.name)
                }

                Kirigami.Icon {
                    source: "go-next"
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: implicitWidth
                }
            }

            onClicked: applicationWindow().pageStack.push(
                Qt.resolvedUrl("ServersPage.qml"), {
                    "countryCode": page.countryCode,
                    "countryName": page.countryName,
                    "countryFlag": page.countryFlag,
                    "groupKind": groupDelegate.kind,
                    "groupName": groupDelegate.name
                })
        }
    }

    Component.onDestruction: vpnController.clearServerContext()
}
