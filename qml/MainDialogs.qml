// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: dialogs

    required property var vpnController
    required property var appSettings
    required property real windowWidth
    readonly property bool runnerActionVisible: runnerActionDialog.visible
    readonly property bool npsVisible: npsDialog.visible

    function requestRunnerAction(action, argument) {
        if (runnerActionDialog.visible) {
            return
        }
        runnerActionDialog.actionId = action
        runnerActionDialog.argument = argument
        runnerActionDialog.open()
    }

    function acceptRunnerAction() {
        runnerActionDialog.accept()
    }

    function openCompatibility() {
        compatibilityDialog.open()
    }

    function openNps() {
        npsDialog.open()
    }

    function openRecovery(code) {
        if (code === "maximum_sessions_reached") {
            sessionLimitDialog.open()
            return true
        }
        if (code === "authentication_denied") {
            authenticationErrorDialog.open()
            return true
        }
        if (code === "two_factor_required") {
            twoFactorRequiredDialog.open()
            return true
        }
        if (code === "certificate_not_yet_valid") {
            clockErrorDialog.open()
            return true
        }
        return false
    }

    function closeAll() {
        const activeDialogs = [
            runnerActionDialog,
            sessionLimitDialog,
            authenticationErrorDialog,
            twoFactorRequiredDialog,
            clockErrorDialog,
            compatibilityDialog,
            npsDialog
        ]
        for (const dialog of activeDialogs) {
            if (dialog.visible) {
                dialog.close()
            }
        }
    }

    Controls.Dialog {
        id: runnerActionDialog
        anchors.centerIn: parent
        width: Math.min(dialogs.windowWidth - Kirigami.Units.gridUnit * 2,
                        Kirigami.Units.gridUnit * 28)
        modal: true
        title: qsTr("Confirm VPN action")
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.Cancel

        property string actionId: ""
        property string argument: ""

        function clearRequest() {
            actionId = ""
            argument = ""
        }

        onOpened: {
            const confirmButton = standardButton(Controls.Dialog.Yes)
            if (confirmButton !== null) {
                confirmButton.enabled = Qt.binding(function() {
                    return dialogs.vpnController.ready
                           && !dialogs.vpnController.busy
                })
            }
        }
        onAccepted: {
            const confirmedAction = actionId
            const confirmedArgument = argument
            clearRequest()
            if (confirmedAction === "fastest") {
                dialogs.vpnController.connectFastestWithFeatures(
                    dialogs.appSettings.fastestFeatures)
            } else if (confirmedAction === "disconnect") {
                dialogs.vpnController.disconnect()
            } else if (confirmedAction === "country") {
                dialogs.vpnController.connectCountry(confirmedArgument)
            } else if (confirmedAction === "server") {
                dialogs.vpnController.connectServer(confirmedArgument)
            }
        }
        onRejected: clearRequest()

        Controls.Label {
            width: Kirigami.Units.gridUnit * 24
            wrapMode: Text.WordWrap
            text: runnerActionDialog.actionId === "fastest"
                  ? qsTr("Connect to the fastest Proton VPN server using your saved feature filters?")
                  : runnerActionDialog.actionId === "disconnect"
                    ? qsTr("Disconnect the current Proton VPN connection?")
                    : runnerActionDialog.actionId === "country"
                      ? qsTr("Connect to the fastest Proton VPN server in %1?").arg(runnerActionDialog.argument)
                      : qsTr("Connect to Proton VPN server %1?").arg(runnerActionDialog.argument)
        }
    }

    Controls.Dialog {
        id: sessionLimitDialog
        anchors.centerIn: parent
        modal: true
        title: qsTr("Connection error: session limit reached")
        standardButtons: Controls.Dialog.Ok

        Controls.Label {
            width: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: qsTr("You've reached your maximum device limit. To reconnect to VPN, please disconnect from another device.")
        }
    }

    Controls.Dialog {
        id: authenticationErrorDialog
        anchors.centerIn: parent
        modal: true
        title: qsTr("VPN connection error")
        standardButtons: Controls.Dialog.Ok

        Controls.Label {
            width: Kirigami.Units.gridUnit * 24
            wrapMode: Text.WordWrap
            text: qsTr("Proton VPN could not connect to the VPN and blocked access to Internet to protect your IP.\n\nClick \"Cancel Connection\" to restore your Internet connection. If the issue persists please try to sign out and in.")
        }
    }

    Controls.Dialog {
        id: twoFactorRequiredDialog
        anchors.centerIn: parent
        modal: true
        title: qsTr("2FA Required")
        standardButtons: Controls.Dialog.Ok

        Controls.Label {
            width: Kirigami.Units.gridUnit * 24
            wrapMode: Text.WordWrap
            text: qsTr("You are connected to the VPN, but all traffic is blocked.\nYou need to go to the authentication page provided by security and authenticate with your hardware key.\nAfter that, the traffic will be enabled.")
        }
    }

    Controls.Dialog {
        id: clockErrorDialog
        anchors.centerIn: parent
        modal: true
        title: qsTr("Update system clock")
        standardButtons: Controls.Dialog.Ok

        Controls.Label {
            width: Kirigami.Units.gridUnit * 24
            wrapMode: Text.WordWrap
            text: qsTr("Looks like your system clock is out of sync.\nThis may cause issues when connecting to VPN.\nUpdate your system time and try to connect again.")
        }
    }

    Controls.Dialog {
        id: compatibilityDialog
        anchors.centerIn: parent
        modal: true
        title: qsTr("Something went wrong")
        standardButtons: Controls.Dialog.Ok

        ColumnLayout {
            width: Kirigami.Units.gridUnit * 22
            spacing: Kirigami.Units.largeSpacing

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: qsTr("Some required components were not detected on your system. The app may not work as expected.")
            }

            Controls.Button {
                Layout.alignment: Qt.AlignHCenter
                text: qsTr("Learn more")
                onClicked: Qt.openUrlExternally(
                    "https://protonvpn.com/support/linux-gui-setup")
            }
        }
    }

    Controls.ButtonGroup {
        id: npsScoreGroup
    }

    Controls.Dialog {
        id: npsDialog
        anchors.centerIn: parent
        width: Math.min(dialogs.windowWidth - Kirigami.Units.gridUnit * 2,
                        Kirigami.Units.gridUnit * 28)
        modal: true
        title: submitted ? qsTr("Thanks for your feedback")
                         : qsTr("How likely are you to recommend Proton VPN to a friend?")
        closePolicy: Controls.Popup.CloseOnEscape

        property int selectedScore: -1
        property bool responseSent: false
        property bool submitted: false

        onOpened: {
            selectedScore = -1
            responseSent = false
            submitted = false
            feedback.clear()
            for (let button of npsScoreGroup.buttons) {
                button.checked = false
            }
        }
        onClosed: {
            if (!responseSent) {
                responseSent = true
                dialogs.vpnController.dismissNpsSurvey()
            }
        }

        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.largeSpacing

            ColumnLayout {
                Layout.fillWidth: true
                visible: !npsDialog.submitted
                spacing: Kirigami.Units.largeSpacing

                GridLayout {
                    Layout.alignment: Qt.AlignHCenter
                    columns: 6

                    Repeater {
                        model: 11

                        Controls.RadioButton {
                            required property int modelData
                            text: modelData.toString()
                            Controls.ButtonGroup.group: npsScoreGroup
                            onClicked: npsDialog.selectedScore = modelData
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    Controls.Label {
                        text: qsTr("0 is very unlikely")
                        color: Kirigami.Theme.disabledTextColor
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    Controls.Label {
                        text: qsTr("10 is very likely")
                        color: Kirigami.Theme.disabledTextColor
                    }
                }

                Controls.Label {
                    Layout.fillWidth: true
                    visible: npsDialog.selectedScore >= 0
                    text: qsTr("Please let us know why you gave that rating (optional)")
                    wrapMode: Text.WordWrap
                }

                Controls.ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 7
                    visible: npsDialog.selectedScore >= 0

                    Controls.TextArea {
                        id: feedback
                        placeholderText: qsTr("Optional feedback")
                        wrapMode: TextEdit.Wrap
                        onTextChanged: {
                            if (length > 250) {
                                text = text.slice(0, 250)
                                cursorPosition = length
                            }
                        }
                    }
                }

                Controls.Label {
                    Layout.alignment: Qt.AlignRight
                    visible: npsDialog.selectedScore >= 0
                    text: qsTr("%1/250").arg(feedback.length)
                    color: Kirigami.Theme.disabledTextColor
                }

                RowLayout {
                    Layout.alignment: Qt.AlignHCenter

                    Controls.Button {
                        text: qsTr("Not now")
                        onClicked: npsDialog.reject()
                    }

                    Controls.Button {
                        text: qsTr("Share anonymously")
                        highlighted: true
                        enabled: npsDialog.selectedScore >= 0
                        onClicked: {
                            npsDialog.responseSent = true
                            dialogs.vpnController.submitNpsSurvey(
                                npsDialog.selectedScore, feedback.text)
                            npsDialog.submitted = true
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                visible: npsDialog.submitted
                spacing: Kirigami.Units.largeSpacing

                Kirigami.Icon {
                    Layout.alignment: Qt.AlignHCenter
                    source: "emblem-success"
                    implicitWidth: Kirigami.Units.iconSizes.huge
                    implicitHeight: implicitWidth
                }

                Controls.Label {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    text: qsTr("Your feedback helps us improve Proton VPN.")
                    wrapMode: Text.WordWrap
                }

                Controls.Button {
                    Layout.alignment: Qt.AlignHCenter
                    text: qsTr("Close")
                    onClicked: npsDialog.accept()
                }
            }
        }
    }
}
