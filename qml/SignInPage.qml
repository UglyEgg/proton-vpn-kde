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

    readonly property int preparingStep: 0
    readonly property int recoveryStep: 1
    readonly property int signingInStep: 2
    readonly property int credentialStep: 3
    readonly property int twoFactorStep: 4
    readonly property int securityKeyStep: 5
    readonly property int securityKeyPinStep: 6

    readonly property bool preparingSignIn: !vpnController.ready
    readonly property bool terminalBackendFailure:
        page.preparingSignIn && !vpnController.backendRestartAllowed
    readonly property bool recoveryRequired: [
        "authentication_unknown", "settings_unavailable", "protection_unknown"
    ].includes(vpnController.authState)
    readonly property bool twoFactorVisible: [
        "two_factor", "fido_error"
    ].includes(vpnController.authState)
    readonly property bool fidoPromptVisible: [
        "fido_waiting", "fido_touch", "fido_select"
    ].includes(vpnController.authState)
    readonly property int activeStep: {
        if (page.preparingSignIn) {
            return page.preparingStep
        }
        if (page.recoveryRequired) {
            return page.recoveryStep
        }
        if (vpnController.authState === "signing_in") {
            return page.signingInStep
        }
        if (page.twoFactorVisible) {
            return page.twoFactorStep
        }
        if (page.fidoPromptVisible) {
            return page.securityKeyStep
        }
        if (vpnController.authState === "fido_pin") {
            return page.securityKeyPinStep
        }
        return page.credentialStep
    }
    readonly property bool credentialsVisible:
        page.activeStep === page.credentialStep
    readonly property string activeStepIcon: {
        if (page.activeStep === page.preparingStep) {
            return page.terminalBackendFailure ? "dialog-error"
                                               : "view-refresh"
        }
        if (page.activeStep === page.recoveryStep) {
            return "dialog-warning"
        }
        if (page.activeStep === page.signingInStep) {
            return "document-encrypt"
        }
        if (page.activeStep === page.securityKeyStep) {
            return "auth-sim-locked"
        }
        if (page.activeStep === page.securityKeyPinStep) {
            return "password-show-off"
        }
        if (page.activeStep === page.twoFactorStep) {
            return "document-encrypt"
        }
        return applicationWindow().appIconSource
    }
    readonly property string activeStepHeading: {
        if (page.activeStep === page.preparingStep) {
            return page.terminalBackendFailure
                   ? qsTr("Sign-in unavailable")
                   : qsTr("Preparing sign-in")
        }
        if (page.activeStep === page.recoveryStep) {
            return qsTr("Account state unavailable")
        }
        if (page.activeStep === page.signingInStep) {
            return qsTr("Signing in")
        }
        if (page.activeStep === page.twoFactorStep) {
            return qsTr("Two-factor authentication")
        }
        if (page.activeStep === page.securityKeyStep) {
            return qsTr("Use your security key")
        }
        if (page.activeStep === page.securityKeyPinStep) {
            return qsTr("Enter your security-key PIN")
        }
        if (vpnController.authState === "human_verification") {
            return qsTr("Verify your Proton account")
        }
        if (vpnController.authState === "expired") {
            return qsTr("Sign in again")
        }
        return qsTr("Sign in to Proton VPN")
    }
    readonly property string activeStepDescription: {
        if (page.activeStep === page.preparingStep) {
            if (page.terminalBackendFailure) {
                return vpnController.message.length > 0
                       ? vpnController.message
                       : qsTr("The local client could not be authorized.")
            }
            return vpnController.backendAvailable
                   ? qsTr("Confirming the saved account and protection state.")
                   : qsTr("Starting the local Proton VPN service.")
        }
        if (page.activeStep === page.recoveryStep) {
            return vpnController.message.length > 0
                   ? vpnController.message
                   : qsTr("Restart the local service before authentication can safely continue.")
        }
        if (page.activeStep === page.signingInStep) {
            return qsTr("Completing authentication and preparing your Proton VPN session.")
        }
        if (page.activeStep === page.twoFactorStep) {
            return qsTr("Complete the additional security check for this account.")
        }
        if (page.activeStep === page.securityKeyStep) {
            return vpnController.message.length > 0
                   ? vpnController.message
                   : qsTr("Follow the prompt from your security key to continue.")
        }
        if (page.activeStep === page.securityKeyPinStep) {
            return qsTr("Your PIN is sent only to the waiting local security-key flow.")
        }
        if (vpnController.authState === "human_verification") {
            return qsTr("Complete the requested check in your Proton account, then try again.")
        }
        if (vpnController.authState === "expired") {
            return qsTr("Your saved session expired. Enter your Proton account details to continue.")
        }
        return qsTr("Use your Proton account to access VPN servers.")
    }

    property string previousAuthState: vpnController.authState
    property bool secretStoreHintVisible: false
    property bool backendRetryVisible: false
    property Kirigami.Action retryBackendAction: Kirigami.Action {
        text: qsTr("Retry service")
        icon.name: "view-refresh"
        onTriggered: {
            page.backendRetryVisible = false
            vpnController.restartBackend()
            page.updateBackendRetry()
        }
    }

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

    function updateBackendRetry() {
        const waiting = page.preparingSignIn
                        && vpnController.backendRestartAllowed
        if (waiting) {
            if (!backendRetryVisible && !backendRetryTimer.running) {
                backendRetryTimer.start()
            }
        } else {
            backendRetryTimer.stop()
            backendRetryVisible = false
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
            page.updateBackendRetry()
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
        page.updateBackendRetry()
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

    Timer {
        id: backendRetryTimer
        interval: 10000
        repeat: false
        onTriggered: {
            if (page.preparingSignIn
                    && vpnController.backendRestartAllowed) {
                page.backendRetryVisible = true
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

        IdentityStage {
            id: authenticationStage
            objectName: "authenticationStage"
            iconSource: page.activeStepIcon
            heading: page.activeStepHeading
            description: page.activeStepDescription
            accentColor: page.activeStep === page.recoveryStep
                         || vpnController.authState === "human_verification"
                         || vpnController.authState === "expired"
                         ? Kirigami.Theme.neutralTextColor
                         : Kirigami.Theme.highlightColor
        }

        Kirigami.InlineMessage {
            objectName: "backendStartupDiagnostic"
            Layout.fillWidth: true
            visible: vpnController.message.length > 0
                     && page.activeStep !== page.securityKeyStep
                     && page.activeStep !== page.recoveryStep
                     && !page.terminalBackendFailure
            type: vpnController.authState === "human_verification"
                  || vpnController.authState === "fido_error"
                  ? Kirigami.MessageType.Warning
                  : Kirigami.MessageType.Information
            text: vpnController.message
        }

        ColumnLayout {
            objectName: "preparingAuthenticationStep"
            Layout.fillWidth: true
            visible: page.activeStep === page.preparingStep
            spacing: Kirigami.Units.largeSpacing

            Controls.BusyIndicator {
                objectName: "backendPreparationProgress"
                Layout.alignment: Qt.AlignHCenter
                visible: running
                running: parent.visible
                         && vpnController.backendRestartAllowed
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                visible: page.backendRetryVisible
                text: page.retryBackendAction.text
                icon.name: page.retryBackendAction.icon.name
                onClicked: page.retryBackendAction.trigger()
            }
        }

        ColumnLayout {
            objectName: "authenticationRecoveryStep"
            Layout.fillWidth: true
            visible: page.activeStep === page.recoveryStep
            spacing: Kirigami.Units.largeSpacing

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: parent.visible
                type: Kirigami.MessageType.Warning
                text: qsTr("Sign-in is paused until the service has restarted. Follow the guidance above before reconnecting.")
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Restart service")
                icon.name: "view-refresh"
                highlighted: true
                onClicked: vpnController.restartBackend()
            }
        }

        ColumnLayout {
            objectName: "signingInStep"
            Layout.fillWidth: true
            visible: page.activeStep === page.signingInStep
            spacing: Kirigami.Units.largeSpacing

            Controls.BusyIndicator {
                objectName: "authenticationProgress"
                Layout.alignment: Qt.AlignHCenter
                running: parent.visible && vpnController.busy
            }

            Kirigami.InlineMessage {
                Layout.fillWidth: true
                visible: page.secretStoreHintVisible
                type: Kirigami.MessageType.Information
                text: qsTr("If your desktop Secret Service requests access, approve it in KeePassXC, KWallet, or your configured provider.")
            }
        }

        Kirigami.AbstractCard {
            objectName: "credentialAuthenticationStep"
            Layout.fillWidth: true
            visible: page.activeStep === page.credentialStep
            enabled: vpnController.ready && !vpnController.busy
                     && vpnController.killSwitch !== 2

            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

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
        }

        Kirigami.AbstractCard {
            objectName: "twoFactorAuthenticationStep"
            Layout.fillWidth: true
            visible: page.activeStep === page.twoFactorStep

            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

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
        }

        ColumnLayout {
            objectName: "securityKeyAuthenticationStep"
            Layout.fillWidth: true
            visible: page.activeStep === page.securityKeyStep
            spacing: Kirigami.Units.largeSpacing

            Controls.BusyIndicator {
                Layout.alignment: Qt.AlignHCenter
                running: parent.visible
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Cancel security key")
                onClicked: vpnController.cancelFido2()
            }
        }

        Kirigami.AbstractCard {
            objectName: "securityKeyPinAuthenticationStep"
            Layout.fillWidth: true
            visible: page.activeStep === page.securityKeyPinStep

            contentItem: ColumnLayout {
                spacing: Kirigami.Units.largeSpacing

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
        }

        Controls.Label {
            Layout.fillWidth: true
            visible: page.activeStep === page.credentialStep
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            text: qsTr("Credentials are encrypted for the local backend, transferred through a sealed one-use memory file, and never included in D-Bus message data or settings.")
            color: Kirigami.Theme.disabledTextColor
        }
    }
}
