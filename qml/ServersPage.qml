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

    Component.onCompleted: vpnController.loadServers(countryCode)

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
            onTriggered: vpnController.loadServers(page.countryCode)
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
            required property int load
            required property bool p2p
            required property bool streaming

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
                        text: serverDelegate.location
                        color: Kirigami.Theme.disabledTextColor
                    }
                }

                ColumnLayout {
                    spacing: 0
                    Controls.Label {
                        Layout.alignment: Qt.AlignHCenter
                        text: qsTr("%1% load").arg(serverDelegate.load)
                        color: serverDelegate.load >= 90
                               ? Kirigami.Theme.negativeTextColor
                               : Kirigami.Theme.textColor
                    }
                    Controls.ProgressBar {
                        Layout.preferredWidth: Kirigami.Units.gridUnit * 5
                        from: 0
                        to: 100
                        value: serverDelegate.load
                    }
                }

                Controls.Button {
                    text: qsTr("Connect")
                    icon.name: "network-connect"
                    enabled: vpnController.primaryActionEnabled
                    onClicked: vpnController.connectServer(serverDelegate.name)
                }
            }
        }
    }

    Component.onDestruction: vpnController.setServerFilter("")
}
