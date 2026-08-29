import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    title: qsTr("About")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        PageHeader {
            heading: qsTr("Proton VPN for Plasma")
            description: qsTr("Version %1").arg(appVersion)
            iconName: "proton-vpn-kde"
        }

        SectionCard {
            title: qsTr("Native Plasma client")
            description: qsTr("A native KDE Plasma client using Proton's official VPN core")
            iconName: "plasma"

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("The Qt and Kirigami frontend is independent community work. Networking, VPN protocols, account sessions, kill switch, and split tunneling remain provided by Proton's official open-source Linux core.")
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
                    text: qsTr("Support")
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
