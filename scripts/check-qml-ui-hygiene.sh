#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
qml_dir="$project_dir/qml"
ci_workflow="$project_dir/.github/workflows/ci.yml"

ci_job_block() {
    local job_name="$1"
    awk -v header="  $job_name:" '
        $0 == header { in_job = 1; seen_header = 1 }
        in_job && seen_header && $0 != header && \
            $0 ~ /^  [[:alnum:]_-]+:/ { exit }
        in_job { print }
    ' "$ci_workflow"
}

for ci_job in fedora native-analysis; do
    job_block="$(ci_job_block "$ci_job")"
    if [[ -z "$job_block" ]]; then
        echo "Source CI job '$ci_job' is missing" >&2
        exit 1
    fi
    for dependency in plasma-breeze-common plasma-integration; do
        if ! grep -Eq \
                "(^|[[:space:]])$dependency([[:space:]\\\\]|$)" \
                <<<"$job_block"; then
            echo "Source CI job '$ci_job' must install $dependency" >&2
            exit 1
        fi
    done
    if ! grep -Fq 'fetch-depth: 0' <<<"$job_block"; then
        echo "Source CI job '$ci_job' must use a full Git checkout for history-sensitive tests" >&2
        exit 1
    fi
done

if ! rg -q '^BuildRequires:[[:space:]]+ripgrep[[:space:]]*$' \
        "$project_dir/packaging/fedora/proton-vpn-kde.spec"; then
    echo "RPM %check requires ripgrep for the QML hygiene gate" >&2
    exit 1
fi

if rg -n 'font\.(pixelSize|pointSize)\s*:' "$qml_dir"; then
    echo "Use theme fonts and heading levels instead of fixed font sizes" >&2
    exit 1
fi

# Descriptions and label/value facts describe available information, not
# disabled controls. Inherit the theme's normal text contrast for these.
if rg -n 'Kirigami.Theme.disabledTextColor' \
        "$qml_dir/PageHeader.qml" "$qml_dir/SectionCard.qml" \
        "$qml_dir/DetailRow.qml"; then
    echo "Shared informational text must not use disabled-control styling" >&2
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
connection_feedback_owner_count="$(
    rg -n '^[[:space:]]*ConnectionActionFeedback[[:space:]]*\{' \
        "$qml_dir" | wc -l
)"
settings_cleanup_calls="$(
    rg -c 'page\.prepareForRemoval\(\)' "$qml_dir/Main.qml"
)"
if ! rg -q 'function prepareForRemoval\(\)' "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'Component\.onDestruction: prepareForRemoval\(\)' \
        "$qml_dir/SettingsPage.qml" \
        || [[ "$settings_cleanup_calls" -lt 2 ]] \
        || ! rg -q 'close\.accepted = vpnController\.requestShutdown\(\)' \
        "$qml_dir/Main.qml" \
        || ! rg -q 'function requestApplicationQuit\(\)' "$qml_dir/Main.qml" \
        || ! rg -q 'vpnController\.npsSurveySubmissionPending' \
        "$qml_dir/MainDialogs.qml" \
        || ! rg -q 'onNpsSurveySubmissionFinished' "$qml_dir/MainDialogs.qml" \
        || rg -U -q 'submitNpsSurvey\([^)]*\)\n[[:space:]]*npsDialog\.submitted = true' \
        "$qml_dir/MainDialogs.qml"; then
    echo "Page retirement, application shutdown, and survey completion must retain explicit operation ownership" >&2
    exit 1
fi

# Capture action admission is exercised against the actual component by
# sign-in-presentation-tests, including busy, unavailable and expired states.

