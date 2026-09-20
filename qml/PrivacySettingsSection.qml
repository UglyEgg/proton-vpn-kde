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
            objectName: "crashReportSwitch"
            Kirigami.FormData.label: qsTr("Diagnostics:")
            text: qsTr("Send anonymous crash reports")
            checked: vpnController.crashReportSubmissionEnabled
                     && vpnSettings.anonymousCrashReports
            enabled: vpnController.crashReportSubmissionEnabled
                     && vpnController.ready
                     && vpnSettings.loaded && !vpnSettings.busy
            onClicked: vpnController.updateSetting("anonymousCrashReports", checked)
        }

        Controls.Switch {
            objectName: "connectionTelemetrySwitch"
            Kirigami.FormData.label: qsTr("Connection telemetry:")
            text: qsTr("Send connection outcome telemetry to Proton")
            checked: vpnController.telemetryEnabled && vpnSettings.telemetry
            enabled: vpnController.telemetryEnabled
                     && vpnController.ready
                     && vpnSettings.loaded && !vpnSettings.busy
            onClicked: vpnController.updateSetting("telemetry", checked)
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !vpnController.crashReportSubmissionEnabled
            type: Kirigami.MessageType.Warning
            text: qsTr("Anonymous crash reporting to Proton is disabled in this unofficial community build. Report Plasma VPN client crashes in the community project tracker.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !vpnController.telemetryEnabled
            type: Kirigami.MessageType.Information
            text: qsTr("Connection telemetry to Proton is disabled by this community build.")
        }

        Controls.Label {
            Layout.maximumWidth: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            visible: vpnController.telemetryEnabled
            text: vpnSettings.telemetry
                  ? qsTr("Enabled by you. Proton Core may send optional connection outcome events to Proton.")
                  : qsTr("Optional connection outcome telemetry is off. You can enable it explicitly.")
            color: Kirigami.Theme.disabledTextColor
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
                enabled: vpnController.ready
                         && !vpnController.packetCaptureActive
                onClicked: browseRequested()
            }

            Controls.Button {
                objectName: "packetCaptureAction"
                text: vpnController.packetCaptureActive
                      ? qsTr("Stop capture")
                      : qsTr("Start capture")
                icon.name: vpnController.packetCaptureActive
                           ? "media-playback-stop"
                           : "media-record"
                highlighted: vpnController.packetCaptureActive
                enabled: vpnController.backendAvailable && vpnController.ready
                         && (vpnController.packetCaptureActive
                             || (!vpnController.busy
                                 && vpnController.state === "connected"))
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
