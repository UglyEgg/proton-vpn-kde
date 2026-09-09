// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    id: section
    objectName: "startupSettingsSection"
    required property var appSettings
    required property real pageWidth
    property bool choosingCustomTarget: false
    readonly property var loginStartup: appSettings.autostart
    title: qsTr("Startup")
    description: qsTr("Choose when Plasma VPN starts, what opens, and whether it connects.")
    iconName: "system-run"

    Component.onCompleted: loginStartup.refresh()
    onVisibleChanged: if (visible && loginStartup) loginStartup.refresh()

    Connections {
        target: section.appSettings
        function onAutoConnectTargetChanged() { section.choosingCustomTarget = false }
    }

    Kirigami.FormLayout {
        Layout.fillWidth: true
        wideMode: section.pageWidth >= Kirigami.Units.gridUnit * 36

        Controls.Switch {
            objectName: "startAtLoginSwitch"
            Kirigami.FormData.label: qsTr("At login:")
            text: qsTr("Start Plasma VPN when I log in")
            checked: section.loginStartup.enabled
            enabled: section.loginStartup.configurable
            onToggled: section.loginStartup.enabled = checked
        }

        Kirigami.InlineMessage {
            objectName: "autostartSaveError"
            Layout.fillWidth: true
            visible: section.loginStartup.errorMessage.length > 0
            type: Kirigami.MessageType.Warning
            text: section.loginStartup.errorMessage
        }

        Controls.ComboBox {
            objectName: "startupPresentation"
            Kirigami.FormData.label: qsTr("On startup:")
            Layout.fillWidth: true
            model: [qsTr("Open the window"), qsTr("System tray only")]
            currentIndex: section.appSettings.startMinimized && section.appSettings.closeToTray ? 1 : 0
            onActivated: index => {
                section.appSettings.startMinimized = index === 1
                if (index === 1) {
                    section.appSettings.closeToTray = true
                }
            }
        }

        Controls.Switch {
            objectName: "keepTrayControlsSwitch"
            Kirigami.FormData.label: qsTr("After closing:")
            text: qsTr("Keep system tray controls available")
            checked: section.appSettings.closeToTray
            onToggled: {
                if (!checked) {
                    section.appSettings.startMinimized = false
                }
                section.appSettings.closeToTray = checked
            }
        }

        Controls.Label {
            objectName: "trayStartupHelp"
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
            visible: section.appSettings.startMinimized && section.appSettings.closeToTray
            wrapMode: Text.WordWrap
            text: qsTr("Use the tray icon or application launcher to open the window.")
        }

        Controls.ComboBox {
            objectName: "startupAutoConnect"
            Kirigami.FormData.label: qsTr("Auto-connect:")
            Layout.fillWidth: true
            model: [qsTr("Off"), qsTr("Fastest suitable server"), qsTr("Country or exact server")]
            currentIndex: section.choosingCustomTarget ? 2
                          : section.appSettings.autoConnectTarget.length === 0 ? 0
                          : section.appSettings.autoConnectTarget === "FASTEST" ? 1 : 2
            onActivated: index => {
                if (index === 0) {
                    section.appSettings.autoConnectTarget = ""
                } else if (index === 1) {
                    section.appSettings.autoConnectTarget = "FASTEST"
                } else if (section.appSettings.autoConnectTarget === "FASTEST") {
                    section.appSettings.autoConnectTarget = ""
                }
                section.choosingCustomTarget = index === 2
            }
        }

        Controls.TextField {
            objectName: "startupCustomTarget"
            Kirigami.FormData.label: qsTr("Target:")
            Layout.fillWidth: true
            visible: section.choosingCustomTarget
                     || (section.appSettings.autoConnectTarget.length > 0
                         && section.appSettings.autoConnectTarget !== "FASTEST")
            text: section.appSettings.autoConnectTarget === "FASTEST" ? "" : section.appSettings.autoConnectTarget
            placeholderText: qsTr("Country code or server ID, e.g. US or CH#101")
            Accessible.name: qsTr("Auto-connect country code or server ID")
            onEditingFinished: {
                section.appSettings.autoConnectTarget = text
                text = Qt.binding(() => section.appSettings.autoConnectTarget === "FASTEST"
                                  ? "" : section.appSettings.autoConnectTarget)
                section.choosingCustomTarget = false
            }
        }

        Controls.Label {
            objectName: "autoConnectHelp"
            Layout.fillWidth: true
            Layout.maximumWidth: Kirigami.Units.gridUnit * 26
            visible: section.choosingCustomTarget || section.appSettings.autoConnectTarget.length > 0
            wrapMode: Text.WordWrap
            text: section.appSettings.autoConnectTarget === "FASTEST"
                  ? qsTr("Uses your selected server capabilities. You must be signed in; your secret store may ask for approval.")
                  : section.appSettings.autoConnectTarget.length > 0
                    ? qsTr("You must be signed in; your secret store may ask for approval.")
                    : qsTr("Enter a target to enable auto-connect.")
        }
    }
}