recovery_state_fixture="$(
    sed -n \
        '/readonly property bool recoveryRequired:/,/].includes(vpnController.authState)/p' \
        "$qml_dir/SignInPage.qml"
)"
for recovery_state in \
        authentication_unknown settings_unavailable protection_unknown expired account_restart_required; do
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
        || ! rg -q 'id: applicationRecoveryBanner' \
        "$qml_dir/Main.qml" \
        || ! rg -q 'readonly property bool connectionErrorActive' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'readonly property bool snapshotErrorActive' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'vpnController\.snapshotError' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'objectName: "refreshInvalidSnapshotAction"' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'vpnController\.snapshotRefreshPending' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'readonly property bool packetCaptureErrorActive' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'property bool showPacketCaptureError' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'vpnController\.packetCaptureError' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'showPacketCaptureError:' "$qml_dir/Main.qml" \
        || ! rg -q 'pageStack\.currentItem\.objectName !== "settingsPage"' \
        "$qml_dir/Main.qml" \
        || ! rg -q 'objectName: "settingsPage"' \
        "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'objectName: "packetCaptureOperationError"' \
        "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'vpnController\.packetCaptureError' \
        "$qml_dir/SettingsPage.qml" \
        || ! rg -q 'readonly property bool bannerActive' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || rg -q 'statusMessageActive' \
        "$qml_dir/ApplicationRecoveryBanner.qml" \
        || ! rg -q 'objectName: "connectionActionFeedback"' \
        "$qml_dir/ConnectionActionFeedback.qml" \
        || ! rg -q 'function beginForOperation\(id, state\)' \
        "$qml_dir/ConnectionActionFeedback.qml" \
        || ! rg -q 'function onConnectionOperationStarted\(operationId, targetState\)' \
        "$qml_dir/ConnectionActionFeedback.qml" \
        || ! rg -q 'function onConnectionOperationFinished\(operationId, targetState,' \
        "$qml_dir/ConnectionActionFeedback.qml" \
        || [[ "$connection_feedback_owner_count" -ne 1 ]] \
        || ! rg -q 'ConnectionActionFeedback' "$qml_dir/Main.qml" \
        || rg -q 'ConnectionActionFeedback' \
        "$qml_dir/OverviewPage.qml" "$qml_dir/LocationsPage.qml" \
        "$qml_dir/CountryPage.qml" "$qml_dir/ServersPage.qml" \
        || ! rg -q 'ServerBrowserFeedback' "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'ServerBrowserFeedback' "$qml_dir/CountryPage.qml" \
        || ! rg -q 'ServerBrowserFeedback' "$qml_dir/ServersPage.qml" \
        || ! rg -q 'objectName: "serverBrowserLoadError"' \
        "$qml_dir/ServerBrowserFeedback.qml" \
        || ! rg -q 'vpnController\.countriesError' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'vpnController\.locationSearchError' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'vpnController\.serverGroupsError' \
        "$qml_dir/CountryPage.qml" \
        || ! rg -q 'vpnController\.serversError' \
        "$qml_dir/ServersPage.qml" \
        || ! rg -q 'vpnController\.serverLoadsError' \
        "$qml_dir/ServersPage.qml" \
        || ! rg -U -q 'visible: countryList\.count === 0\n[[:space:]]*&& vpnController\.countriesError\.length === 0' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -U -q 'visible: searchResults\.count === 0\n[[:space:]]*&& vpnController\.locationSearchError\.length === 0' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -U -q 'visible: groupList\.count === 0\n[[:space:]]*&& vpnController\.serverGroupsError\.length === 0' \
        "$qml_dir/CountryPage.qml" \
        || ! rg -U -q 'visible: serverList\.count === 0\n[[:space:]]*&& vpnController\.serversError\.length === 0' \
        "$qml_dir/ServersPage.qml" \
        || ! rg -q 'readonly property bool serverSearchActive' \
        "$qml_dir/ServersPage.qml" \
        || ! rg -q 'readonly property string emptyServerMessage' \
        "$qml_dir/ServersPage.qml" \
        || ! rg -q 'No servers match your search' \
        "$qml_dir/ServersPage.qml" \
        || ! rg -q 'objectName: "serverEmptyState"' \
        "$qml_dir/ServersPage.qml" \
        || rg -q 'beginConnectionAction|connectionActionStarted' \
        "$qml_dir/Main.qml" "$qml_dir/MainDialogs.qml" \
        "$qml_dir/OverviewPage.qml" "$qml_dir/LocationsPage.qml" \
        "$qml_dir/CountryPage.qml" "$qml_dir/ServersPage.qml" \
        || ! rg -U -q 'readonly property bool browserConnectionActionEnabled:\n[[:space:]]*controller\.canConnect' \
        "$qml_dir/Main.qml" \
        || rg -q 'vpnController\.primaryActionEnabled' \
        "$qml_dir/LocationsPage.qml" "$qml_dir/CountryPage.qml" \
        "$qml_dir/ServersPage.qml" \
        || ! rg -q 'browserConnectionActionEnabled' \
        "$qml_dir/LocationsPage.qml" "$qml_dir/CountryPage.qml" \
        "$qml_dir/ServersPage.qml" \
        || ! rg -q 'primaryEnabled: vpnController\.primaryActionEnabled' \
        "$qml_dir/OverviewPage.qml" \
        || ! rg -q 'connectionOperationStarted' \
        "$project_dir/src/VpnControllerActions.cpp" \
        || ! rg -q 'readonly property bool runnerActionEnabled' \
        "$qml_dir/MainDialogs.qml" \
        || ! rg -q 'vpnController\.canDisconnect' \
        "$qml_dir/MainDialogs.qml" \
        || ! rg -q 'vpnController\.canConnect' \
        "$qml_dir/MainDialogs.qml" \
        || rg -q 'vpnController\.primaryActionEnabled|!vpnController\.busy' \
        "$qml_dir/MainDialogs.qml" \
        || ! rg -U -q 'onAccepted: \{\n[[:space:]]*const confirmedAction.*\n[[:space:]]*const confirmedArgument.*\n[[:space:]]*if \(!dialogs\.runnerActionEnabled\)' \
        "$qml_dir/MainDialogs.qml" \
        || ! rg -q 'mainDialogs\.supportsRecovery\(code\)' \
        "$qml_dir/Main.qml" \
        || ! rg -q 'readonly property var recoveryErrorCodes' \
        "$qml_dir/MainDialogs.qml" \
        || ! rg -q 'Object\.keys\(recoveryDialogs\)' \
        "$qml_dir/MainDialogs.qml" \
        || rg -q 'if \(code ===' \
        "$qml_dir/MainDialogs.qml" \
        || rg -q 'function connectionErrorText' \
        "$qml_dir/OverviewPage.qml" \
        || ! rg -q 'running: parent\.visible && vpnController\.busy' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'readonly property bool terminalBackendFailure' \
        "$qml_dir/SignInPage.qml" \
        || ! rg -q 'enabled: vpnController\.ready' \
        "$qml_dir/SettingsPage.qml" \
        || ! rg -U -q 'enabled: vpnController\.ready\n[[:space:]]*&& vpnSettings\.loaded' \
        "$qml_dir/VpnConnectionSettingsSection.qml"; then
    echo "Backend failures must preserve diagnostics and expose only valid recovery actions" >&2
    exit 1
fi

if ! rg -q 'bool snapshotHealthy\(\) const' \
        "$project_dir/src/VpnController.h" \
        || ! rg -q '!snapshotHealthy\(\)' \
        "$project_dir/src/VpnControllerActions.cpp" \
        "$project_dir/src/VpnControllerSettings.cpp"; then
    echo "An invalid backend snapshot must fail closed for mutating operations" >&2
    exit 1
fi

if rg -q 'packetCaptureOperationFinished' \
        "$project_dir/src" "$project_dir/qml" "$project_dir/tests"; then
    echo "Packet-capture failures must use the authoritative typed state" >&2
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
