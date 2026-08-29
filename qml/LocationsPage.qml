import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: page
    title: qsTr("Countries")

    readonly property bool searching: searchField.text.trim().length > 0

    function openCountry(code, name, flag, accessible, underMaintenance) {
        applicationWindow().pushCountry({
                "countryCode": code,
                "countryName": name,
                "countryFlag": flag,
                "countryAccessible": accessible,
                "countryUnderMaintenance": underMaintenance
            })
    }

    function activateSearchResult(kind, name, countryCode, countryName,
                                  countryFlag, location, groupKind, groupName,
                                  accessible, underMaintenance) {
        if (!accessible) {
            Qt.openUrlExternally("https://protonvpn.com/pricing")
        } else if (kind === "country") {
            page.openCountry(countryCode, countryName, countryFlag,
                             accessible, underMaintenance)
        } else if (kind === "location" || kind === "server") {
            applicationWindow().pushServers({
                    "countryCode": countryCode,
                    "countryName": countryName,
                    "countryFlag": countryFlag,
                    "groupKind": groupKind,
                    "groupName": groupName.length > 0
                                 ? groupName
                                 : (location.length > 0 ? location : name),
                    "groupAccessible": accessible,
                    "groupUnderMaintenance": underMaintenance,
                    "initialServerFilter": kind === "server" ? name : ""
                })
        }
    }

    Component.onCompleted: vpnController.loadCountries()
    Component.onDestruction: vpnController.clearLocationSearch()

    actions: [
        Kirigami.Action {
            text: qsTr("Refresh")
            icon.name: "view-refresh"
            enabled: !vpnController.locationsBusy
            onTriggered: vpnController.loadCountries()
        }
    ]

    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: searchField.forceActiveFocus()
    }

    Timer {
        id: searchDelay
        interval: 180
        repeat: false
        onTriggered: vpnController.searchLocations(searchField.text)
    }

    Component {
        id: countryDelegateComponent

        Controls.ItemDelegate {
            id: countryDelegate
            required property string code
            required property string name
            required property string flag
            required property int serverCount
            required property bool accessible
            required property bool underMaintenance
            required property bool free
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
            opacity: countryDelegate.accessible
                     && !countryDelegate.underMaintenance ? 1.0 : 0.65

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
                        text: countryDelegate.underMaintenance
                              ? qsTr("Under maintenance")
                              : !countryDelegate.accessible
                                ? qsTr("VPN Plus location")
                                : countryDelegate.free
                                  ? qsTr("%n free server(s)", "", countryDelegate.serverCount)
                                  : qsTr("%n server(s)", "", countryDelegate.serverCount)
                        color: Kirigami.Theme.disabledTextColor
                    }
                }

                Controls.Button {
                    text: countryDelegate.accessible ? qsTr("Fastest")
                                                     : qsTr("Upgrade")
                    icon.name: countryDelegate.accessible
                               ? "network-connect" : "internet-web-browser"
                    enabled: !countryDelegate.underMaintenance
                             && (countryDelegate.accessible
                                 ? vpnController.primaryActionEnabled : true)
                    onClicked: {
                        if (countryDelegate.accessible) {
                            vpnController.connectCountry(countryDelegate.code)
                        } else {
                            Qt.openUrlExternally("https://protonvpn.com/pricing")
                        }
                    }
                }

                Controls.Button {
                    flat: true
                    icon.name: countryDelegate.pinned
                               ? "favorite" : "non-starred-symbolic"
                    text: countryDelegate.pinned ? qsTr("Unpin") : qsTr("Pin")
                    onClicked: appSettings.togglePinnedServer(countryDelegate.code)
                }

                Kirigami.Icon {
                    source: "go-next"
                    implicitWidth: Kirigami.Units.iconSizes.small
                    implicitHeight: implicitWidth
                }
            }

            onClicked: page.openCountry(
                countryDelegate.code, countryDelegate.name, countryDelegate.flag,
                countryDelegate.accessible, countryDelegate.underMaintenance)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        Kirigami.SearchField {
            id: searchField
            Layout.fillWidth: true
            placeholderText: qsTr("Search countries, cities, or servers")
            onTextChanged: {
                if (text.trim().length === 0) {
                    searchDelay.stop()
                    vpnController.clearLocationSearch()
                } else {
                    searchDelay.restart()
                }
            }
        }

        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: page.searching ? 1 : 0

            ListView {
                id: countryList
                model: vpnController.countryModel
                spacing: Kirigami.Units.smallSpacing
                clip: true

                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    visible: countryList.count === 0
                    text: vpnController.locationsBusy
                          ? qsTr("Loading countries…")
                          : qsTr("No countries available")
                    icon.name: vpnController.locationsBusy
                               ? "view-refresh" : "network-offline"
                }

                delegate: countryDelegateComponent
            }

            ListView {
                id: searchResults
                model: vpnController.locationSearchModel
                spacing: Kirigami.Units.smallSpacing
                clip: true
                section.property: "kind"
                section.criteria: ViewSection.FullString
                section.delegate: Kirigami.ListSectionHeader {
                    required property string section
                    text: section === "country" ? qsTr("Countries")
                          : section === "location" ? qsTr("Locations")
                          : qsTr("Servers")
                }

                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    visible: searchResults.count === 0
                    text: vpnController.locationSearchBusy
                          ? qsTr("Searching…") : qsTr("No matching locations")
                    icon.name: vpnController.locationSearchBusy
                               ? "view-refresh" : "edit-find"
                }

                delegate: Controls.ItemDelegate {
                    id: resultDelegate
                    required property string kind
                    required property string name
                    required property string countryCode
                    required property string countryName
                    required property string countryFlag
                    required property string location
                    required property string groupKind
                    required property string groupName
                    required property int load
                    required property int serverCount
                    required property bool accessible
                    required property bool underMaintenance

                    width: ListView.view.width
                    horizontalPadding: Kirigami.Units.largeSpacing
                    opacity: resultDelegate.accessible
                             && !resultDelegate.underMaintenance ? 1.0 : 0.65

                    contentItem: RowLayout {
                        spacing: Kirigami.Units.largeSpacing

                        Controls.Label {
                            text: resultDelegate.countryFlag
                            font.pixelSize: Kirigami.Units.gridUnit * 1.4
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0

                            Controls.Label {
                                text: resultDelegate.name
                                font.bold: true
                            }
                            Controls.Label {
                                text: resultDelegate.kind === "country"
                                      ? (!resultDelegate.accessible
                                         ? qsTr("VPN Plus location")
                                         : qsTr("%n server(s)", "", resultDelegate.serverCount))
                                      : resultDelegate.kind === "server"
                                        ? qsTr("%1 · %2% load")
                                            .arg(resultDelegate.location.length > 0
                                                 ? resultDelegate.location
                                                 : resultDelegate.countryName)
                                            .arg(resultDelegate.load)
                                        : resultDelegate.countryName
                                color: Kirigami.Theme.disabledTextColor
                            }
                        }

                        Controls.Button {
                            text: !resultDelegate.accessible ? qsTr("Upgrade")
                                  : resultDelegate.kind === "server"
                                    ? qsTr("Connect") : qsTr("Open")
                            icon.name: !resultDelegate.accessible
                                       ? "internet-web-browser"
                                       : resultDelegate.kind === "server"
                                         ? "network-connect" : "go-next"
                            enabled: !resultDelegate.underMaintenance
                                     && (resultDelegate.kind !== "server"
                                         || vpnController.primaryActionEnabled)
                            onClicked: {
                                if (!resultDelegate.accessible) {
                                    Qt.openUrlExternally(
                                        "https://protonvpn.com/pricing")
                                } else if (resultDelegate.kind === "server") {
                                    vpnController.connectServer(resultDelegate.name)
                                } else {
                                    page.activateSearchResult(
                                        resultDelegate.kind, resultDelegate.name,
                                        resultDelegate.countryCode,
                                        resultDelegate.countryName,
                                        resultDelegate.countryFlag,
                                        resultDelegate.location,
                                        resultDelegate.groupKind,
                                        resultDelegate.groupName,
                                        resultDelegate.accessible,
                                        resultDelegate.underMaintenance)
                                }
                            }
                        }
                    }

                    onClicked: page.activateSearchResult(
                        resultDelegate.kind, resultDelegate.name,
                        resultDelegate.countryCode, resultDelegate.countryName,
                        resultDelegate.countryFlag, resultDelegate.location,
                        resultDelegate.groupKind, resultDelegate.groupName,
                        resultDelegate.accessible,
                        resultDelegate.underMaintenance)
                }
            }
        }
    }
}
