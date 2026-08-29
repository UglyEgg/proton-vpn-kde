import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: page
    title: qsTr("Locations")

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

        PlasmaListItem {
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
            text: countryDelegate.name
            leadingText: countryDelegate.flag
            subtitle: countryDelegate.underMaintenance
                      ? qsTr("Under maintenance")
                      : !countryDelegate.accessible
                        ? qsTr("VPN Plus location")
                        : countryDelegate.free
                          ? qsTr("%n free server(s)", "", countryDelegate.serverCount)
                          : qsTr("%n server(s)", "", countryDelegate.serverCount)
            opacity: countryDelegate.accessible
                     && !countryDelegate.underMaintenance ? 1.0 : 0.65

            trailingContent: [
                Controls.ToolButton {
                    text: countryDelegate.accessible ? qsTr("Fastest")
                                                     : qsTr("Upgrade")
                    icon.name: countryDelegate.accessible
                               ? "network-connect" : "internet-web-browser"
                    display: Controls.AbstractButton.IconOnly
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

                    Controls.ToolTip.visible: hovered || activeFocus
                    Controls.ToolTip.text: text
                },

                Controls.ToolButton {
                    icon.name: countryDelegate.pinned
                               ? "favorite" : "non-starred-symbolic"
                    text: countryDelegate.pinned ? qsTr("Unpin") : qsTr("Pin")
                    display: Controls.AbstractButton.IconOnly
                    onClicked: appSettings.togglePinnedServer(countryDelegate.code)

                    Controls.ToolTip.visible: hovered || activeFocus
                    Controls.ToolTip.text: text
                }
            ]

            onClicked: page.openCountry(
                countryDelegate.code, countryDelegate.name, countryDelegate.flag,
                countryDelegate.accessible, countryDelegate.underMaintenance)
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: Kirigami.Units.smallSpacing

        PageHeader {
            heading: qsTr("Countries and servers")
            description: qsTr("Choose a country, city, or exact Proton server.")
            iconName: "network-server"
        }

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

                delegate: PlasmaListItem {
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
                    text: resultDelegate.name
                    leadingText: resultDelegate.countryFlag
                    subtitle: resultDelegate.kind === "country"
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
                    showChevron: resultDelegate.accessible
                                 && resultDelegate.kind !== "server"
                    opacity: resultDelegate.accessible
                             && !resultDelegate.underMaintenance ? 1.0 : 0.65

                    trailingContent: Controls.ToolButton {
                        visible: !resultDelegate.accessible
                                 || resultDelegate.kind === "server"
                        text: !resultDelegate.accessible ? qsTr("Upgrade")
                              : qsTr("Connect")
                        icon.name: !resultDelegate.accessible
                                   ? "internet-web-browser" : "network-connect"
                        display: Controls.AbstractButton.IconOnly
                        enabled: !resultDelegate.underMaintenance
                                 && (resultDelegate.kind !== "server"
                                     || vpnController.primaryActionEnabled)
                        onClicked: {
                            if (!resultDelegate.accessible) {
                                Qt.openUrlExternally(
                                    "https://protonvpn.com/pricing")
                            } else {
                                vpnController.connectServer(resultDelegate.name)
                            }
                        }

                        Controls.ToolTip.visible: hovered || activeFocus
                        Controls.ToolTip.text: text
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
