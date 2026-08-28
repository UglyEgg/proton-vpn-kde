import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    width: 520
    height: 700
    minimumWidth: 420
    minimumHeight: 560
    visible: !startMinimized
    title: qsTr("Proton VPN")

    onClosing: close => {
        if (appSettings.closeToTray) {
            close.accepted = false
            root.hide()
        } else {
            close.accepted = false
            appLifecycle.requestQuit(
                vpnController.state,
                vpnController.backendAvailable && vpnController.ready
                    && vpnController.loggedIn)
        }
    }

    function showPage(pageUrl) {
        pageStack.clear()
        pageStack.push(pageUrl)
    }

    function showSettings() {
        showPage(Qt.resolvedUrl("SettingsPage.qml"))
    }

    function maybeShowNpsSurvey() {
        if (root.visible && vpnController.npsSurveyAvailable
                && !npsDialog.visible) {
            npsDialog.open()
        }
    }

    onVisibleChanged: Qt.callLater(root.maybeShowNpsSurvey)

    property bool previousLoggedIn: vpnController.loggedIn
    property string previousErrorCode: ""

    Controls.Dialog {
        id: quitDialog
        anchors.centerIn: parent
        modal: true
        title: qsTr("Disconnect and quit Proton VPN?")
        standardButtons: Controls.Dialog.Yes | Controls.Dialog.Cancel

        Controls.Label {
            width: Kirigami.Units.gridUnit * 22
            wrapMode: Text.WordWrap
            text: vpnController.settings.killSwitch === 2
                  ? qsTr("The VPN tunnel will be disconnected. The permanent kill switch will remain active after the app exits.")
                  : qsTr("The active VPN tunnel will be disconnected before the app exits.")
        }

        onAccepted: appLifecycle.confirmQuit()
        onRejected: appLifecycle.cancelQuit()
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
            text: qsTr("You've reached your maximum device limit. To reconnect to VPN, disconnect from another device.")
        }
    }

    Controls.ButtonGroup {
        id: npsScoreGroup
    }

    Controls.Dialog {
        id: npsDialog
        anchors.centerIn: parent
        width: Math.min(root.width - Kirigami.Units.gridUnit * 2,
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
                vpnController.dismissNpsSurvey()
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
                            vpnController.submitNpsSurvey(
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

    Connections {
        target: appLifecycle
        function onQuitConfirmationRequested() {
            root.show()
            root.raise()
            root.requestActivate()
            quitDialog.open()
        }
    }

    Connections {
        target: vpnController
        function onSnapshotChanged() {
            if (!root.previousLoggedIn && vpnController.loggedIn) {
                root.showPage(Qt.resolvedUrl("OverviewPage.qml"))
            } else if (root.previousLoggedIn && !vpnController.loggedIn) {
                root.showPage(Qt.resolvedUrl("SignInPage.qml"))
            }
            if (vpnController.errorCode === "maximum_sessions_reached"
                    && root.previousErrorCode
                       !== "maximum_sessions_reached") {
                root.show()
                root.raise()
                root.requestActivate()
                sessionLimitDialog.open()
            }
            root.previousLoggedIn = vpnController.loggedIn
            root.previousErrorCode = vpnController.errorCode
        }
        function onNpsSurveyChanged() {
            Qt.callLater(root.maybeShowNpsSurvey)
        }
    }

    pageStack.initialPage: Qt.resolvedUrl(initialPageName)

    globalDrawer: Kirigami.GlobalDrawer {
        title: qsTr("Proton VPN")
        titleIcon: "network-vpn"
        isMenu: true

        actions: [
            Kirigami.Action {
                text: qsTr("Overview")
                icon.name: "network-vpn"
                onTriggered: root.showPage(Qt.resolvedUrl("OverviewPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Countries and servers")
                icon.name: "network-server"
                enabled: vpnController.loggedIn
                onTriggered: root.showPage(Qt.resolvedUrl("LocationsPage.qml"))
            },
            Kirigami.Action {
                text: vpnController.loggedIn ? qsTr("Account") : qsTr("Sign in")
                icon.name: vpnController.loggedIn ? "user-identity" : "system-log-in"
                onTriggered: root.showPage(Qt.resolvedUrl(
                    vpnController.loggedIn ? "AccountPage.qml" : "SignInPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Settings")
                icon.name: "settings-configure"
                onTriggered: root.showPage(Qt.resolvedUrl("SettingsPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Release notes")
                icon.name: "view-list-text"
                onTriggered: root.showPage(Qt.resolvedUrl("ReleaseNotesPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Report an issue")
                icon.name: "tools-report-bug"
                enabled: vpnController.loggedIn
                onTriggered: root.showPage(Qt.resolvedUrl("ReportIssuePage.qml"))
            },
            Kirigami.Action {
                text: qsTr("About")
                icon.name: "help-about"
                onTriggered: root.showPage(Qt.resolvedUrl("AboutPage.qml"))
            },
            Kirigami.Action {
                text: qsTr("Quit")
                icon.name: "application-exit"
                onTriggered: appLifecycle.requestQuit(
                    vpnController.state,
                    vpnController.backendAvailable && vpnController.ready
                        && vpnController.loggedIn)
            }
        ]
    }
}
