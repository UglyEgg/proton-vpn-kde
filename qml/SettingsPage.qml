import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Settings")

    Kirigami.FormLayout {
        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Connection")
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Recovery:")
            text: qsTr("Reconnect dropped VPN tunnels")
            checked: appSettings.reconnectEnabled
            onToggled: appSettings.reconnectEnabled = checked
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: qsTr("Retries the same Proton server after an unexpected drop. This never connects a deliberately disconnected VPN.")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Plasma integration")
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Notifications:")
            text: qsTr("Show connection notifications")
            checked: appSettings.notificationsEnabled
            onToggled: appSettings.notificationsEnabled = checked
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Window:")
            text: qsTr("Keep running in the system tray when closed")
            checked: appSettings.closeToTray
            onToggled: appSettings.closeToTray = checked
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Startup:")
            text: qsTr("Start with the window hidden")
            checked: appSettings.startMinimized
            onToggled: appSettings.startMinimized = checked
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: appSettings.startMinimized
            type: Kirigami.MessageType.Information
            text: qsTr("This controls window visibility only. Enable application autostart separately in Plasma System Settings.")
        }
    }
}
