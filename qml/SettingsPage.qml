import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Dialogs as Dialogs
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Settings")

    property var vpnSettings: vpnController.settings
    property var splitSettings: vpnController.splitTunneling
    property var customDns: vpnController.customDns
    readonly property bool splitProtocolCompatible:
        vpnSettings.protocol === "wireguard"
        || vpnSettings.protocol.indexOf("protun-") === 0
    readonly property bool splitConfigurationEditable:
        !splitSettings.enabled
        || (splitProtocolCompatible && vpnSettings.killSwitch === 0)
    property var packetCaptureFolderDialog: null

    Component {
        id: packetCaptureFolderDialogComponent

        Dialogs.FolderDialog {
            title: qsTr("Select packet capture folder")
            onAccepted: appSettings.setPacketCaptureDirectoryUrl(selectedFolder)
        }
    }

    function openPacketCaptureFolderDialog() {
        if (packetCaptureFolderDialog === null) {
            packetCaptureFolderDialog =
                packetCaptureFolderDialogComponent.createObject(page)
        }
        packetCaptureFolderDialog.open()
    }

    Controls.Dialog {
        id: updateChannelDialog
        property bool enableBeta: false
        anchors.centerIn: parent
        modal: true
        title: enableBeta ? qsTr("Enable Beta access?")
                          : qsTr("Disable Beta access?")
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.Cancel

        Controls.Label {
            width: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: updateChannelDialog.enableBeta
                  ? qsTr("This will replace Proton's stable Fedora repository package with its Beta repository package. Install the offered updates afterward to use Beta components.")
                  : qsTr("This will replace Proton's Beta Fedora repository package with its stable repository package. Install the offered updates afterward to return to stable components.")
        }

        onAccepted: updateChannel.setBetaEnabled(enableBeta)
    }

    Component.onDestruction: {
        if (vpnController.packetCaptureActive) {
            vpnController.stopPacketCapture()
        }
        if (packetCaptureFolderDialog !== null) {
            packetCaptureFolderDialog.destroy()
        }
    }

    Component.onCompleted: {
        if (vpnController.loggedIn && !vpnSettings.loaded) {
            vpnController.loadSettings()
        }
        if (vpnController.loggedIn && !splitSettings.loaded) {
            vpnController.loadSplitTunneling()
        }
        if (vpnController.loggedIn && !customDns.loaded) {
            vpnController.loadCustomDns()
        }
        updateChannel.refresh()
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
            if (vpnController.loggedIn && !page.customDns.loaded
                    && !page.customDns.busy) {
                vpnController.loadCustomDns()
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

        Controls.TextField {
            Kirigami.FormData.label: qsTr("Auto connect:")
            Layout.fillWidth: true
            text: appSettings.autoConnectTarget
            placeholderText: qsTr("Off, FASTEST, US, or CH#101")
            onEditingFinished: {
                appSettings.autoConnectTarget = text
                text = appSettings.autoConnectTarget
            }
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: qsTr("Connect to the fastest server, a country, or an exact server when the app starts.")
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
            text: qsTr("Custom DNS")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.message.length > 0
            type: Kirigami.MessageType.Error
            text: customDns.message
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("DNS:")
            text: qsTr("Use custom DNS servers")
            checked: customDns.enabled
            enabled: customDns.loaded && customDns.paidFeaturesAvailable
                     && !customDns.busy
                     && (checked || vpnSettings.netShield === 0)
            onClicked: vpnController.updateCustomDns("enabled", checked)
        }

        Controls.Button {
            Kirigami.FormData.label: qsTr("Servers:")
            text: customDns.serverCount > 0
                  ? qsTr("Manage %n server(s)…", "", customDns.serverCount)
                  : qsTr("Add DNS servers…")
            icon.name: "network-server-database"
            enabled: customDns.loaded && customDns.paidFeaturesAvailable
                     && !customDns.busy
            onClicked: applicationWindow().pushCustomDns()
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.restartRequired
            type: Kirigami.MessageType.Information
            text: qsTr("Reconnect the VPN to apply the custom DNS changes.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.loaded && vpnSettings.loaded
                     && vpnSettings.netShield !== 0
            type: Kirigami.MessageType.Warning
            text: qsTr("Disable NetShield before enabling custom DNS. Neither setting will be changed automatically.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.loaded && !customDns.paidFeaturesAvailable
            type: Kirigami.MessageType.Information
            text: qsTr("Custom DNS requires a paid Proton VPN plan.")
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
            text: qsTr("Choose applications and IP ranges…")
            icon.name: "applications-all"
            enabled: splitSettings.loaded && splitSettings.available
                     && splitSettings.paidFeaturesAvailable
                     && !splitSettings.busy
                     && page.splitConfigurationEditable
            onClicked: applicationWindow().pushSplitTunneling()
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
            text: qsTr("%n IP rule(s) are configured in this mode.",
                       "", splitSettings.selectedIpRangeCount)
            color: Kirigami.Theme.disabledTextColor
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
            visible: vpnSettings.packetCaptureSupported
            text: qsTr("Troubleshooting capture")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnSettings.packetCaptureSupported
            type: Kirigami.MessageType.Warning
            text: qsTr("A packet capture records all internet activity during the capture session. Only create one when diagnosing a specific problem, and review it before sharing.")
        }

        RowLayout {
            Layout.fillWidth: true
            visible: vpnSettings.packetCaptureSupported

            Controls.Label {
                Layout.fillWidth: true
                text: appSettings.packetCaptureDirectory
                elide: Text.ElideMiddle
                color: Kirigami.Theme.disabledTextColor
            }

            Controls.Button {
                text: qsTr("Browse…")
                icon.name: "folder-open"
                enabled: !vpnController.packetCaptureActive
                onClicked: page.openPacketCaptureFolderDialog()
            }

            Controls.Button {
                text: vpnController.packetCaptureActive
                      ? qsTr("Stop capture")
                      : qsTr("Start capture")
                icon.name: vpnController.packetCaptureActive
                           ? "media-playback-stop"
                           : "media-record"
                highlighted: vpnController.packetCaptureActive
                enabled: !vpnController.busy
                         && (vpnController.packetCaptureActive
                             || vpnController.state === "connected")
                onClicked: {
                    if (vpnController.packetCaptureActive) {
                        vpnController.stopPacketCapture()
                    } else {
                        vpnController.startPacketCapture(
                            appSettings.packetCaptureDirectory)
                    }
                }
            }
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: vpnSettings.packetCaptureSupported
                     && vpnController.state !== "connected"
            text: qsTr("Connect the VPN before starting a troubleshooting capture.")
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

        Controls.TextField {
            Kirigami.FormData.label: qsTr("Tray favorites:")
            Layout.fillWidth: true
            text: appSettings.pinnedServersText
            placeholderText: qsTr("US, CH#101, NL#42")
            onEditingFinished: {
                appSettings.pinnedServersText = text
                text = appSettings.pinnedServersText
            }
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: qsTr("Favorite countries and servers appear as one-click connections in the Plasma system tray.")
            color: Kirigami.Theme.disabledTextColor
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: appSettings.startMinimized
            type: Kirigami.MessageType.Information
            text: qsTr("This controls window visibility only. Enable application autostart separately in Plasma System Settings.")
        }

        Controls.Label {
            Kirigami.FormData.isSection: true
            visible: updateChannel.available
            text: qsTr("Updates")
        }

        RowLayout {
            Layout.fillWidth: true
            visible: updateChannel.available

            Controls.Switch {
                id: betaAccessSwitch
                text: qsTr("Beta access")
                checked: updateChannel.betaEnabled
                enabled: !updateChannel.busy
                onClicked: {
                    updateChannelDialog.enableBeta = !updateChannel.betaEnabled
                    checked = Qt.binding(function() {
                        return updateChannel.betaEnabled
                    })
                    updateChannelDialog.open()
                }
            }

            Controls.BusyIndicator {
                visible: updateChannel.busy
                running: visible
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
            }
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: updateChannel.available
            text: qsTr("Selects Proton's Fedora package repository. Package installation remains managed by Discover or dnf.")
            color: Kirigami.Theme.disabledTextColor
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: updateChannel.available
                     && updateChannel.message.length > 0
            type: updateChannel.error ? Kirigami.MessageType.Error
                                      : Kirigami.MessageType.Information
            text: updateChannel.message
        }
    }
}
