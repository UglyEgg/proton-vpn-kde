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
            text: "0.8.8"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Remove native page-navigation and shutdown diagnostics, add an automated every-page runtime check, and warn when the installed Proton Core no longer contains the verified server-list memory optimizations. VPN behavior remains owned by Proton Core.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.8.7"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Harden the on-demand backend with private temporary storage, read-only system directories, and prevention of privilege gain while preserving Proton networking and user-selected capture folders.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.8.6"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Make full-cache country, city, and server search effectively instantaneous with a compact projection that keeps live VPN state in Proton's official core.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.8.2"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Keep exactly one Proton backend active, preserve supervision while connected, and release the full Python core shortly after the last Plasma client exits while disconnected. Location data is now constructed only when it is opened.")
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
