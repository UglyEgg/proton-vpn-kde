// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    id: section

    required property var appSettings
    required property real pageWidth
    readonly property var iconStyleOptions: [
        { "label": qsTr("Color"), "value": "color" },
        { "label": qsTr("Light symbol"), "value": "light" },
        { "label": qsTr("Dark symbol"), "value": "dark" }
    ]

    function iconStyleIndex(style) {
        for (let index = 0; index < iconStyleOptions.length; ++index) {
            if (iconStyleOptions[index].value === style) {
                return index
            }
        }
        return 0
    }

    title: qsTr("Plasma integration")
    description: qsTr("Configure the resident tray agent and desktop behavior.")
    iconName: "preferences-desktop"

    Kirigami.FormLayout {
        Layout.fillWidth: true
        wideMode: pageWidth >= Kirigami.Units.gridUnit * 36

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Notifications:")
            text: qsTr("Show connection notifications")
            checked: appSettings.notificationsEnabled
            onToggled: appSettings.notificationsEnabled = checked
        }

        Controls.ComboBox {
            Kirigami.FormData.label: qsTr("Interface icon:")
            Layout.fillWidth: true
            model: section.iconStyleOptions
            textRole: "label"
            valueRole: "value"
            currentIndex: section.iconStyleIndex(appSettings.iconStyle)
            Accessible.name: qsTr("Interface icon style")
            onActivated: appSettings.iconStyle = currentValue
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: qsTr("Choose the color mark or a fixed light or dark symbol for the Control Center and system tray. The application launcher keeps the color mark for reliable visibility.")
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Window:")
            text: qsTr("Keep Plasma tray controls available after closing")
            checked: appSettings.closeToTray
            onToggled: appSettings.closeToTray = checked
        }

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Startup:")
            text: qsTr("Open only the Plasma tray controls at startup")
            checked: appSettings.startMinimized
            onToggled: appSettings.startMinimized = checked
        }

        Controls.TextField {
            Kirigami.FormData.label: qsTr("Pinned countries and servers:")
            Layout.fillWidth: true
            text: appSettings.pinnedServersText
            placeholderText: qsTr("US, CH#101, NL#42")
            onEditingFinished: {
                appSettings.pinnedServersText = text
                text = appSettings.pinnedServersText
            }
        }

        Controls.TextField {
            Kirigami.FormData.label: qsTr("Pinned locations:")
            Layout.fillWidth: true
            readOnly: true
            text: appSettings.pinnedServerGroupsText
            placeholderText: qsTr("Pin states or cities from the Locations browser")
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: qsTr("Pinned countries, states, cities, and exact servers appear as one-click connections in the Plasma system tray.")
            color: Kirigami.Theme.disabledTextColor
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: appSettings.startMinimized
            type: Kirigami.MessageType.Information
            text: qsTr("Enable application autostart separately in Plasma System Settings. The full Control Center is not kept in memory.")
        }
    }
}
