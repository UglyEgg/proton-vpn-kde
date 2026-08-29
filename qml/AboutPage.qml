import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("About")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Icon {
            Layout.alignment: Qt.AlignHCenter
            source: "proton-vpn-kde"
            implicitWidth: Kirigami.Units.iconSizes.huge
            implicitHeight: implicitWidth
        }

        Kirigami.Heading {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            level: 1
            text: qsTr("Proton VPN for Plasma")
        }

        Controls.Label {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: qsTr("Version %1").arg(appVersion)
            color: Kirigami.Theme.disabledTextColor
        }

        Controls.Label {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: qsTr("A native KDE Plasma client using Proton's official VPN core")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            Layout.fillWidth: true
            level: 2
            text: qsTr("About this client")
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("The Qt and Kirigami frontend is independent community work. Networking, VPN protocols, account sessions, kill switch, and split tunneling remain provided by Proton's official open-source Linux core.")
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter

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

        Kirigami.Heading {
            Layout.fillWidth: true
            level: 2
            text: qsTr("Author")
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: "uglyegg · uglyegg@entropy.quest\n"
                  + qsTr("Plasma client development")
        }

        Kirigami.Heading {
            Layout.fillWidth: true
            level: 2
            text: qsTr("License")
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
