// SPDX-FileCopyrightText: 2026 Plasma VPN contributors
// SPDX-License-Identifier: GPL-3.0-or-later

import QtQuick
import org.kde.kirigami as Kirigami

Kirigami.ApplicationWindow {
    id: root

    width: diagnosticWindowWidth > 0 ? diagnosticWindowWidth : 900
    height: diagnosticWindowHeight > 0 ? diagnosticWindowHeight : 560
    minimumWidth: 480
    minimumHeight: 560
    visible: !startMinimized
    title: qsTr("Plasma VPN")
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    // The connection canvas is the navigation home. Keep drill-in pages on a
    // single full-width stack so their native Back action always returns home.
    pageStack.defaultColumnWidth: pageStack.width
    readonly property var controller: vpnController
    readonly property var integrationSettings: appSettings

    footer: Column {
        width: root.width
        spacing: applicationRecoveryBanner.visible
                 && globalConnectionActionFeedback.visible
                 ? Kirigami.Units.smallSpacing : 0
        height: childrenRect.height

        ApplicationRecoveryBanner {
            id: applicationRecoveryBanner
            width: parent.width
            vpnController: root.controller
            dialogErrorCodes: mainDialogs.recoveryErrorCodes
        }

        ConnectionActionFeedback {
            id: globalConnectionActionFeedback
            width: parent.width
            controller: root.controller
        }
    }

    onClosing: close => {
        close.accepted = true
    }

    function beginConnectionAction(expectedState) {
        globalConnectionActionFeedback.beginForState(expectedState)
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
        // PageRow has detached the item, but its toolbar transition may still
        // hold bindings until the animation completes.
        page.destroy(Kirigami.Units.longDuration * 2)
    }

    function showPage(pageComponent, properties) {
        pageStack.clear()
        return pushOwnedPage(pageComponent, properties)
    }

    function pushOverviewPage(pageComponent, section) {
        root.currentSection = section
        return pushOwnedPage(pageComponent)
    }

    function showOverviewPage(pageComponent, section) {
        root.showOverview()
        return root.pushOverviewPage(pageComponent, section)
    }

    function openOverviewDestination(destination) {
        if (destination === "settings") {
            root.pushOverviewPage(settingsPageComponent, "settings")
        } else if (destination === "locations") {
            root.pushOverviewPage(locationsPageComponent, "locations")
        } else if (destination === "account") {
            root.pushOverviewPage(accountPageComponent, "account")
        } else if (destination === "inspector") {
            root.pushOverviewPage(connectionInspectorPageComponent, "inspector")
        } else if (destination === "release-notes") {
            root.pushOverviewPage(releaseNotesPageComponent, "release-notes")
        } else if (destination === "report-issue") {
            root.pushOverviewPage(reportIssuePageComponent, "report-issue")
        } else if (destination === "about") {
            root.pushOverviewPage(aboutPageComponent, "about")
        } else if (destination === "close") {
            Qt.quit()
        } else {
            console.error("Unknown Overview destination: " + destination)
        }
    }

    function closeOverviewDestination() {
        if (pageStack.depth <= 1) {
            return false
        }
        pageStack.pop()
        return true
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
        return root.showOverviewPage(settingsPageComponent, "settings")
    }

    function showSignIn() {
        root.currentSection = "account"
        showPage(signInPageComponent)
    }

    function showLocations() {
        return root.showOverviewPage(locationsPageComponent, "locations")
    }

    function showConnectionInspector() {
        return root.showOverviewPage(
            connectionInspectorPageComponent, "inspector")
    }

    function showAccount() {
        return root.showOverviewPage(accountPageComponent, "account")
    }

    function showReleaseNotes() {
        return root.showOverviewPage(
            releaseNotesPageComponent, "release-notes")
    }

    function showReportIssue() {
        return root.showOverviewPage(reportIssuePageComponent, "report-issue")
    }

    function showAbout() {
        return root.showOverviewPage(aboutPageComponent, "about")
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
        if (mainDialogs.supportsRecovery(code)) {
            root.show()
            root.raise()
            root.requestActivate()
            mainDialogs.openRecovery(code)
        }
    }

    Component.onCompleted: {
        if (initialPageName === "settings") {
            root.showSettings()
        } else if (initialPageName === "settings-protection") {
            root.showSettings().showIntent(1)
        } else if (initialPageName === "settings-plasma") {
            root.showSettings().showIntent(2)
        } else if (initialPageName === "settings-diagnostics") {
            root.showSettings().showIntent(3)
        } else if (initialPageName === "locations") {
            root.showLocations()
        } else if (initialPageName === "inspector") {
            root.showConnectionInspector()
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
    property bool settingsRouteExpectedModerateNat: false
    property string currentSection: "overview"
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
        function onCurrentItemChanged() {
            if (pageStack.currentItem !== null
                    && pageStack.currentItem.objectName === "overviewPage") {
                root.currentSection = "overview"
            }
        }
    }

    Component {
        id: locationsPageComponent
        LocationsPage { }
    }

    Component {
        id: connectionInspectorPageComponent
        ConnectionInspectorPage { }
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
                const informationPage = root.showAbout()
                if (informationPage === null
                        || informationPage.objectName
                           !== "secondaryInformationHub") {
                    stop()
                    console.error("diagnostics-smoke: secondary information hub unavailable")
                    Qt.exit(2)
                    return
                }
                console.info("diagnostics-smoke: Help and information")
                break
            case 12:
                console.info("diagnostics-smoke: Sign in")
                root.showSignIn()
                break
            case 13:
                console.info("diagnostics-smoke: Connection Inspector")
                root.showConnectionInspector()
                break
            case 14:
                console.info("diagnostics-smoke: Overview reload")
                root.showOverview()
                break
            case 15:
                const collapsedOverview = pageStack.currentItem
                if (collapsedOverview.objectName !== "overviewPage"
                        || collapsedOverview.connectionFactsVisible
                        || !collapsedOverview.graphicalRouteVisible
                        || !collapsedOverview.homeNavigationVisible) {
                    stop()
                    console.error("diagnostics-smoke: Overview did not begin with graphical home navigation and hidden inactive facts")
                    Qt.exit(2)
                    return
                }
                console.info("diagnostics-smoke: Overview home navigation")
                console.info("diagnostics-smoke: Overview graphical route")
                console.info("diagnostics-smoke: Overview inactive facts hidden")
                root.openOverviewDestination("settings")
                break
            case 16:
                if (pageStack.depth !== 2
                        || root.currentSection !== "settings") {
                    stop()
                    console.error("diagnostics-smoke: Overview destination did not use the back stack")
                    Qt.exit(2)
                    return
                }
                pageStack.pop()
                break
            case 17:
                if (pageStack.depth !== 1
                        || pageStack.currentItem.objectName !== "overviewPage") {
                    return
                }
                console.info("diagnostics-smoke: Overview back navigation")
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
            case 18:
                mainDialogs.acceptRunnerAction()
                break
            case 19:
                if (vpnController.state !== "connected") {
                    return
                }
                const connectedOverview = pageStack.currentItem
                if (!connectedOverview.connectionFactsVisible) {
                    stop()
                    console.error("diagnostics-smoke: Overview connection facts did not appear")
                    Qt.exit(2)
                    return
                }
                console.info("diagnostics-smoke: Overview connection facts visible")
                break
            case 20:
                root.requestRunnerAction("disconnect", "")
                if (!mainDialogs.runnerActionVisible) {
                    stop()
                    console.error("diagnostics-smoke: KRunner disconnect confirmation missing")
                    Qt.exit(2)
                    return
                }
                break
            case 21:
                mainDialogs.acceptRunnerAction()
                break
            case 22:
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
                const settingsPage = pageStack.currentItem
                settingsPage.showIntent(1)
                if (settingsPage.selectedIntent !== 1) {
                    stop()
                    console.error("settings-route-smoke: unable to select Protection intent")
                    Qt.exit(2)
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
            console.info("settings-route-smoke: stack depth",
                         pageStack.depth)
            console.info("settings-route-smoke: selected intent",
                         pageStack.currentItem.selectedIntent)
        }
    }

    MainDialogs {
        id: mainDialogs
        anchors.fill: parent
        vpnController: root.controller
        appSettings: root.integrationSettings
        windowWidth: root.width
        onConnectionActionStarted: expectedState =>
            root.beginConnectionAction(expectedState)
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

}
