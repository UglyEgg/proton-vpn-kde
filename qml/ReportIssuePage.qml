// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ScrollablePage {
    id: page
    objectName: "reportIssuePage"
    title: qsTr("Report an Issue")
    readonly property real maximumFormWidth: Kirigami.Units.gridUnit * 30
    leftPadding: Math.max(Kirigami.Units.largeSpacing, (width - maximumFormWidth) / 2)
    rightPadding: leftPadding
    property bool submitting: false
    property bool submitted: false
    property string statusMessage: ""

    function submitReport() {
        if (!vpnController.supportReportSubmissionEnabled) {
            submissionUnavailableDialog.open();
            return;
        }
        page.submitting = true;
        page.submitted = false;
        page.statusMessage = "";
        vpnController.submitSupportReport(usernameField.text, emailField.text, descriptionField.text, includeLogs.checked);
    }

    Component.onCompleted: {
        if (!vpnController.supportReportSubmissionEnabled) {
            Qt.callLater(function () {
                submissionUnavailableDialog.open();
            });
        }
    }

    Controls.Dialog {
        id: submissionUnavailableDialog
        objectName: "reportUnavailableDialog"
        parent: Controls.Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(Kirigami.Units.gridUnit * 26, page.width - Kirigami.Units.gridUnit * 2)
        implicitHeight: unavailableMessage.implicitHeight + Kirigami.Units.gridUnit * 6
        modal: true
        title: qsTr("Direct reporting unavailable")
        standardButtons: Controls.Dialog.Ok

        contentItem: Controls.Label {
            id: unavailableMessage
            wrapMode: Text.WordWrap
            text: qsTr("This build cannot send reports to Proton. The form remains visible only as a proof of concept for possible future approval. Report Plasma VPN client problems in the community project tracker. Contact Proton only for confirmed service or Core issues.")
        }
    }

    Connections {
        target: vpnController
        function onSupportReportFinished(success, message) {
            page.submitting = false;
            page.submitted = success;
            page.statusMessage = message;
        }
    }

    ColumnLayout {
        spacing: Kirigami.Units.largeSpacing

        PageHeader {
            heading: qsTr("Report an issue")
            description: vpnController.supportReportSubmissionEnabled ? qsTr("Send a report through Proton's official VPN API.") : qsTr("Preview the direct-reporting proof of concept.")
            iconName: "tools-report-bug"
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: !vpnController.supportReportSubmissionEnabled
            type: Kirigami.MessageType.Warning
            text: qsTr("Direct Proton submission is not enabled for this unofficial community client.")
        }

        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: page.statusMessage.length > 0
            type: page.submitted ? Kirigami.MessageType.Positive : Kirigami.MessageType.Error
            text: page.statusMessage
        }

        SectionCard {
            id: reportCard
            objectName: "supportReportCard"
            title: qsTr("Support report")
            iconName: "mail-message-new"

            Controls.Label {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                text: vpnController.supportReportSubmissionEnabled ? qsTr("Send a report directly to Proton support. The form is submitted through Proton's official VPN API.") : qsTr("This inactive form preserves the reviewed reporting workflow without sending community-client reports to Proton.")
            }

            Kirigami.FormLayout {
                id: reportForm
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                wideMode: false

                Controls.TextField {
                    id: usernameField
                    objectName: "reportUsername"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.preferredWidth: reportForm.width
                    Kirigami.FormData.label: qsTr("Username:")
                    text: vpnController.accountName
                    maximumLength: 255
                    enabled: !page.submitting
                    inputMethodHints: Qt.ImhNoAutoUppercase
                    Accessible.name: qsTr("Proton username")
                }

                Controls.TextField {
                    id: emailField
                    objectName: "reportEmail"
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Kirigami.FormData.label: qsTr("Email:")
                    maximumLength: 254
                    enabled: !page.submitting
                    inputMethodHints: Qt.ImhEmailCharactersOnly | Qt.ImhNoAutoUppercase
                    Accessible.name: qsTr("Contact email address")
                }

                ColumnLayout {
                    Kirigami.FormData.label: qsTr("Description:")
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0

                    Controls.ScrollView {
                        id: descriptionScroll
                        objectName: "reportDescriptionScroll"
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.preferredHeight: Kirigami.Units.gridUnit * 10
                        contentWidth: availableWidth

                        Controls.TextArea {
                            id: descriptionField
                            objectName: "reportDescription"
                            // The viewport owns width, never the placeholder or a
                            // pasted unbroken line. This keeps the form in its card.
                            implicitWidth: Kirigami.Units.gridUnit * 16
                            enabled: !page.submitting
                            wrapMode: TextEdit.Wrap
                            placeholderText: qsTr("Describe what happened, what you expected, and how to reproduce it.")
                            Accessible.name: qsTr("Issue description")
                            onTextChanged: {
                                if (length > 8000) {
                                    text = text.slice(0, 8000);
                                    cursorPosition = length;
                                }
                            }
                        }
                    }

                    Controls.Label {
                        Layout.alignment: Qt.AlignRight
                        color: descriptionField.length >= 50 ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.negativeTextColor
                        text: qsTr("%1 / 50 minimum").arg(descriptionField.length)
                    }
                }

                Controls.CheckBox {
                    id: includeLogs
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Kirigami.FormData.label: qsTr("Diagnostics:")
                    text: qsTr("Include error logs from the last 24 hours")
                    checked: true
                    enabled: !page.submitting
                    contentItem: Controls.Label {
                        text: includeLogs.text
                        font: includeLogs.font
                        wrapMode: Text.WordWrap
                        leftPadding: !includeLogs.mirrored && includeLogs.indicator ? includeLogs.indicator.width + includeLogs.spacing : 0
                        rightPadding: includeLogs.mirrored && includeLogs.indicator ? includeLogs.indicator.width + includeLogs.spacing : 0
                    }
                }
            }

            Kirigami.InlineMessage {
                objectName: "reportLogWarning"
                Layout.fillWidth: true
                type: Kirigami.MessageType.Warning
                visible: includeLogs.checked
                text: qsTr("Diagnostic logs can contain server names, network configuration, IP addresses, and error details. They are collected only after you press Submit.")
            }

            Flow {
                id: reportActions
                objectName: "reportActions"
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                Layout.preferredHeight: childrenRect.height
                spacing: Kirigami.Units.smallSpacing

                Controls.Button {
                    objectName: "reportSubmit"
                    width: Math.min(implicitWidth, reportActions.width)
                    text: !vpnController.supportReportSubmissionEnabled ? qsTr("Submission disabled") : page.submitting ? qsTr("Submitting…") : qsTr("Submit")
                    icon.name: "mail-send"
                    highlighted: vpnController.supportReportSubmissionEnabled
                    enabled: vpnController.supportReportSubmissionEnabled && vpnController.loggedIn && !page.submitting && !vpnController.busy && usernameField.text.trim().length > 0 && emailField.text.trim().length > 0 && descriptionField.length >= 50
                    onClicked: page.submitReport()
                }

                Controls.Button {
                    width: Math.min(implicitWidth, reportActions.width)
                    text: qsTr("Community issue tracker")
                    icon.name: "tools-report-bug"
                    enabled: !page.submitting
                    onClicked: Qt.openUrlExternally("https://github.com/uglyegg/proton-vpn-kde/issues/new/choose")
                }

                Controls.Button {
                    width: Math.min(implicitWidth, reportActions.width)
                    text: qsTr("Open support website")
                    icon.name: "internet-web-browser"
                    enabled: !page.submitting
                    onClicked: Qt.openUrlExternally("https://protonvpn.com/support-form")
                }
            }
        }
    }
}
