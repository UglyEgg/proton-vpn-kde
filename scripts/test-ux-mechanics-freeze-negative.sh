#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture_root="$(mktemp -d)"
fixture_dir="$fixture_root/repository"
feedback_fixture_dir="$fixture_root/feedback-repository"
busy_fixture_dir="$fixture_root/busy-repository"
controller_fixture_dir="$fixture_root/controller-repository"
trap 'rm -rf -- "$fixture_root"' EXIT

git clone --quiet --no-hardlinks "$project_dir" "$fixture_dir"

sed -i \
    's/vpnController.connectCountry(countryDelegate.code)/vpnController.connectCountry("")/' \
    "$fixture_dir/qml/LocationsPage.qml"
if ! rg -q 'vpnController\.connectCountry\(""\)' \
        "$fixture_dir/qml/LocationsPage.qml"; then
    echo "Unable to construct the mechanics-gate negative fixture" >&2
    exit 1
fi

gate_output="$fixture_root/gate-output"
if "$fixture_dir/scripts/check-ux-mechanics-freeze.sh" \
        >"$gate_output" 2>&1; then
    echo "The mechanics gate accepted a changed connection argument" >&2
    exit 1
fi
if ! rg -q 'QML presentation delta changed' "$gate_output"; then
    echo "The mechanics gate failed for an unexpected reason" >&2
    sed -n '1,120p' "$gate_output" >&2
    exit 1
fi

echo "The mechanics gate rejects changed QML operation arguments"

git clone --quiet --no-hardlinks "$project_dir" "$controller_fixture_dir"
sed -i \
    's/m_packetCaptureStopRequested = true;/m_packetCaptureStopRequested = false;/' \
    "$controller_fixture_dir/src/VpnControllerActions.cpp"
if rg -q 'm_packetCaptureStopRequested = true;' \
        "$controller_fixture_dir/src/VpnControllerActions.cpp"; then
    echo "Unable to construct the controller-state negative fixture" >&2
    exit 1
fi

controller_output="$fixture_root/controller-output"
if "$controller_fixture_dir/scripts/check-ux-mechanics-freeze.sh" \
        >"$controller_output" 2>&1; then
    echo "The mechanics gate accepted changed capture state ownership" >&2
    exit 1
fi
if ! rg -q 'frontend presentation contract delta changed' \
        "$controller_output"; then
    echo "The controller-state mechanics gate failed for an unexpected reason" >&2
    sed -n '1,120p' "$controller_output" >&2
    exit 1
fi

echo "The mechanics gate rejects changed controller state ownership"

git clone --quiet --no-hardlinks "$project_dir" "$feedback_fixture_dir"
perl -0pi -e \
    's/\n\s*function onConnectionOperationStarted\(operationId, targetState\) \{\n\s*root\.beginForOperation\(operationId, targetState\)\n\s*\}//' \
    "$feedback_fixture_dir/qml/ConnectionActionFeedback.qml"
if rg -q 'function onConnectionOperationStarted' \
        "$feedback_fixture_dir/qml/ConnectionActionFeedback.qml"; then
    echo "Unable to construct the feedback-ownership negative fixture" >&2
    exit 1
fi

feedback_output="$fixture_root/feedback-output"
if "$feedback_fixture_dir/scripts/check-qml-ui-hygiene.sh" \
        >"$feedback_output" 2>&1; then
    echo "The UI hygiene gate accepted an unowned connection action" >&2
    exit 1
fi
if ! rg -q 'Backend failures must preserve diagnostics' \
        "$feedback_output"; then
    echo "The UI hygiene gate failed for an unexpected reason" >&2
    sed -n '1,120p' "$feedback_output" >&2
    exit 1
fi

echo "The UI hygiene gate rejects unowned connection actions"

git clone --quiet --no-hardlinks "$project_dir" "$busy_fixture_dir"
sed -i \
    's/controller.primaryActionEnabled && !controller.busy/controller.primaryActionEnabled/' \
    "$busy_fixture_dir/qml/Main.qml"
if ! rg -q 'controller\.primaryActionEnabled$' \
        "$busy_fixture_dir/qml/Main.qml"; then
    echo "Unable to construct the busy browser-action negative fixture" >&2
    exit 1
fi

busy_output="$fixture_root/busy-output"
if "$busy_fixture_dir/scripts/check-qml-ui-hygiene.sh" \
        >"$busy_output" 2>&1; then
    echo "The UI hygiene gate accepted browser actions while busy" >&2
    exit 1
fi
if ! rg -q 'Backend failures must preserve diagnostics' "$busy_output"; then
    echo "The busy-action UI hygiene gate failed for an unexpected reason" >&2
    sed -n '1,120p' "$busy_output" >&2
    exit 1
fi

echo "The UI hygiene gate rejects browser connection actions while busy"
