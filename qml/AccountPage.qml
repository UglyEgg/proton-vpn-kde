import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Account")

    Kirigami.FormLayout {
        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Proton account")
        }

        Controls.Label {
            Kirigami.FormData.label: qsTr("Account:")
            text: vpnController.accountName
            font.bold: true
        }

        Controls.Label {
            Kirigami.FormData.label: qsTr("VPN plan:")
            text: vpnController.planTitle.length > 0
                  ? vpnController.planTitle : qsTr("Free")
        }

        Controls.Label {
            Kirigami.FormData.label: qsTr("Connections:")
            text: qsTr("Up to %1 devices").arg(vpnController.maxConnections)
        }

        Controls.Button {
            Kirigami.FormData.label: qsTr("Online:")
            text: qsTr("Manage Proton account")
            icon.name: "internet-web-browser"
            onClicked: Qt.openUrlExternally("https://account.proton.me/")
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Session")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Warning
            visible: vpnController.state !== "disconnected"
            text: qsTr("Signing out will disconnect the active VPN tunnel.")
        }

        Controls.Button {
            text: vpnController.busy ? qsTr("Signing out…") : qsTr("Sign out")
            icon.name: "system-log-out"
            enabled: !vpnController.busy
            onClicked: logoutDialog.open()
        }
    }

    Controls.Dialog {
        id: logoutDialog
        anchors.centerIn: parent
        title: qsTr("Sign out of Proton VPN?")
        modal: true
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.Cancel

        Controls.Label {
            width: Kirigami.Units.gridUnit * 20
            wrapMode: Text.WordWrap
            text: vpnController.state === "disconnected"
                  ? qsTr("The saved Proton session will be removed from your Secret Service provider.")
                  : qsTr("The VPN tunnel will be disconnected and the saved Proton session will be removed from your Secret Service provider.")
        }

        onAccepted: vpnController.logout()
    }
}
