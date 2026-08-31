// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
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
    readonly property var controller: vpnController
    readonly property var integrationSettings: appSettings

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
        mainDialogs.closeAll()
        pageStack.clear()
    }

    function requestRunnerAction(action, argument) {
        mainDialogs.requestRunnerAction(action, argument)
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
                && !mainDialogs.npsVisible) {
            mainDialogs.openNps()
        }
    }

    function maybeShowCompatibilityWarning() {
        if (vpnController.ready && !vpnController.startupCompatible
                && !root.compatibilityWarningShown) {
            root.compatibilityWarningShown = true
            root.show()
            root.raise()
            root.requestActivate()
            mainDialogs.openCompatibility()
        }
    }

    function showConnectionRecoveryDialog(code) {
        const supported = [
            "maximum_sessions_reached",
            "authentication_denied",
            "two_factor_required",
            "certificate_not_yet_valid"
        ].includes(code)
        if (supported) {
            root.show()
            root.raise()
            root.requestActivate()
            mainDialogs.openRecovery(code)
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
                if (!mainDialogs.runnerActionVisible
                        || vpnController.state !== "disconnected") {
                    stop()
                    console.error("diagnostics-smoke: KRunner request bypassed confirmation")
                    Qt.exit(2)
                    return
                }
                console.info("diagnostics-smoke: KRunner confirmation required")
                break
            case 15:
                mainDialogs.acceptRunnerAction()
                break
            case 16:
                if (vpnController.state !== "connected") {
                    return
                }
                root.requestRunnerAction("disconnect", "")
                if (!mainDialogs.runnerActionVisible) {
                    stop()
                    console.error("diagnostics-smoke: KRunner disconnect confirmation missing")
                    Qt.exit(2)
                    return
                }
                break
            case 17:
                mainDialogs.acceptRunnerAction()
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

    MainDialogs {
        id: mainDialogs
        anchors.fill: parent
        vpnController: root.controller
        appSettings: root.integrationSettings
        windowWidth: root.width
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
