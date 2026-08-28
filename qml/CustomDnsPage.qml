pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Custom DNS servers")

    property var customDns: vpnController.customDns
    property var vpnSettings: vpnController.settings

    Component.onCompleted: {
        if (vpnController.loggedIn && !vpnSettings.loaded) {
            vpnController.loadSettings()
        }
        if (vpnController.loggedIn && !customDns.loaded) {
            vpnController.loadCustomDns()
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: customDns.message.length > 0
            type: Kirigami.MessageType.Error
            text: customDns.message
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

        RowLayout {
            Layout.fillWidth: true
            visible: customDns.busy

            Controls.BusyIndicator {
                running: parent.visible
                implicitWidth: Kirigami.Units.iconSizes.small
                implicitHeight: implicitWidth
            }

            Controls.Label {
                text: qsTr("Updating custom-DNS settings…")
                color: Kirigami.Theme.disabledTextColor
            }
        }

        Controls.Switch {
            text: qsTr("Use custom DNS servers")
            checked: customDns.enabled
            enabled: customDns.loaded && customDns.paidFeaturesAvailable
                     && !customDns.busy
                     && (checked || vpnSettings.netShield === 0)
            onClicked: vpnController.updateCustomDns("enabled", checked)
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Proton's networking core applies enabled addresses when it creates the next VPN connection.")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.Label {
            Layout.fillWidth: true
            text: qsTr("DNS servers")
            font.bold: true
        }

        RowLayout {
            Layout.fillWidth: true

            Controls.TextField {
                id: addressField
                Layout.fillWidth: true
                placeholderText: qsTr("IPv4 or IPv6 address")
                enabled: customDns.loaded && customDns.paidFeaturesAvailable
                         && !customDns.busy
                inputMethodHints: Qt.ImhNoPredictiveText
                onAccepted: {
                    if (customDns.isValidServerAddress(text)
                            && !customDns.containsServer(text)) {
                        vpnController.addCustomDnsServer(text)
                        clear()
                    }
                }
            }

            Controls.Button {
                text: qsTr("Add")
                icon.name: "list-add"
                enabled: addressField.enabled
                         && customDns.isValidServerAddress(addressField.text)
                         && !customDns.containsServer(addressField.text)
                onClicked: {
                    vpnController.addCustomDnsServer(addressField.text)
                    addressField.clear()
                }
            }
        }

        Controls.Label {
            Layout.fillWidth: true
            visible: addressField.text.length > 0
                     && !customDns.isValidServerAddress(addressField.text)
            wrapMode: Text.WordWrap
            text: qsTr("Enter a numeric IPv4 or IPv6 address, such as 1.1.1.1 or 2606:4700:4700::1111.")
            color: Kirigami.Theme.negativeTextColor
        }

        Kirigami.PlaceholderMessage {
            Layout.fillWidth: true
            visible: customDns.loaded && customDns.serverCount === 0
            text: qsTr("No custom DNS servers")
            explanation: qsTr("Add an address for Proton to use on the next connection.")
            icon.name: "network-server-database"
        }

        Repeater {
            model: customDns.servers

            delegate: Kirigami.AbstractCard {
                id: serverDelegate
                required property var modelData
                Layout.fillWidth: true

                contentItem: RowLayout {
                    Kirigami.Icon {
                        source: "network-server-database"
                        implicitWidth: Kirigami.Units.iconSizes.small
                        implicitHeight: implicitWidth
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        Controls.Label {
                            Layout.fillWidth: true
                            text: serverDelegate.modelData.address
                            font.family: "monospace"
                            elide: Text.ElideMiddle
                        }

                        Controls.Label {
                            Layout.fillWidth: true
                            visible: !serverDelegate.modelData.enabled
                            text: qsTr("Inactive entry preserved from Proton settings")
                            color: Kirigami.Theme.disabledTextColor
                        }
                    }

                    Controls.ToolButton {
                        icon.name: "list-remove"
                        text: qsTr("Remove")
                        display: Controls.AbstractButton.IconOnly
                        enabled: !customDns.busy
                                 && customDns.paidFeaturesAvailable
                        onClicked: vpnController.removeCustomDnsServer(
                            serverDelegate.modelData.address)

                        Controls.ToolTip.visible: hovered
                        Controls.ToolTip.text: text
                    }
                }
            }
        }
    }
}
