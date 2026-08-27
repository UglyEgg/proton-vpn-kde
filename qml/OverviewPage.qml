import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Page {
    id: page
    title: qsTr("Connection")

    function stateLabel(state) {
        const labels = {
            "connected": qsTr("Connected"),
            "connecting": qsTr("Connecting…"),
            "disconnecting": qsTr("Disconnecting…"),
            "disconnected": qsTr("Not connected"),
            "error": qsTr("Connection error"),
            "starting": qsTr("Starting backend…"),
            "unavailable": qsTr("Backend unavailable")
        }
        return labels[state] ?? state
    }

    function stateColor(state) {
        if (state === "connected") {
            return Kirigami.Theme.positiveTextColor
        }
        if (state === "error" || state === "unavailable") {
            return Kirigami.Theme.negativeTextColor
        }
        return Kirigami.Theme.neutralTextColor
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !vpnController.backendAvailable || vpnController.message.length > 0
            type: vpnController.state === "error"
                  ? Kirigami.MessageType.Error
                  : Kirigami.MessageType.Information
            text: vpnController.message.length > 0
                  ? vpnController.message
                  : qsTr("Start the backend service to manage Proton VPN")
        }

        Item { Layout.fillHeight: true }

        Kirigami.Icon {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: Kirigami.Units.gridUnit * 7
            implicitHeight: implicitWidth
            source: vpnController.state === "connected"
                    ? "security-high"
                    : "network-vpn"
            color: page.stateColor(vpnController.state)
        }

        Kirigami.Heading {
            Layout.alignment: Qt.AlignHCenter
            level: 1
            text: page.stateLabel(vpnController.state)
            color: page.stateColor(vpnController.state)
        }

        Controls.Label {
            Layout.alignment: Qt.AlignHCenter
            visible: vpnController.serverName.length > 0
            text: vpnController.serverName
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.15
        }

        Controls.Label {
            Layout.alignment: Qt.AlignHCenter
            visible: vpnController.ready && !vpnController.loggedIn
            text: qsTr("Sign in to connect with your Proton account")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.Button {
            Layout.alignment: Qt.AlignHCenter
            visible: vpnController.ready && !vpnController.loggedIn
            text: qsTr("Sign in")
            icon.name: "system-log-in"
            highlighted: true
            onClicked: applicationWindow().showPage(
                Qt.resolvedUrl("SignInPage.qml"))
        }

        Controls.Button {
            Layout.alignment: Qt.AlignHCenter
            Layout.minimumWidth: Kirigami.Units.gridUnit * 12
            text: vpnController.busy ? qsTr("Working…")
                                     : vpnController.primaryActionText
            icon.name: vpnController.state === "connected"
                       ? "network-disconnect"
                       : "network-connect"
            enabled: vpnController.primaryActionEnabled
            highlighted: vpnController.state !== "connected"
            onClicked: vpnController.activatePrimaryAction()
        }

        Controls.BusyIndicator {
            Layout.alignment: Qt.AlignHCenter
            running: vpnController.busy
            visible: running
        }

        Item { Layout.fillHeight: true }

        Kirigami.Card {
            Layout.fillWidth: true
            contentItem: ColumnLayout {
                spacing: Kirigami.Units.smallSpacing

                Controls.Label {
                    text: qsTr("Native Plasma milestone")
                    font.bold: true
                }
                Controls.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: qsTr("Native sign-in, server selection, recovery, and Plasma integration. Proton's official core continues to own networking and security behavior.")
                    color: Kirigami.Theme.disabledTextColor
                }
                Controls.Button {
                    Layout.alignment: Qt.AlignRight
                    text: qsTr("Browse servers")
                    icon.name: "network-server"
                    enabled: vpnController.loggedIn
                    onClicked: {
                        applicationWindow().pageStack.clear()
                        applicationWindow().pageStack.push(
                            Qt.resolvedUrl("LocationsPage.qml"))
                    }
                }
            }
        }
    }
}
