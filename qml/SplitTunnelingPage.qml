// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Split tunneling rules")

    property var splitSettings: vpnController.splitTunneling
    property var vpnSettings: vpnController.settings
    readonly property bool protocolCompatible:
        vpnSettings.protocol === "wireguard"
        || vpnSettings.protocol.indexOf("protun-") === 0
    readonly property bool configurationEditable:
        !splitSettings.enabled
        || (protocolCompatible && vpnSettings.killSwitch === 0)

    Component.onCompleted: {
        if (vpnController.loggedIn && !vpnSettings.loaded) {
            vpnController.loadSettings()
        }
        if (vpnController.loggedIn && !splitSettings.loaded) {
            vpnController.loadSplitTunneling()
        }
    }

    Component.onDestruction: vpnController.setApplicationFilter("")

    ListView {
        id: applicationList
        model: vpnController.applicationModel
        spacing: Kirigami.Units.smallSpacing

        header: ColumnLayout {
            width: applicationList.width
            spacing: Kirigami.Units.largeSpacing

            PageHeader {
                heading: qsTr("Split tunneling rules")
                description: qsTr("Choose which applications and addresses use the VPN tunnel.")
                iconName: "applications-all"
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: splitSettings.message.length > 0
                type: Kirigami.MessageType.Error
                text: splitSettings.message
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: splitSettings.enabled
                         && (vpnSettings.killSwitch !== 0
                             || !page.protocolCompatible)
                type: Kirigami.MessageType.Warning
                text: qsTr("Turn split tunneling off before editing application rules, or resolve the protocol and kill-switch conflict in Settings.")
            }

            Controls.Switch {
                text: qsTr("Enable split tunneling")
                checked: splitSettings.enabled
                enabled: splitSettings.loaded && splitSettings.available
                         && splitSettings.paidFeaturesAvailable
                         && !splitSettings.busy
                         && (checked || (vpnSettings.killSwitch === 0
                                         && page.protocolCompatible))
                onClicked: vpnController.updateSplitTunneling("enabled", checked)
            }

            RowLayout {
                Layout.fillWidth: true

                Controls.Label {
                    text: qsTr("Mode:")
                }

                Controls.ComboBox {
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
                             && page.configurationEditable
                    onActivated: vpnController.updateSplitTunneling(
                        "mode", currentValue)
                }
            }

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: splitSettings.mode === "include"
                      ? qsTr("Only the selected applications use the VPN tunnel.")
                      : qsTr("Selected applications bypass the VPN tunnel.")
                color: Kirigami.Theme.disabledTextColor
            }

            RowLayout {
                Layout.fillWidth: true

                Controls.TextField {
                    id: ipRangeInput
                    Layout.fillWidth: true
                    placeholderText: qsTr("IP address or CIDR range, e.g. 10.0.0.0/8")
                    enabled: splitSettings.loaded && !splitSettings.busy
                             && page.configurationEditable
                    onAccepted: vpnController.addSplitTunnelingIpRange(text)
                }

                Controls.Button {
                    text: qsTr("Add IP rule")
                    icon.name: "list-add"
                    enabled: ipRangeInput.enabled
                             && ipRangeInput.text.trim().length > 0
                    onClicked: vpnController.addSplitTunnelingIpRange(
                        ipRangeInput.text)
                }
            }

            RowLayout {
                Layout.fillWidth: true
                visible: splitSettings.selectedIpRanges.length > 0

                Controls.Label {
                    Layout.fillWidth: true
                    text: qsTr("Selected IP ranges")
                    font.bold: true
                }

                Controls.Button {
                    text: qsTr("Clear")
                    icon.name: "edit-clear-all"
                    enabled: !splitSettings.busy
                             && page.configurationEditable
                    onClicked: vpnController.clearSplitTunnelingIpRanges()
                }
            }

            Repeater {
                model: splitSettings.selectedIpRanges

                delegate: RowLayout {
                    id: selectedIpRangeDelegate
                    required property string modelData
                    Layout.fillWidth: true

                    Kirigami.Icon {
                        source: "network-wired"
                        implicitWidth: Kirigami.Units.iconSizes.small
                        implicitHeight: implicitWidth
                    }

                    Controls.Label {
                        Layout.fillWidth: true
                        text: selectedIpRangeDelegate.modelData
                        font.family: "monospace"
                    }

                    Controls.ToolButton {
                        icon.name: "list-remove"
                        text: qsTr("Remove")
                        display: Controls.AbstractButton.IconOnly
                        enabled: !splitSettings.busy
                                 && page.configurationEditable
                        onClicked: vpnController.removeSplitTunnelingIpRange(
                            selectedIpRangeDelegate.modelData)

                        Controls.ToolTip.visible: hovered
                        Controls.ToolTip.text: text
                    }
                }
            }

            Kirigami.Separator {
                Layout.fillWidth: true
                visible: splitSettings.selectedIpRanges.length > 0
            }

            Controls.Label {
                Layout.fillWidth: true
                visible: splitSettings.mode === "include"
                         && splitSettings.selectedAppPaths.length === 0
                         && splitSettings.selectedIpRangeCount === 0
                wrapMode: Text.WordWrap
                text: qsTr("Choose at least one application or IP range before enabling include-only mode.")
                color: Kirigami.Theme.neutralTextColor
            }

            RowLayout {
                Layout.fillWidth: true
                visible: splitSettings.selectedAppPaths.length > 0

                Controls.Label {
                    Layout.fillWidth: true
                    text: qsTr("Selected applications")
                    font.bold: true
                }

                Controls.Button {
                    text: qsTr("Clear")
                    icon.name: "edit-clear-all"
                    enabled: !splitSettings.busy
                             && page.configurationEditable
                    onClicked: vpnController.clearSplitTunnelingApplications()
                }
            }

            Repeater {
                model: splitSettings.selectedAppPaths

                delegate: RowLayout {
                    id: selectedApplicationDelegate
                    required property string modelData
                    Layout.fillWidth: true

                    Kirigami.Icon {
                        source: "application-x-executable"
                        implicitWidth: Kirigami.Units.iconSizes.small
                        implicitHeight: implicitWidth
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0

                        Controls.Label {
                            Layout.fillWidth: true
                            text: vpnController.applicationName(
                                selectedApplicationDelegate.modelData)
                            elide: Text.ElideRight
                        }

                        Controls.Label {
                            Layout.fillWidth: true
                            text: selectedApplicationDelegate.modelData
                            elide: Text.ElideMiddle
                            color: Kirigami.Theme.disabledTextColor
                        }
                    }

                    Controls.ToolButton {
                        icon.name: "list-remove"
                        text: qsTr("Remove")
                        display: Controls.AbstractButton.IconOnly
                        enabled: !splitSettings.busy
                                 && page.configurationEditable
                        onClicked: vpnController.setSplitTunnelingApplication(
                            selectedApplicationDelegate.modelData, false)

                        Controls.ToolTip.visible: hovered
                        Controls.ToolTip.text: text
                    }
                }
            }

            Controls.Label {
                Layout.fillWidth: true
                text: qsTr("Installed applications")
                font.bold: true
            }

            Kirigami.SearchField {
                Layout.fillWidth: true
                placeholderText: qsTr("Search applications")
                onTextChanged: vpnController.setApplicationFilter(text)
            }

            Kirigami.Separator {
                Layout.fillWidth: true
            }
        }

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            visible: applicationList.count === 0
            text: qsTr("No matching applications")
            icon.name: "edit-find"
        }

        delegate: Controls.CheckDelegate {
            id: applicationDelegate
            required property string applicationName
            required property string executable
            required property string iconName
            required property string applicationComment

            width: ListView.view.width
            text: applicationDelegate.applicationName
            checked: splitSettings.containsApplication(
                applicationDelegate.executable)
            enabled: splitSettings.loaded && splitSettings.available
                     && splitSettings.paidFeaturesAvailable
                     && !splitSettings.busy
                     && page.configurationEditable
            icon.name: applicationDelegate.iconName.length > 0
                       ? applicationDelegate.iconName
                       : "application-x-executable"
            onClicked: vpnController.setSplitTunnelingApplication(
                applicationDelegate.executable, checked)

            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text:
                applicationDelegate.applicationComment.length > 0
                ? applicationDelegate.applicationComment + "\n"
                  + applicationDelegate.executable
                : applicationDelegate.executable
        }
    }
}
