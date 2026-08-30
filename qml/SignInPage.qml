// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Sign in")
    readonly property real maximumFormWidth: Kirigami.Units.gridUnit * 26
    leftPadding: Math.max(Kirigami.Units.largeSpacing,
                          (width - maximumFormWidth) / 2)
    rightPadding: leftPadding

    readonly property bool preparingSignIn: !vpnController.ready
    readonly property bool credentialsVisible: preparingSignIn || [
        "signed_out", "signing_in", "human_verification", "expired"
    ].includes(vpnController.authState)
    readonly property bool twoFactorVisible: [
        "two_factor", "fido_error"
    ].includes(vpnController.authState)
    readonly property bool fidoPromptVisible: [
        "fido_waiting", "fido_touch", "fido_select"
    ].includes(vpnController.authState)
    property string previousAuthState: vpnController.authState
    property bool secretStoreHintVisible: false

    function updateSecretStoreHint() {
        const waiting = vpnController.busy
                        && vpnController.authState === "signing_in"
        if (waiting) {
            if (!secretStoreHintVisible && !secretStoreHintTimer.running) {
                secretStoreHintTimer.start()
            }
        } else {
            secretStoreHintTimer.stop()
            secretStoreHintVisible = false
        }
    }

    function focusCurrentInput() {
        if (page.preparingSignIn) {
            return
        }
        if (page.credentialsVisible) {
            usernameField.forceActiveFocus()
        } else if (page.twoFactorVisible) {
            twoFactorField.forceActiveFocus()
        } else if (vpnController.authState === "fido_pin") {
            fidoPinField.forceActiveFocus()
        }
    }

    function submitCredentials() {
        if (usernameField.text.trim().length === 0
                || passwordField.text.length === 0) {
            return
        }
        vpnController.login(usernameField.text, passwordField.text)
        passwordField.clear()
    }

    function submitCode() {
        const code = twoFactorField.text.trim()
        if (code.length !== 6 && code.length !== 8) {
            return
        }
        vpnController.submitTwoFactor(code)
        twoFactorField.clear()
    }

    Connections {
        target: vpnController
        function onSnapshotChanged() {
            page.updateSecretStoreHint()
            if (vpnController.loggedIn
                    && applicationWindow().pageStack.currentItem === page) {
                applicationWindow().showOverview()
            } else if (page.previousAuthState !== vpnController.authState) {
                page.previousAuthState = vpnController.authState
                Qt.callLater(page.focusCurrentInput)
            }
        }
    }

    Component.onCompleted: {
        Qt.callLater(page.focusCurrentInput)
        page.updateSecretStoreHint()
    }

    Timer {
        id: secretStoreHintTimer
        interval: 1800
        repeat: false
        onTriggered: {
            if (vpnController.busy
                    && vpnController.authState === "signing_in") {
                page.secretStoreHintVisible = true
            }
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnController.ready && !vpnController.loggedIn
                     && vpnController.killSwitch === 2
            type: Kirigami.MessageType.Warning
            text: qsTr("The permanent kill switch is active and can block Proton authentication. Disable it before signing in.")

            actions: [
                Kirigami.Action {
                    text: qsTr("Disable kill switch")
                    icon.name: "security-low"
                    enabled: !vpnController.busy
                    onTriggered: vpnController.disableKillSwitchForLogin()
                }
            ]
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: page.preparingSignIn
                     && vpnController.state !== "error"
            type: Kirigami.MessageType.Information
            text: vpnController.backendAvailable
                  ? qsTr("Preparing Proton sign-in. Your desktop secret store may ask for access before the account state is available.")
                  : qsTr("Starting the Proton VPN service…")
        }

        PageHeader {
            heading: page.twoFactorVisible || !page.credentialsVisible
                     ? qsTr("Two-factor authentication")
                     : qsTr("Sign in to Proton VPN")
            description: page.credentialsVisible
                         ? qsTr("Use your Proton account to access VPN servers.")
                         : qsTr("Complete the security check for this account.")
            iconName: applicationWindow().appIconSource
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: vpnController.message.length > 0
            type: vpnController.authState === "human_verification"
                  || vpnController.authState === "fido_error"
                  ? Kirigami.MessageType.Warning
                  : Kirigami.MessageType.Information
            text: vpnController.message
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: page.secretStoreHintVisible
            type: Kirigami.MessageType.Information
            text: qsTr("Still signing in. Your desktop secret store may be waiting for access approval; check for a prompt to continue.")
        }

        SectionCard {
            Layout.fillWidth: true
            visible: page.credentialsVisible
            enabled: vpnController.ready && !vpnController.busy
                     && vpnController.killSwitch !== 2
            title: qsTr("Proton account")
            iconName: "user-identity"

            Controls.TextField {
                id: usernameField
                Layout.fillWidth: true
                placeholderText: qsTr("Proton username or email")
                inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoAutoUppercase
                activeFocusOnTab: true
                KeyNavigation.tab: passwordField
                Accessible.name: qsTr("Proton username or email")
                Accessible.description: qsTr("Username field for Proton VPN sign-in")
                onAccepted: passwordField.forceActiveFocus()
            }

            Controls.TextField {
                id: passwordField
                Layout.fillWidth: true
                placeholderText: qsTr("Password")
                echoMode: TextInput.Password
                inputMethodHints: Qt.ImhSensitiveData | Qt.ImhHiddenText
                                  | Qt.ImhNoPredictiveText
                activeFocusOnTab: true
                KeyNavigation.backtab: usernameField
                Accessible.name: qsTr("Proton password")
                Accessible.description: qsTr("Password field for Proton VPN sign-in")
                onAccepted: page.submitCredentials()
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: vpnController.busy ? qsTr("Signing in…") : qsTr("Sign in")
                icon.name: "document-encrypt"
                highlighted: true
                enabled: usernameField.text.trim().length > 0
                         && passwordField.text.length > 0
                         && vpnController.ready
                         && !vpnController.busy
                onClicked: page.submitCredentials()
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                visible: vpnController.authState === "human_verification"
                text: qsTr("Open Proton account")
                icon.name: "internet-web-browser"
                onClicked: Qt.openUrlExternally(
                    "https://account.protonvpn.com/account")
            }

            RowLayout {
                Layout.fillWidth: true

                Controls.Button {
                    flat: true
                    text: qsTr("Create Account")
                    onClicked: Qt.openUrlExternally(
                        "https://account.protonvpn.com/signup?ref=linux")
                }

                Item {
                    Layout.fillWidth: true
                }

                Controls.Button {
                    flat: true
                    text: qsTr("Need Help?")
                    onClicked: Qt.openUrlExternally(
                        "https://protonvpn.com/support")
                }
            }

        }

        SectionCard {
            Layout.fillWidth: true
            visible: page.twoFactorVisible
            title: qsTr("Authentication code")
            iconName: "document-encrypt"

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Enter the six-digit code from your authenticator, or an eight-character recovery code.")
            }

            Controls.TextField {
                id: twoFactorField
                Layout.fillWidth: true
                placeholderText: qsTr("Authentication or recovery code")
                echoMode: TextInput.Password
                inputMethodHints: Qt.ImhSensitiveData | Qt.ImhHiddenText
                                  | Qt.ImhNoPredictiveText
                enabled: !vpnController.busy
                activeFocusOnTab: true
                Accessible.name: qsTr("Authentication or recovery code")
                onAccepted: page.submitCode()
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Authenticate")
                highlighted: true
                enabled: (twoFactorField.text.trim().length === 6
                          || twoFactorField.text.trim().length === 8)
                         && !vpnController.busy
                onClicked: page.submitCode()
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                visible: vpnController.fido2Available
                text: qsTr("Use a security key")
                icon.name: "auth-sim-locked"
                enabled: !vpnController.busy
                onClicked: vpnController.beginFido2()
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Cancel sign-in")
                onClicked: vpnController.cancelLogin()
            }
        }

        SectionCard {
            Layout.fillWidth: true
            visible: page.fidoPromptVisible
            title: qsTr("Security key")
            iconName: "auth-sim-locked"

            Controls.BusyIndicator {
                Layout.alignment: Qt.AlignHCenter
                running: parent.visible
            }

            Controls.Label {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: vpnController.message
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Cancel security key")
                onClicked: vpnController.cancelFido2()
            }
        }

        SectionCard {
            Layout.fillWidth: true
            visible: vpnController.authState === "fido_pin"
            title: qsTr("Security-key PIN")
            iconName: "password-show-off"

            Controls.TextField {
                id: fidoPinField
                Layout.fillWidth: true
                placeholderText: qsTr("Security-key PIN")
                echoMode: TextInput.Password
                inputMethodHints: Qt.ImhSensitiveData | Qt.ImhHiddenText
                                  | Qt.ImhNoPredictiveText
                activeFocusOnTab: true
                Accessible.name: qsTr("Security-key PIN")
                onAccepted: {
                    vpnController.submitFido2Pin(text)
                    clear()
                }
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Continue")
                highlighted: true
                enabled: fidoPinField.text.length > 0
                onClicked: {
                    vpnController.submitFido2Pin(fidoPinField.text)
                    fidoPinField.clear()
                }
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Cancel security key")
                onClicked: vpnController.cancelFido2()
            }
        }

        Controls.Label {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: qsTr("Credentials are encrypted for the local backend, transferred through a sealed one-use memory file, and never included in D-Bus message data or settings.")
            color: Kirigami.Theme.disabledTextColor
        }
    }
}
