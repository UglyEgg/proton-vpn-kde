// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page

    objectName: "secondaryInformationHub"
    title: qsTr("Help & information")
    readonly property real maximumContentWidth: Kirigami.Units.gridUnit * 32
    leftPadding: Math.max(Kirigami.Units.largeSpacing,
                          (width - maximumContentWidth) / 2)
    rightPadding: leftPadding

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        IdentityStage {
            heading: qsTr("Plasma VPN")
            description: qsTr("Proton VPN-compatible community client · Version %1 preview").arg(appVersion)
            iconSource: applicationWindow().appIconSource
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            type: Kirigami.MessageType.Information
            text: qsTr("Independent community software—not developed, reviewed, sponsored, or endorsed by Proton AG.")
        }

        SectionCard {
            title: qsTr("Help and project information")
            description: qsTr("Open details only when you need them.")
            iconName: "help-contents"

            PlasmaListItem {
                Layout.fillWidth: true
                text: qsTr("Release notes")
                subtitle: qsTr("What changed in this version and earlier releases")
                icon.name: "view-pim-notes"
                onClicked: applicationWindow().openOverviewDestination(
                    "release-notes")
            }

            PlasmaListItem {
                Layout.fillWidth: true
                text: qsTr("Help and reporting")
                subtitle: vpnController.supportReportSubmissionEnabled
                          ? qsTr("Support and direct-reporting options")
                          : qsTr("Community tracker · Direct Proton submission unavailable")
                icon.name: "tools-report-bug"
                onClicked: applicationWindow().openOverviewDestination(
                    "report-issue")
            }

            PlasmaListItem {
                Layout.fillWidth: true
                text: qsTr("Check local setup")
                subtitle: qsTr("Backend, Proton Core, and Secret Service availability")
                icon.name: "view-list-details"
                onClicked: applicationWindow().openOverviewDestination(
                    "readiness")
            }
        }

        SectionCard {
            title: qsTr("Native Plasma client")
            description: qsTr("A native KDE Plasma client using Proton's official VPN core")
            iconName: "plasma"

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Networking, VPN protocols, account sessions, kill switch, and split tunneling remain provided by Proton's official open-source Linux core.")
            }

            RowLayout {
                Layout.fillWidth: true
                Item { Layout.fillWidth: true }
                Controls.Button {
                    text: qsTr("Proton VPN website")
                    icon.name: "internet-web-browser"
                    onClicked: Qt.openUrlExternally("https://protonvpn.com/")
                }
                Controls.Button {
                    text: qsTr("Proton service support")
                    icon.name: "help-contents"
                    onClicked: Qt.openUrlExternally(
                        "https://protonvpn.com/support-form")
                }
            }
        }

        SectionCard {
            title: qsTr("Project")
            iconName: "applications-development"

            DetailRow {
                label: qsTr("Author")
                value: "uglyegg · uglyegg@entropy.quest"
            }

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("GNU General Public License, version 3 or later. The complete license is included with the source and installed package documentation.")
            }

            Controls.Label {
                Layout.fillWidth: true
                text: "© 2026 uglyegg and contributors"
                color: Kirigami.Theme.disabledTextColor
            }
        }
    }
}
