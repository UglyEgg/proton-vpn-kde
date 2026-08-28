import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    title: qsTr("Release Notes")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.Heading {
            level: 1
            text: qsTr("Development build after 0.8.1")
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("• Browse Proton locations, Secure Core routes, Tor servers, Smart Routing locations, and individual servers.\n• Pin preferred countries and servers to the Plasma system tray and configure auto-connect.\n• View live connection features and copy an assigned port-forwarding port.\n• Edit split-tunneling IP ranges as well as applications.\n• Create protocol-supported troubleshooting captures.\n• Send protected issue reports through Proton's official support API.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.8.1"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Restart the D-Bus backend after package upgrades so the frontend and backend interface remain synchronized.")
        }

        Kirigami.Heading {
            level: 2
            text: "0.8.0"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Add native custom DNS editing with IPv4 and IPv6 validation and explicit NetShield conflict handling.")
        }

        Kirigami.Heading {
            level: 2
            text: "0.7.0"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Add native split-tunneling controls and a Plasma application chooser backed by KDE's application catalog.")
        }

        Kirigami.Heading {
            level: 2
            text: "0.6.0"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Add conflict-aware native controls for Proton VPN connection and privacy settings.")
        }
    }
}
