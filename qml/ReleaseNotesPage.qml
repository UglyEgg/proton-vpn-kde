// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    objectName: "releaseNotesPage"
    title: qsTr("Release Notes")
    readonly property real maximumContentWidth: Kirigami.Units.gridUnit * 34
    leftPadding: Math.max(Kirigami.Units.largeSpacing,
                          (width - maximumContentWidth) / 2)
    rightPadding: leftPadding

    component ReleaseNoteGroup: ColumnLayout {
        id: group

        property string heading
        property int headingLevel: 3
        property var notes: []

        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        Kirigami.Heading {
            Layout.fillWidth: true
            level: group.headingLevel
            text: group.heading
            wrapMode: Text.WordWrap
        }

        Repeater {
            model: group.notes

            delegate: RowLayout {
                id: noteDelegate

                required property string modelData

                Layout.fillWidth: true
                Layout.leftMargin: Kirigami.Units.smallSpacing
                spacing: Kirigami.Units.smallSpacing

                Controls.Label {
                    Layout.alignment: Qt.AlignTop
                    text: "\u2022"
                    color: Kirigami.Theme.highlightColor
                    Accessible.ignored: true
                }

                Controls.Label {
                    Layout.fillWidth: true
                    text: noteDelegate.modelData
                    wrapMode: Text.WordWrap
                }
            }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        PageHeader {
            heading: qsTr("Release notes")
            description: qsTr("Changes in the Proton VPN-compatible Plasma client")
            iconName: "view-pim-notes"
        }

        SectionCard {
            title: qsTr("What's new")
            description: qsTr("Unreleased 0.14.1 preview. Proton Core still handles your VPN.")
            iconName: "software-properties"

            Kirigami.Heading {
                Layout.fillWidth: true
                level: 3
                text: "0.14.1"
            }

            ReleaseNoteGroup {
                objectName: "currentReleaseHighlights"
                heading: qsTr("Highlights")
                headingLevel: 4
                notes: [
                    qsTr("Show the VPN exit address reported at connection time, with the device-side address labeled separately when split tunneling is active."),
                    qsTr("Check local Core, backend, package, and Secret Service readiness without opening your secret provider."),
                    qsTr("Preview a small, privacy-bounded community diagnostic report before choosing to copy it; direct Proton submission remains disabled."),
                    qsTr("Support Proton Core 5.7 on Fedora; optional connection telemetry remains off by default, clears queued events on opt-out, and is visible in Settings."),
                    qsTr("Keep the previous settings and snapshot contracts working while frontend and backend packages cross an in-place upgrade.")
                ]
            }

            Controls.Button {
                Layout.alignment: Qt.AlignLeft
                text: qsTr("Published 0.13.1 changelog (online)")
                icon.name: "internet-web-browser"
                Accessible.description: qsTr("Open the published 0.13.1 source changelog in your browser; preview changes are not published yet")
                onClicked: Qt.openUrlExternally(
                    "https://github.com/UglyEgg/proton-vpn-kde/blob/main/CHANGELOG.md")
            }
        }

        Controls.Button {
            id: previousReleasesToggle
            objectName: "previousReleasesToggle"

            Layout.alignment: Qt.AlignLeft
            checkable: true
            text: checked
                ? qsTr("Hide earlier versions")
                : qsTr("Show earlier versions")
            icon.name: checked ? "go-up-symbolic" : "go-down-symbolic"
            Accessible.description: qsTr("Expand or collapse notes for earlier releases and development milestones")
        }

        SectionCard {
            objectName: "previousReleaseHistory"
            visible: previousReleasesToggle.checked
            title: qsTr("Earlier versions")
            description: qsTr("Development milestones and published releases. The complete engineering history remains in CHANGELOG.md.")
            iconName: "view-history"

            ReleaseNoteGroup {
                heading: "0.13.1"
                headingLevel: 3
                notes: [
                    qsTr("Added Ubuntu 26.04 client and overlay packages with clean-container package and lifecycle checks."),
                    qsTr("Kept Proton's daemon and VPN networking ownership unchanged.")
                ]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.13.0"
                headingLevel: 3
                notes: [
                    qsTr("Introduced the graphical Plasma connection experience, on-demand Control Center and Inspector, and lean resident agent."),
                    qsTr("Added capability-aware server discovery, native settings, bounded recovery, and hardened local process boundaries.")
                ]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: qsTr("0.12.0 development milestone")
                headingLevel: 3
                notes: [
                    qsTr("Accepted locally but never tagged or published. Its changes are included in the 0.13.0 release.")
                ]
            }

            ReleaseNoteGroup {
                heading: qsTr("Connection insight")
                headingLevel: 4
                notes: [
                    qsTr("The new on-demand Connection Inspector shows the current server, its capabilities, protection settings, and local runtime state."),
                    qsTr("The Inspector collects no traffic or history and performs no background polling.")
                ]
            }

            ReleaseNoteGroup {
                heading: qsTr("Lean desktop integration")
                headingLevel: 4
                notes: [
                    qsTr("Backend lifetime now follows D-Bus ownership events and a one-shot idle deadline instead of periodic polling."),
                    qsTr("Repeated refreshes are coalesced, and stale replies are discarded after account or backend changes.")
                ]
            }

            ReleaseNoteGroup {
                heading: qsTr("Stronger recovery")
                headingLevel: 4
                notes: [
                    qsTr("Reconnect work remains cancellable and retryable across suspend, long outages, backend restarts, and package upgrades."),
                    qsTr("Packet capture now uses transactional start, bounded stop attempts, and durable recovery from interrupted shutdown.")
                ]
            }

            ReleaseNoteGroup {
                heading: qsTr("Coherent account state")
                headingLevel: 4
                notes: [
                    qsTr("Sign-in, two-factor, security-key, sign-out, expiry, and cancellation paths reconcile with Proton Core before changing the interface."),
                    qsTr("When account, protection, or backend state cannot be confirmed, the client pauses safely and offers explicit recovery guidance.")
                ]
            }

            ReleaseNoteGroup {
                heading: qsTr("Hardened local boundaries")
                headingLevel: 4
                notes: [
                    qsTr("Tray, global-shortcut, and KRunner connection requests require explicit Control Center confirmation."),
                    qsTr("Secret Service traffic is pinned to the selected same-user provider, and packaged launchers sanitize runtime search paths. Proton Core continues to own VPN networking.")
                ]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.11.3"
                notes: [
                    qsTr("Restore reliable Plasma reconnects without depending on a missing Protun secret-agent plug-in."),
                    qsTr("Clear stale account and tunnel state when the Proton backend stops."),
                    qsTr("Offer an explicit service retry when Secret Service restoration stalls during sign-in.")
                ]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.11.2"
                notes: [
                    qsTr("Add shared color, light-symbol, and dark-symbol icon choices for the Control Center, tray, and System Settings."),
                    qsTr("Require explicit confirmation for KRunner requests and keep Proton support and crash submission disabled in unofficial builds."),
                    qsTr("Retry transiently empty server groups and distinguish leaving a tunnel connected from waiting for a confirmed disconnect."),
                    qsTr("Recover cleanly from unexpected backend exits and explain when a package upgrade requires a restart.")
                ]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.11.1"
                notes: [
                    qsTr("Introduce the original Plasma VPN identity and make the Proton VPN-compatible community relationship explicit."),
                    qsTr("Embed the application mark and keep Settings open after configuration changes.")
                ]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.10.2"
                notes: [qsTr("Keep Settings open after applying VPN changes instead of returning unexpectedly to Overview.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.10.1"
                notes: [qsTr("Open directly to sign-in when needed, serialize credentials with backend startup, and explain pending secret-store approval.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.10.0"
                notes: [qsTr("Adopt responsive Plasma navigation, Kirigami cards, compact actions, semantic styling, and compact, scaled-text, and RTL layout checks.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.9.0"
                notes: [qsTr("Move tray controls, shortcuts, notifications, favorites, and auto-connect into a lean resident agent while keeping the full Control Center on demand.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.8.8"
                notes: [qsTr("Add every-page runtime diagnostics and warn when the installed Proton Core lacks the verified server-list memory optimizations.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.8.7"
                notes: [qsTr("Harden the on-demand backend with fixed service paths, privilege controls, and interpreter and loader environment cleanup.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.8.6"
                notes: [qsTr("Make full-cache country, city, and server search effectively instantaneous with a compact local projection.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.8.2"
                notes: [qsTr("Keep one Proton backend active, supervise connected tunnels, release Core when idle, and build location data only when opened.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.8.1"
                notes: [qsTr("Restart the D-Bus backend after package upgrades so frontend and backend interfaces remain synchronized.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.8.0"
                notes: [qsTr("Add native custom DNS editing with IPv4 and IPv6 validation and explicit NetShield conflict handling.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.7.0"
                notes: [qsTr("Add native split-tunneling controls and a Plasma application chooser backed by KDE's application catalog.")]
            }

            Kirigami.Separator { Layout.fillWidth: true }

            ReleaseNoteGroup {
                heading: "0.6.0"
                notes: [qsTr("Add conflict-aware native controls for Proton VPN connection and privacy settings.")]
            }
        }
    }
}
