#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture_root="$(mktemp -d)"
fixture_dir="$fixture_root/repository"
feedback_fixture_dir="$fixture_root/feedback-repository"
busy_fixture_dir="$fixture_root/busy-repository"
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

git clone --quiet --no-hardlinks "$project_dir" "$feedback_fixture_dir"
perl -0pi -e \
    's/\n\s*applicationWindow\(\)\.beginConnectionAction\(\n\s*"connected"\)(\n\s*vpnController\.connectServer\(resultDelegate\.name\))/\1/' \
    "$feedback_fixture_dir/qml/LocationsPage.qml"
if rg -U -q \
        'beginConnectionAction\(\n[[:space:]]*"connected"\)\n[[:space:]]*vpnController\.connectServer\(resultDelegate\.name\)' \
        "$feedback_fixture_dir/qml/LocationsPage.qml"; then
    echo "Unable to construct the feedback-ownership negative fixture" >&2
    exit 1
fi

feedback_output="$fixture_root/feedback-output"
if "$feedback_fixture_dir/scripts/check-qml-ui-hygiene.sh" \
        >"$feedback_output" 2>&1; then
    echo "The UI hygiene gate accepted an unowned connection action" >&2
    exit 1
fi
if ! rg -q 'Connection action lacks explicit feedback ownership' \
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
