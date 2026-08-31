// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    required property var appSettings

    title: qsTr("Default fastest server")
    description: qsTr("Require every checked capability whenever Connect fastest is used from the overview, tray, global shortcut, KRunner, or auto-connect.")
    iconName: "speedometer"

    ServerCapabilitySelector {
        Layout.fillWidth: true
        selectedFeatures: appSettings.fastestFeatures
        onSelectionChanged: function(features) {
            appSettings.fastestFeatures = features
        }
    }

    Controls.Label {
        Layout.fillWidth: true
        text: appSettings.fastestFeatures.length === 0
              ? qsTr("No default capability filter.")
              : qsTr("Proton Core will choose the fastest server matching all checked capabilities.")
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.WordWrap
    }
}
