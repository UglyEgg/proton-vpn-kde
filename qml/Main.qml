import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    width: diagnosticWindowWidth > 0 ? diagnosticWindowWidth : 900
    height: diagnosticWindowHeight > 0 ? diagnosticWindowHeight : 720
    minimumWidth: 480
    minimumHeight: 560
    visible: !startMinimized
    title: qsTr("Plasma VPN")
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar

    onClosing: close => {
        close.accepted = true
    }

    function pushOwnedPage(pageComponent, properties) {
        const page = pageComponent.createObject(
            pageStack, properties === undefined ? {} : properties)
        if (page === null) {
            console.error("Unable to create a navigation page")
            return null
        }
        if (pageStack.push(page) === null) {
            page.destroy()
            console.error("Unable to add a navigation page")
            return null
        }
        root.ownedPages = root.ownedPages.concat([page])
        return page
    }

    function releaseOwnedPage(page) {
        const index = root.ownedPages.indexOf(page)
        if (index < 0) {
            return
        }
        const remainingPages = root.ownedPages.slice()
        remainingPages.splice(index, 1)
        root.ownedPages = remainingPages
        page.destroy()
    }

    function showPage(pageComponent, properties) {
        pageStack.clear()
        return pushOwnedPage(pageComponent, properties)
    }

    function showOverview() {
        root.currentSection = "overview"
        showPage(overviewPageComponent)
    }

    function resolveStartupAccountRoute() {
        if (!root.startupAccountRoutingPending || !vpnController.ready) {
            return
        }
        root.startupAccountRoutingPending = false
        if (vpnController.loggedIn) {
            root.showOverview()
        } else {
            root.showSignIn()
        }
    }

    function showSettings() {
        root.currentSection = "settings"
        showPage(settingsPageComponent)
    }

    function showSignIn() {
        root.currentSection = "account"
        showPage(signInPageComponent)
    }

    function showLocations() {
        root.currentSection = "locations"
        showPage(locationsPageComponent)
    }

    function showAccount() {
        root.currentSection = "account"
        showPage(accountPageComponent)
    }

    function showReleaseNotes() {
        root.currentSection = "release-notes"
        showPage(releaseNotesPageComponent)
    }

    function showReportIssue() {
        root.currentSection = "report-issue"
        showPage(reportIssuePageComponent)
    }

    function showAbout() {
        root.currentSection = "about"
        showPage(aboutPageComponent)
    }

    function pushCountry(properties) {
        return pushOwnedPage(countryPageComponent, properties)
    }

    function pushServers(properties) {
        return pushOwnedPage(serversPageComponent, properties)
    }

    function pushCustomDns() {
        return pushOwnedPage(customDnsPageComponent)
    }

    function pushSplitTunneling() {
        return pushOwnedPage(splitTunnelingPageComponent)
    }

    function prepareForQuit() {
        if (runnerActionDialog.visible) {
            runnerActionDialog.close()
        }
        if (sessionLimitDialog.visible) {
            sessionLimitDialog.close()
        }
        if (authenticationErrorDialog.visible) {
            authenticationErrorDialog.close()
        }
        if (twoFactorRequiredDialog.visible) {
            twoFactorRequiredDialog.close()
        }
        if (clockErrorDialog.visible) {
            clockErrorDialog.close()
        }
        if (compatibilityDialog.visible) {
            compatibilityDialog.close()
        }
        if (npsDialog.visible) {
            npsDialog.close()
        }
        pageStack.clear()
    }

    function requestRunnerAction(action, argument) {
        if (runnerActionDialog.visible) {
            return
        }
        runnerActionDialog.actionId = action
        runnerActionDialog.argument = argument
        runnerActionDialog.open()
    }

    function synchronizeNavigationDrawerMode() {
        // Kirigami clears collapsible when a drawer becomes modal. Restore it
        // explicitly when returning to the wide layout so the framework's
        // internal assignment cannot permanently remove the collapse button.
        if (navigationDrawer.modal) {
            navigationDrawer.collapsible = false
            navigationDrawer.collapsed = false
            navigationDrawer.close()
            return
        }
        navigationDrawer.collapsible = true
        navigationDrawer.open()
        navigationDrawer.collapsed = root.navigationSidebarCollapsed
    }

    function requireNavigationDrawerState(condition, description) {
        if (condition) {
            return true
        }
        console.error("navigation-drawer-smoke: " + description)
        navigationDrawerDiagnostics.stop()
        Qt.exit(2)
        return false
    }

    function maybeShowNpsSurvey() {
        if (root.visible && vpnController.npsSurveyAvailable
                && !npsDialog.visible) {
            npsDialog.open()
        }
    }

    function maybeShowCompatibilityWarning() {
        if (vpnController.ready && !vpnController.startupCompatible
                && !root.compatibilityWarningShown) {
            root.compatibilityWarningShown = true
            root.show()
            root.raise()
            root.requestActivate()
            compatibilityDialog.open()
        }
    }

    function showConnectionRecoveryDialog(code) {
        let dialog = null
        if (code === "maximum_sessions_reached") {
            dialog = sessionLimitDialog
        } else if (code === "authentication_denied") {
            dialog = authenticationErrorDialog
        } else if (code === "two_factor_required") {
            dialog = twoFactorRequiredDialog
        } else if (code === "certificate_not_yet_valid") {
            dialog = clockErrorDialog
        }
        if (dialog !== null) {
            root.show()
            root.raise()
            root.requestActivate()
            dialog.open()
        }
    }

    Component.onCompleted: {
        if (initialPageName === "settings") {
            root.showSettings()
        } else if (initialPageName === "locations") {
            root.showLocations()
        } else if (initialPageName === "account") {
            root.showAccount()
        } else if (initialPageName === "sign-in") {
            root.showSignIn()
        } else if (initialPageName === "about") {
            root.showAbout()
        } else if (initialPageName === "report-issue") {
            root.showReportIssue()
        } else if (initialPageName === "release-notes") {
            root.showReleaseNotes()
        } else if (!vpnController.ready || !vpnController.loggedIn) {
            root.showSignIn()
        } else {
            root.showOverview()
        }
        Qt.callLater(root.resolveStartupAccountRoute)
        Qt.callLater(root.maybeShowCompatibilityWarning)
        if (diagnosticSmokeTest) {
            diagnosticNavigation.start()
        }
        if (settingsRouteSmokeTest) {
            settingsRouteNavigation.start()
        }
    }
    onVisibleChanged: {
        Qt.callLater(root.maybeShowNpsSurvey)
        Qt.callLater(root.maybeShowCompatibilityWarning)
    }

    property bool previousLoggedIn: vpnController.loggedIn
    property bool startupAccountRoutingPending: initialPageName === "overview"
    property string previousErrorCode: ""
    property bool compatibilityWarningShown: false
    property var ownedPages: []
    property int diagnosticNavigationStep: 0
    property int settingsRouteNavigationStep: 0
    property int navigationDrawerDiagnosticStep: 0
    property bool settingsRouteExpectedModerateNat: false
    property bool navigationSidebarCollapsed: false
    property bool navigationDrawerDiagnosticsComplete: !diagnosticSmokeTest
    property real navigationDrawerDiagnosticOriginalWidth: width
    property string currentSection: "overview"
    readonly property real navigationCompactBreakpoint:
        Kirigami.Units.gridUnit * 46
    readonly property string appIconSource:
        appSettings.iconStyle === "light"
        ? "qrc:/data/plasma-vpn-light.svg"
        : appSettings.iconStyle === "dark"
          ? "qrc:/data/plasma-vpn-dark.svg"
          : "qrc:/data/plasma-vpn.svg"

    Component {
        id: overviewPageComponent
        OverviewPage { }
    }

    Connections {
        target: pageStack
        function onPageRemoved(page) {
            root.releaseOwnedPage(page)
        }
    }

    Component {
        id: locationsPageComponent
        LocationsPage { }
    }

    Component {
        id: countryPageComponent
        CountryPage { }
    }

    Component {
        id: serversPageComponent
        ServersPage { }
    }

    Component {
        id: accountPageComponent
        AccountPage { }
    }

    Component {
        id: signInPageComponent
        SignInPage { }
    }

    Component {
        id: settingsPageComponent
        SettingsPage { }
    }

    Component {
        id: customDnsPageComponent
        CustomDnsPage { }
    }

    Component {
        id: splitTunnelingPageComponent
        SplitTunnelingPage { }
    }

    Component {
        id: releaseNotesPageComponent
        ReleaseNotesPage { }
    }

    Component {
        id: reportIssuePageComponent
        ReportIssuePage { }
    }

    Component {
        id: aboutPageComponent
        AboutPage { }
    }

    Timer {
        id: diagnosticNavigation
        interval: 120
        repeat: true
        onTriggered: {
            if (!root.navigationDrawerDiagnosticsComplete) {
                return
            }
            switch (root.diagnosticNavigationStep) {
            case 0:
                console.info("diagnostics-smoke: Overview")
                root.showOverview()
                break
            case 1:
                console.info("diagnostics-smoke: Locations")
                root.showLocations()
                break
            case 2:
                console.info("diagnostics-smoke: Country")
                root.pushCountry({
                    "countryCode": "CH",
                    "countryName": "Switzerland",
                    "countryFlag": "🇨🇭",
                    "countryAccessible": true,
                    "countryUnderMaintenance": false
                })
                break
            case 3:
                console.info("diagnostics-smoke: Servers")
                root.pushServers({
                    "countryCode": "CH",
                    "countryName": "Switzerland",
                    "countryFlag": "🇨🇭",
                    "groupKind": "location",
                    "groupName": "Zurich",
                    "groupAccessible": true,
                    "groupUnderMaintenance": false
                })
                break
            case 4:
                console.info("diagnostics-smoke: Account")
                root.showAccount()
                break
            case 5:
                console.info("diagnostics-smoke: Settings")
                root.showSettings()
                break
            case 6:
                console.info("diagnostics-smoke: Custom DNS")
                root.pushCustomDns()
                break
            case 7:
                console.info("diagnostics-smoke: Settings reload")
                root.showSettings()
                break
            case 8:
                console.info("diagnostics-smoke: Split tunneling")
                root.pushSplitTunneling()
                break
            case 9:
                console.info("diagnostics-smoke: Release notes")
                root.showReleaseNotes()
                break
            case 10:
                console.info("diagnostics-smoke: Report issue")
                root.showReportIssue()
                break
            case 11:
                console.info("diagnostics-smoke: About")
                root.showAbout()
                break
            case 12:
                console.info("diagnostics-smoke: Sign in")
                root.showSignIn()
                break
            case 13:
                console.info("diagnostics-smoke: Overview reload")
                root.showOverview()
                break
            case 14:
                root.requestRunnerAction("fastest", "")
                if (!runnerActionDialog.visible
                        || vpnController.state !== "disconnected") {
                    stop()
                    console.error("diagnostics-smoke: KRunner request bypassed confirmation")
                    Qt.exit(2)
                    return
                }
                console.info("diagnostics-smoke: KRunner confirmation required")
                break
            case 15:
                runnerActionDialog.accept()
                break
            case 16:
                if (vpnController.state !== "connected") {
                    return
                }
                root.requestRunnerAction("disconnect", "")
                if (!runnerActionDialog.visible) {
                    stop()
                    console.error("diagnostics-smoke: KRunner disconnect confirmation missing")
                    Qt.exit(2)
                    return
                }
                break
            case 17:
                runnerActionDialog.accept()
                break
            case 18:
                if (vpnController.state !== "disconnected") {
                    return
                }
                console.info("diagnostics-smoke: KRunner confirmed actions complete")
                break
            default:
                stop()
                console.info("diagnostics-smoke: complete")
                Qt.quit()
                return
            }
            ++root.diagnosticNavigationStep
        }
    }

    Timer {
        id: navigationDrawerDiagnostics
        interval: 120
        repeat: true
        running: diagnosticSmokeTest
        onTriggered: {
            const wideWidth = Math.max(
                900, root.navigationCompactBreakpoint + Kirigami.Units.gridUnit)
            const compactWidth = Math.max(
                root.minimumWidth,
                root.navigationCompactBreakpoint - Kirigami.Units.gridUnit)
            switch (root.navigationDrawerDiagnosticStep) {
            case 0:
                root.width = wideWidth
                break
            case 1:
                if (!root.requireNavigationDrawerState(
                        !navigationDrawer.modal
                        && navigationDrawer.collapsible
                        && navigationDrawer.drawerOpen
                        && !navigationDrawer.collapsed,
                        "wide layout did not expose an expanded collapsible sidebar")) {
                    return
                }
                navigationDrawer.collapsed = true
                break
            case 2:
                if (!root.requireNavigationDrawerState(
                        navigationDrawer.collapsed
                        && root.navigationSidebarCollapsed,
                        "wide layout did not retain the requested collapsed state")) {
                    return
                }
                root.width = compactWidth
                break
            case 3:
                if (!root.requireNavigationDrawerState(
                        navigationDrawer.modal
                        && !navigationDrawer.collapsible
                        && !navigationDrawer.collapsed
                        && !navigationDrawer.drawerOpen
                        && navigationDrawer.handleVisible
                        && navigationDrawer.handle.handleAnchor !== null
                        && navigationDrawer.handle.handleAnchor.visible,
                        "compact layout did not expose a closed overlay with an open handle")) {
                    return
                }
                navigationDrawer.open()
                break
            case 4:
                if (!root.requireNavigationDrawerState(
                        navigationDrawer.modal
                        && navigationDrawer.drawerOpen,
                        "compact navigation handle could not open the overlay")) {
                    return
                }
                navigationDrawer.close()
                root.width = wideWidth
                break
            case 5:
                if (!root.requireNavigationDrawerState(
                        !navigationDrawer.modal
                        && navigationDrawer.collapsible
                        && navigationDrawer.drawerOpen
                        && navigationDrawer.collapsed,
                        "wide layout did not restore the sidebar and collapse control")) {
                    return
                }
                navigationDrawer.collapsed = false
                break
            default:
                if (!root.requireNavigationDrawerState(
                        !navigationDrawer.collapsed
                        && !root.navigationSidebarCollapsed,
                        "wide sidebar could not be expanded again")) {
                    return
                }
                stop()
                root.width = root.navigationDrawerDiagnosticOriginalWidth
                root.navigationDrawerDiagnosticsComplete = true
                console.info("navigation-drawer-smoke: complete")
                return
            }
            ++root.navigationDrawerDiagnosticStep
        }
    }

    Timer {
        id: settingsRouteNavigation
        interval: 50
        repeat: true
        onTriggered: {
            if (root.settingsRouteNavigationStep === 0) {
                if (!vpnController.ready || !vpnController.loggedIn) {
                    return
                }
                root.showSignIn()
                root.settingsRouteNavigationStep = 1
                return
            }
            if (root.settingsRouteNavigationStep === 1) {
                root.showSettings()
                root.settingsRouteNavigationStep = 2
                return
            }
            if (root.settingsRouteNavigationStep === 2) {
                if (!vpnController.settings.loaded
                        || vpnController.settings.busy) {
                    return
                }
                root.settingsRouteExpectedModerateNat =
                    !vpnController.settings.moderateNat
                vpnController.updateSetting(
                    "moderateNat", root.settingsRouteExpectedModerateNat)
                root.settingsRouteNavigationStep = 3
                return
            }
            if (vpnController.settings.busy
                    || vpnController.settings.moderateNat
                       !== root.settingsRouteExpectedModerateNat) {
                return
            }
            stop()
            console.info("settings-route-smoke: current section",
                         root.currentSection)
            console.info("settings-route-smoke: owned pages",
                         root.ownedPages.length)
        }
    }

    Controls.Dialog {
        id: runnerActionDialog
        anchors.centerIn: parent
        width: Math.min(root.width - Kirigami.Units.gridUnit * 2,
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
                    return vpnController.ready && !vpnController.busy
                })
            }
        }
        onAccepted: {
            const confirmedAction = actionId
            const confirmedArgument = argument
            clearRequest()
            if (confirmedAction === "fastest") {
                vpnController.connectFastestWithFeatures(
                    appSettings.fastestFeatures)
            } else if (confirmedAction === "disconnect") {
                vpnController.disconnect()
            } else if (confirmedAction === "country") {
                vpnController.connectCountry(confirmedArgument)
            } else if (confirmedAction === "server") {
                vpnController.connectServer(confirmedArgument)
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
        target: vpnController
        function onSnapshotChanged() {
            root.resolveStartupAccountRoute()
            Qt.callLater(root.maybeShowCompatibilityWarning)
            if (root.previousLoggedIn && !vpnController.loggedIn) {
                root.showSignIn()
            }
            if (vpnController.errorCode.length > 0
                    && vpnController.errorCode !== root.previousErrorCode) {
                root.showConnectionRecoveryDialog(vpnController.errorCode)
            }
            root.previousLoggedIn = vpnController.loggedIn
            root.previousErrorCode = vpnController.errorCode
        }
        function onNpsSurveyChanged() {
            Qt.callLater(root.maybeShowNpsSurvey)
        }
    }

    globalDrawer: Kirigami.GlobalDrawer {
        id: navigationDrawer
        title: qsTr("Plasma VPN")
        titleIcon: root.appIconSource
        handleClosedIcon.name: "application-menu"
        handleOpenIcon.name: "application-menu"
        isMenu: false
        modal: root.width < root.navigationCompactBreakpoint
        collapsible: false
        interactiveResizeEnabled: !modal
        preferredSize: Kirigami.Units.gridUnit * 14
        minimumSize: Kirigami.Units.gridUnit * 12
        maximumSize: Kirigami.Units.gridUnit * 18

        Component.onCompleted: Qt.callLater(root.synchronizeNavigationDrawerMode)
        onModalChanged: {
            Qt.callLater(root.synchronizeNavigationDrawerMode)
        }
        onCollapsedChanged: {
            if (!modal) {
                root.navigationSidebarCollapsed = collapsed
            }
        }

        actions: [
            Kirigami.Action {
                text: qsTr("Overview")
                icon.source: root.appIconSource
                checkable: true
                checked: root.currentSection === "overview"
                onTriggered: root.showOverview()
            },
            Kirigami.Action {
                text: qsTr("Countries and servers")
                icon.name: "network-server"
                enabled: vpnController.loggedIn
                checkable: true
                checked: root.currentSection === "locations"
                onTriggered: root.showLocations()
            },
            Kirigami.Action {
                text: vpnController.loggedIn ? qsTr("Account") : qsTr("Sign in")
                icon.name: vpnController.loggedIn ? "user-identity" : "system-log-in"
                checkable: true
                checked: root.currentSection === "account"
                onTriggered: vpnController.loggedIn
                             ? root.showAccount() : root.showSignIn()
            },
            Kirigami.Action {
                text: qsTr("Settings")
                icon.name: "settings-configure"
                checkable: true
                checked: root.currentSection === "settings"
                onTriggered: root.showSettings()
            },
            Kirigami.Action {
                text: qsTr("Release notes")
                icon.name: "view-pim-notes"
                checkable: true
                checked: root.currentSection === "release-notes"
                onTriggered: root.showReleaseNotes()
            },
            Kirigami.Action {
                text: qsTr("Report an issue")
                icon.name: "tools-report-bug"
                enabled: vpnController.loggedIn
                checkable: true
                checked: root.currentSection === "report-issue"
                onTriggered: root.showReportIssue()
            },
            Kirigami.Action {
                text: qsTr("About")
                icon.name: "help-about"
                checkable: true
                checked: root.currentSection === "about"
                onTriggered: root.showAbout()
            },
            Kirigami.Action {
                text: qsTr("Close Control Center")
                icon.name: "application-exit"
                onTriggered: Qt.quit()
            }
        ]
    }
}
