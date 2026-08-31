// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    title: qsTr("Release Notes")

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        PageHeader {
            heading: qsTr("Release notes")
            description: qsTr("Changes in the Proton VPN-compatible Plasma client")
            iconName: "view-pim-notes"
        }

        SectionCard {
            title: qsTr("What's new")
            iconName: "software-properties"

        Kirigami.Heading {
            level: 1
            text: "0.11.3"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Restore reliable Plasma reconnects without depending on a missing Protun secret-agent plugin. When the Proton backend stops, the Control Center now clears stale account and tunnel state instead of continuing to appear signed in. If desktop Secret Service session restoration stalls, Sign in presents an explicit service retry rather than leaving an inert screen.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.11.2"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Choose a color mark, light symbol, or dark symbol for the Control Center and resident Plasma tray icon. The shared preference applies immediately and is also available in Plasma System Settings. Release Notes uses a distinct bound-notebook symbol in collapsed navigation. KRunner connection requests now require explicit Control Center confirmation and the shared plug-in host is not trusted by the VPN backend. Direct Proton support-report submission is disabled in unofficial builds; the reporting page remains an inactive proof of concept and directs client problems to the community tracker. Server browsing now retries transiently empty groups without requiring a manual refresh. Background-control shutdown distinguishes leaving a tunnel connected from waiting for a confirmed disconnect. The Control Center recovers from unexpected backend exits and clearly requests a restart when it was left open across a package upgrade.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.11.1"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Present an original Plasma VPN identity, make the Proton VPN-compatible community relationship explicit, and add reproducible public-release guidance. The application mark is now embedded, and Settings remains open after configuration changes.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.10.2"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Keep Settings open after applying VPN configuration changes instead of unexpectedly returning to Overview.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.10.1"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Open directly to sign-in when no Proton session is available, prevent credentials from racing backend startup, and explain when the desktop secret store may be awaiting access approval.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.10.0"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Adopt a responsive Plasma navigation sidebar, native Kirigami cards, compact location actions, semantic colors and typography, and layout checks for compact windows, scaled text, and right-to-left desktops.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
            text: "0.9.0"
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Keep tray controls, shortcuts, notifications, favorites, and auto-connect in a lean Plasma agent while the full Control Center opens only when needed and exits when closed. Closing the window does not disconnect the VPN.")
        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            level: 2
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
            text: qsTr("Harden the on-demand backend with absolute service paths, prevention of privilege gain, and explicit interpreter and loader environment cleanup while preserving Proton networking and user-selected capture folders.")
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
}
