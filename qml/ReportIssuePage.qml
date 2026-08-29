import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    title: qsTr("Report an Issue")
    readonly property real maximumFormWidth: Kirigami.Units.gridUnit * 30
    leftPadding: Math.max(Kirigami.Units.largeSpacing,
                          (width - maximumFormWidth) / 2)
    rightPadding: leftPadding
    property bool submitting: false
    property bool submitted: false
    property string statusMessage: ""

    Connections {
        target: vpnController
        function onSupportReportFinished(success, message) {
            page.submitting = false
            page.submitted = success
            page.statusMessage = message
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: page.statusMessage.length > 0
            type: page.submitted ? Kirigami.MessageType.Positive
                                 : Kirigami.MessageType.Error
            text: page.statusMessage
        }

        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            text: qsTr("Send a report directly to Proton support. The form is submitted through Proton's official VPN API.")
        }

        Kirigami.FormLayout {
            Layout.fillWidth: true

            Controls.TextField {
                id: usernameField
                Kirigami.FormData.label: qsTr("Username:")
                text: vpnController.accountName
                maximumLength: 255
                enabled: !page.submitting
                inputMethodHints: Qt.ImhNoAutoUppercase
                Accessible.name: qsTr("Proton username")
            }

            Controls.TextField {
                id: emailField
                Kirigami.FormData.label: qsTr("Email:")
                maximumLength: 254
                enabled: !page.submitting
                inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoAutoUppercase
                Accessible.name: qsTr("Contact email address")
            }

            ColumnLayout {
                Kirigami.FormData.label: qsTr("Description:")
                Layout.fillWidth: true

                Controls.ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.gridUnit * 10

                    Controls.TextArea {
                        id: descriptionField
                        enabled: !page.submitting
                        wrapMode: TextEdit.Wrap
                        placeholderText: qsTr("Describe what happened, what you expected, and how to reproduce it.")
                        Accessible.name: qsTr("Issue description")
                        onTextChanged: {
                            if (length > 8000) {
                                text = text.slice(0, 8000)
                                cursorPosition = length
                            }
                        }
                    }
                }

                Controls.Label {
                    Layout.alignment: Qt.AlignRight
                    color: descriptionField.length >= 50
                           ? Kirigami.Theme.disabledTextColor
                           : Kirigami.Theme.negativeTextColor
                    text: qsTr("%1 / 50 minimum").arg(descriptionField.length)
                }
            }

            Controls.CheckBox {
                id: includeLogs
                Kirigami.FormData.label: qsTr("Diagnostics:")
                text: qsTr("Include error logs from the last 24 hours")
                checked: true
                enabled: !page.submitting
            }
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            type: Kirigami.MessageType.Warning
            visible: includeLogs.checked
            text: qsTr("Diagnostic logs can contain server names, network configuration, IP addresses, and error details. They are collected only after you press Submit.")
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter

            Controls.Button {
                text: page.submitting ? qsTr("Submitting…") : qsTr("Submit")
                icon.name: "mail-send"
                highlighted: true
                enabled: vpnController.loggedIn && !page.submitting
                         && !vpnController.busy
                         && usernameField.text.trim().length > 0
                         && emailField.text.trim().length > 0
                         && descriptionField.length >= 50
                onClicked: {
                    page.submitting = true
                    page.submitted = false
                    page.statusMessage = ""
                    vpnController.submitSupportReport(
                        usernameField.text,
                        emailField.text,
                        descriptionField.text,
                        includeLogs.checked)
                }
            }

            Controls.Button {
                text: qsTr("Open support website")
                icon.name: "internet-web-browser"
                enabled: !page.submitting
                onClicked: Qt.openUrlExternally("https://protonvpn.com/support-form")
            }
        }
    }
}
