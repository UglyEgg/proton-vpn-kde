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

    property bool previousLoggedIn: vpnController.loggedIn

    Connections {
        target: vpnController
        function onSnapshotChanged() {
            if (!root.previousLoggedIn && vpnController.loggedIn) {
                root.showPage(Qt.resolvedUrl("OverviewPage.qml"))
            } else if (root.previousLoggedIn && !vpnController.loggedIn) {
                root.showPage(Qt.resolvedUrl("SignInPage.qml"))
            }
            root.previousLoggedIn = vpnController.loggedIn
        }
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
                text: vpnController.loggedIn ? qsTr("Account") : qsTr("Sign in")
                icon.name: vpnController.loggedIn ? "user-identity" : "system-log-in"
                onTriggered: root.showPage(Qt.resolvedUrl(
                    vpnController.loggedIn ? "AccountPage.qml" : "SignInPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Settings")
                icon.name: "settings-configure"
                onTriggered: root.showPage(Qt.resolvedUrl("SettingsPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Release notes")
                icon.name: "view-list-text"
                onTriggered: root.showPage(Qt.resolvedUrl("ReleaseNotesPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Report an issue")
                icon.name: "tools-report-bug"
                enabled: vpnController.loggedIn
                onTriggered: root.showPage(Qt.resolvedUrl("ReportIssuePage.qml"))
            },
            Kirigami.Action {
                text: qsTr("About")
                icon.name: "help-about"
                onTriggered: root.showPage(Qt.resolvedUrl("AboutPage.qml"))
            }
        ]
    }
}
