#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
qml_dir="$project_dir/qml"

if rg -n 'font\.(pixelSize|pointSize)\s*:' "$qml_dir"; then
    echo "Use theme fonts and heading levels instead of fixed font sizes" >&2
    exit 1
fi

if rg -n "color\\s*:\\s*(['\"]#|Qt\\.(rgba|hsla)\\()" "$qml_dir"; then
    echo "Use Kirigami semantic colors instead of literal colors" >&2
    exit 1
fi

if rg -n '(NumberAnimation|ColorAnimation|PropertyAnimation)\s*\{' "$qml_dir"; then
    echo "Custom animation must explicitly honor the Plasma motion setting" >&2
    exit 1
fi

if rg -n 'Controls\.ToolTip\.visible:\s*hovered\s*$' "$qml_dir"; then
    echo "Tooltips on keyboard-focusable controls must appear for active focus" >&2
    exit 1
fi

if rg -n '(MouseArea|TapHandler)\s*\{' "$qml_dir"; then
    echo "Use keyboard- and accessibility-aware native controls for interaction" >&2
    exit 1
fi

if rg -n '(Timer|WorkerScript|WebSocket)\s*\{' \
        "$qml_dir/ConnectionInspectorPage.qml"; then
    echo "The on-demand Connection Inspector must not collect in the background" >&2
    exit 1
fi

if ! rg -q 'onSnapshotChanged' \
        "$qml_dir/ConnectionInspectorPage.qml" \
        || ! rg -q 'ensureInspectorModels\(\)' \
        "$qml_dir/ConnectionInspectorPage.qml"; then
    echo "The open Connection Inspector must recover its models after a backend snapshot changes" >&2
    exit 1
fi

if ! rg -q 'root\.mirrored.*go-previous-symbolic.*go-next-symbolic' \
        "$qml_dir/PlasmaListItem.qml"; then
    echo "The shared navigation row must preserve RTL directionality" >&2
    exit 1
fi

if ! rg -q 'id: connectionFacts' "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'signal copyPortRequested\(\)' \
        "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'onCopyPortRequested' "$qml_dir/OverviewPage.qml" \
        || ! rg -q 'root\.navigateRequested\("inspector"\)' \
        "$qml_dir/ConnectionScene.qml" \
        || rg -q 'connectionDetails(Dialog|Expanded|Toggle)' \
        "$qml_dir/OverviewPage.qml"; then
    echo "Overview must present compact connection facts and keep deeper inspection on demand" >&2
    exit 1
fi

if ! rg -q 'id: routeDiagram' "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'qsTr\("This device"\)' "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'qsTr\("Encrypted tunnel"\)' \
        "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'onNavigateRequested' "$qml_dir/OverviewPage.qml"; then
    echo "Overview must present the connection as a graphical device-to-destination route" >&2
    exit 1
fi

if ! rg -q 'objectName: "fastestServerCard"' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'qsTr\("Fastest suitable server"\)' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'qsTr\("Must support"\)' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'ServerCapabilitySelector' \
        "$qml_dir/LocationsPage.qml"; then
    echo "Server discovery must lead with a visible fastest-suitable intent and capability criteria" >&2
    exit 1
fi

if ! rg -q 'objectName: "settingsIntentBar"' \
        "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'Controls\.AbstractButton\.TextUnderIcon' \
        "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'currentIndex: settingsIntentBar\.currentIndex' \
        "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'qsTr\("Connection"\)' "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'qsTr\("Protection"\)' "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'qsTr\("Plasma"\)' "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'qsTr\("Diagnostics"\)' "$qml_dir/SettingsPage.qml"; then
    echo "Settings must group controls into native icon-led user intents" >&2
    exit 1
fi

if ! rg -q 'objectName: "authenticationStage"' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'readonly property int activeStep' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'objectName: "signingInStep"' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'page\.activeStep === page\.signingInStep' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'objectName: "twoFactorAuthenticationStep"' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'objectName: "securityKeyAuthenticationStep"' \
        "$qml_dir/SignInPage.qml"; then
    echo "Authentication must present one explicit active step, including sign-in progress and security-key waits" >&2
    exit 1
fi

backend_restart_policy_uses="$(
    rg -c 'vpnController\.backendRestartAllowed' \
        "$qml_dir/SignInPage.qml"
)"
recovery_state_fixture="$(
    sed -n \
        '/readonly property bool recoveryRequired:/,/].includes(vpnController.authState)/p' \
        "$qml_dir/SignInPage.qml"
)"
for recovery_state in \
        authentication_unknown settings_unavailable protection_unknown; do
    if ! grep -Fq "\"$recovery_state\"" <<<"$recovery_state_fixture"; then
        echo "Missing authentication recovery presentation for $recovery_state" >&2
        exit 1
    fi
done
if ! rg -q 'objectName: "backendStartupDiagnostic"' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -U -q 'activeStep === page\.recoveryStep\) \{\n[[:space:]]*return vpnController\.message\.length > 0\n[[:space:]]*\? vpnController\.message' \
        "$qml_dir/SignInPage.qml" \
        || [[ "$backend_restart_policy_uses" -lt 3 ]] \
        || ! rg -q 'objectName: "restartUnresponsiveBackendAction"' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'objectName: "applicationBackendRecovery"' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'vpnController\.state === "unresponsive"' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'footer: ApplicationRecoveryBanner' \
        "$qml_dir/Main.qml" \
        || ! rg -q 'running: parent\.visible && vpnController\.busy' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'readonly property bool terminalBackendFailure' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'enabled: vpnController\.ready' \
        "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'backendReady: vpnController\.ready' \
        "$qml_dir/SettingsPage.qml"; then
    echo "Backend failures must preserve diagnostics and expose only valid recovery actions" >&2
    exit 1
fi

if ! rg -q 'id: moreAction' "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'text: qsTr\("More options"\)' \
        "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'icon.name: "configure"' \
        "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'text: qsTr\("Help & information"\)' \
        "$qml_dir/ConnectionScene.qml" \
        || rg -q 'onTriggered: root\.navigateRequested\("(release-notes|report-issue)"\)' \
        "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'objectName: "secondaryInformationHub"' \
        "$qml_dir/AboutPage.qml" \
        || ! rg -q 'applicationWindow\(\)\.openOverviewDestination\(' \
        "$qml_dir/AboutPage.qml" \
        || ! rg -q '"release-notes"' "$qml_dir/AboutPage.qml" \
        || ! rg -q '"report-issue"' "$qml_dir/AboutPage.qml" \
        || rg -q 'globalDrawer\s*:' "$qml_dir/Main.qml"; then
    echo "Overview must keep one secondary information hub without a persistent sidebar or redundant project routes" >&2
    exit 1
fi
