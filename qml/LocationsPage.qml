import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Countries")

    Component.onCompleted: vpnController.loadCountries()

    actions: [
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            enabled: !vpnController.locationsBusy
            onTriggered: vpnController.loadCountries()
        }
    ]

    ListView {
        id: countryList
        model: vpnController.countryModel
        spacing: Kirigami.Units.smallSpacing

        header: Kirigami.SearchField {
            width: countryList.width
            placeholderText: qsTr("Search countries")
            onTextChanged: vpnController.setCountryFilter(text)
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: countryList.count === 0
            text: vpnController.locationsBusy
                  ? qsTr("Loading countries…")
                  : qsTr("No countries available")
            icon.name: vpnController.locationsBusy ? "view-refresh" : "network-offline"
        }

        delegate: Controls.ItemDelegate {
            id: countryDelegate
            required property string code
            required property string name
            required property string flag
            required property int serverCount
            property bool pinned: appSettings.isServerPinned(code)

            Connections {
                target: appSettings
                function onPinnedServersChanged() {
                    countryDelegate.pinned = appSettings.isServerPinned(
                        countryDelegate.code)
                }
            }

            width: ListView.view.width
            horizontalPadding: Kirigami.Units.largeSpacing

            contentItem: RowLayout {
                spacing: Kirigami.Units.largeSpacing

                Controls.Label {
                    text: countryDelegate.flag
                    font.pixelSize: Kirigami.Units.gridUnit * 1.6
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    Controls.Label {
                        text: countryDelegate.name
                        font.bold: true
                    }
                    Controls.Label {
                        text: qsTr("%n server(s)", "", countryDelegate.serverCount)
                        color: Kirigami.Theme.disabledTextColor
                    }
                }

                Controls.Button {
                    text: qsTr("Fastest")
                    icon.name: "network-connect"
                    enabled: vpnController.primaryActionEnabled
                    onClicked: vpnController.connectCountry(countryDelegate.code)
                }

                Controls.Button {
                    flat: true
                    icon.name: countryDelegate.pinned ? "favorite" : "non-starred-symbolic"
                    text: countryDelegate.pinned ? qsTr("Unpin") : qsTr("Pin")
                    onClicked: appSettings.togglePinnedServer(countryDelegate.code)
                }

                Kirigami.Icon {
                    source: "go-next"
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: implicitWidth
                }
            }

            onClicked: {
                applicationWindow().pageStack.push(
                    Qt.resolvedUrl("CountryPage.qml"), {
                    "countryCode": countryDelegate.code,
                    "countryName": countryDelegate.name,
                    "countryFlag": countryDelegate.flag
                })
            }
        }
    }

    Component.onDestruction: vpnController.setCountryFilter("")
}
