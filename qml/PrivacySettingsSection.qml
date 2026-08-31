// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

SectionCard {
    required property var vpnController
    required property var vpnSettings
    required property var appSettings
    required property real pageWidth
    signal browseRequested()

    title: qsTr("Privacy and troubleshooting")
    description: qsTr("Control diagnostics and create a temporary support capture.")
    iconName: "preferences-desktop-privacy"

    Kirigami.FormLayout {
        Layout.fillWidth: true
        wideMode: pageWidth >= Kirigami.Units.gridUnit * 36

        Controls.Switch {
            Kirigami.FormData.label: qsTr("Diagnostics:")
            text: qsTr("Send anonymous crash reports")
            checked: vpnController.crashReportSubmissionEnabled
                     && vpnSettings.anonymousCrashReports
            enabled: vpnController.crashReportSubmissionEnabled
                     && vpnSettings.loaded && !vpnSettings.busy
            onClicked: vpnController.updateSetting("anonymousCrashReports", checked)
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !vpnController.crashReportSubmissionEnabled
            type: Kirigami.MessageType.Warning
            text: qsTr("Anonymous crash reporting to Proton is disabled in this unofficial community build. Report Plasma VPN client crashes in the community project tracker.")
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
                onClicked: browseRequested()
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
    }
}
