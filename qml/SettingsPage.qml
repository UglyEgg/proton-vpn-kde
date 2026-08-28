import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Settings")

    property var vpnSettings: vpnController.settings
    property var splitSettings: vpnController.splitTunneling
    readonly property bool splitProtocolCompatible:
        vpnSettings.protocol === "wireguard"
        || vpnSettings.protocol.indexOf("protun-") === 0
    readonly property bool splitConfigurationEditable:
        !splitSettings.enabled
        || (splitProtocolCompatible && vpnSettings.killSwitch === 0)

    Component.onCompleted: {
        if (vpnController.loggedIn && !vpnSettings.loaded) {
            vpnController.loadSettings()
        }
        if (vpnController.loggedIn && !splitSettings.loaded) {
            vpnController.loadSplitTunneling()
        }
    }

    Connections {
        target: vpnController
        function onSnapshotChanged() {
            if (vpnController.loggedIn && !page.vpnSettings.loaded
                    && !page.vpnSettings.busy) {
                vpnController.loadSettings()
            }
            if (vpnController.loggedIn && !page.splitSettings.loaded
                    && !page.splitSettings.busy) {
                vpnController.loadSplitTunneling()
            }
        }
    }

    Kirigami.FormLayout {
        wideMode: page.width >= Kirigami.Units.gridUnit * 28

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !vpnController.loggedIn
            type: Kirigami.MessageType.Information
            text: qsTr("Sign in to change Proton VPN settings.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnSettings.message.length > 0
            type: Kirigami.MessageType.Error
            text: vpnSettings.message
        }

        RowLayout {
            Layout.fillWidth: true
            visible: vpnController.loggedIn && vpnSettings.busy

            Controls.BusyIndicator {
                running: parent.visible
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
            }

            Controls.Label {
                text: qsTr("Updating VPN settings…")
                color: Kirigami.Theme.disabledTextColor
            }
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("VPN connection")
        }

        Controls.ComboBox {
            id: protocolCombo
            Kirigami.FormData.label: qsTr("Protocol:")
            Layout.fillWidth: true
            model: vpnSettings.protocolOptions
            textRole: "name"
            valueRole: "id"
            currentIndex: vpnSettings.protocolIndex
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.protocolEditable
            onActivated: vpnController.updateSetting("protocol", currentValue)
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: vpnSettings.loaded && !vpnSettings.protocolEditable
            text: qsTr("Disconnect the VPN to change protocols.")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.ComboBox {
            id: killSwitchCombo
            Kirigami.FormData.label: qsTr("Kill switch:")
            Layout.fillWidth: true
            model: [
                { "id": 0, "name": qsTr("Off") },
                { "id": 1, "name": qsTr("Standard") },
                { "id": 2, "name": qsTr("Permanent") }
            ]
            textRole: "name"
            valueRole: "id"
            currentIndex: vpnSettings.killSwitch
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.killSwitchEditable
            onActivated: vpnController.updateSetting("killSwitch", currentValue)
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: vpnSettings.loaded && !vpnSettings.killSwitchEditable
            text: qsTr("Disconnect the VPN to change kill-switch mode.")
            color: Kirigami.Theme.disabledTextColor
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
            text: qsTr("Protection and performance")
        }

        Controls.ComboBox {
            Kirigami.FormData.label: qsTr("NetShield:")
            Layout.fillWidth: true
            model: [
                { "id": 0, "name": qsTr("Off") },
                { "id": 1, "name": qsTr("Block malware") },
                { "id": 2, "name": qsTr("Block ads, trackers, and malware") }
            ]
            textRole: "name"
            valueRole: "id"
            currentIndex: vpnSettings.netShield
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.paidFeaturesAvailable
            onActivated: vpnController.updateSetting("netShield", currentValue)
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Performance:")
            text: qsTr("Enable VPN Accelerator")
            checked: vpnSettings.vpnAccelerator
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.paidFeaturesAvailable
            onClicked: vpnController.updateSetting("vpnAccelerator", checked)
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("NAT:")
            text: qsTr("Use moderate NAT")
            checked: vpnSettings.moderateNat
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.paidFeaturesAvailable
            onClicked: vpnController.updateSetting("moderateNat", checked)
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("P2P:")
            text: qsTr("Enable port forwarding")
            checked: vpnSettings.portForwarding
            enabled: vpnSettings.loaded && !vpnSettings.busy
                     && vpnSettings.paidFeaturesAvailable
            onClicked: vpnController.updateSetting("portForwarding", checked)
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("IPv6:")
            text: qsTr("Tunnel IPv6 traffic")
            checked: vpnSettings.ipv6
            enabled: vpnSettings.loaded && !vpnSettings.busy
            onClicked: vpnController.updateSetting("ipv6", checked)
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnSettings.loaded && !vpnSettings.paidFeaturesAvailable
            type: Kirigami.MessageType.Information
            text: qsTr("NetShield, VPN Accelerator, moderate NAT, and port forwarding require a paid Proton VPN plan.")
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Split tunneling")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.message.length > 0
            type: Kirigami.MessageType.Error
            text: splitSettings.message
        }

        RowLayout {
            Layout.fillWidth: true
            visible: vpnController.loggedIn && splitSettings.busy

            Controls.BusyIndicator {
                running: parent.visible
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
            }

            Controls.Label {
                text: qsTr("Updating split-tunneling settings…")
                color: Kirigami.Theme.disabledTextColor
            }
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Applications:")
            text: qsTr("Enable split tunneling")
            checked: splitSettings.enabled
            enabled: splitSettings.loaded && splitSettings.available
                     && splitSettings.paidFeaturesAvailable
                     && !splitSettings.busy
                     && (checked || (vpnSettings.killSwitch === 0
                                     && page.splitProtocolCompatible))
            onClicked: vpnController.updateSplitTunneling("enabled", checked)
        }

        Controls.ComboBox {
            id: splitModeCombo
            Kirigami.FormData.label: qsTr("Mode:")
            Layout.fillWidth: true
            model: [
                { "id": "exclude", "name": qsTr("Exclude selected apps") },
                { "id": "include", "name": qsTr("Only include selected apps") }
            ]
            textRole: "name"
            valueRole: "id"
            currentIndex: splitSettings.modeIndex
            enabled: splitSettings.loaded && splitSettings.available
                     && splitSettings.paidFeaturesAvailable
                     && !splitSettings.busy
                     && page.splitConfigurationEditable
            onActivated: vpnController.updateSplitTunneling("mode", currentValue)
        }

        Controls.Button {
            Kirigami.FormData.label: qsTr("Rules:")
            text: qsTr("Choose applications…")
            icon.name: "applications-all"
            enabled: splitSettings.loaded && splitSettings.available
                     && splitSettings.paidFeaturesAvailable
                     && !splitSettings.busy
                     && page.splitConfigurationEditable
            onClicked: applicationWindow().pageStack.push(
                Qt.resolvedUrl("SplitTunnelingPage.qml"))
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.loaded && !splitSettings.available
            type: Kirigami.MessageType.Information
            text: qsTr("The installed Proton VPN backend reports that split tunneling is unavailable on this system.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.loaded && splitSettings.available
                     && !splitSettings.paidFeaturesAvailable
            type: Kirigami.MessageType.Information
            text: qsTr("Split tunneling requires a paid Proton VPN plan.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.loaded && vpnSettings.loaded
                     && vpnSettings.killSwitch !== 0
            type: Kirigami.MessageType.Warning
            text: splitSettings.enabled
                  ? qsTr("Turn split tunneling off before editing its rules, or disable the kill switch first.")
                  : qsTr("Disable the kill switch before enabling split tunneling.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: splitSettings.loaded && vpnSettings.loaded
                     && !page.splitProtocolCompatible
            type: Kirigami.MessageType.Warning
            text: splitSettings.enabled
                  ? qsTr("Turn split tunneling off before editing its rules, or select WireGuard first.")
                  : qsTr("Select WireGuard or a compatible protocol before enabling split tunneling.")
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: splitSettings.loaded
                     && splitSettings.selectedIpRangeCount > 0
            text: qsTr("%n existing IP rule(s) in this mode are preserved. This editor changes application rules only.",
                       "", splitSettings.selectedIpRangeCount)
            color: Kirigami.Theme.disabledTextColor
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnSettings.customDnsEnabled
            type: Kirigami.MessageType.Information
            text: qsTr("Custom DNS is enabled. Conflicting NetShield changes remain blocked until its native editor is available.")
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            text: qsTr("Privacy")
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Diagnostics:")
            text: qsTr("Send anonymous crash reports")
            checked: vpnSettings.anonymousCrashReports
            enabled: vpnSettings.loaded && !vpnSettings.busy
            onClicked: vpnController.updateSetting("anonymousCrashReports", checked)
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
