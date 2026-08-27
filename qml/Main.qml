import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    width: 520
    height: 700
    minimumWidth: 420
    minimumHeight: 560
    visible: !startMinimized
    title: qsTr("Proton VPN")

    onClosing: close => {
        if (appSettings.closeToTray) {
            close.accepted = false
            root.hide()
        }
    }

    function showPage(pageUrl) {
        pageStack.clear()
        pageStack.push(pageUrl)
    }

    pageStack.initialPage: Qt.resolvedUrl("OverviewPage.qml")

    globalDrawer: Kirigami.GlobalDrawer {
        title: qsTr("Proton VPN")
        titleIcon: "network-vpn"
        isMenu: true

        actions: [
            Kirigami.Action {
                text: qsTr("Overview")
                icon.name: "network-vpn"
                onTriggered: root.showPage(Qt.resolvedUrl("OverviewPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Countries and servers")
                icon.name: "network-server"
                enabled: vpnController.loggedIn
                onTriggered: root.showPage(Qt.resolvedUrl("LocationsPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Settings")
                icon.name: "settings-configure"
                onTriggered: root.showPage(Qt.resolvedUrl("SettingsPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("About")
                icon.name: "help-about"
                enabled: false
                tooltip: qsTr("Coming in the next milestone")
            }
        ]
    }
}
