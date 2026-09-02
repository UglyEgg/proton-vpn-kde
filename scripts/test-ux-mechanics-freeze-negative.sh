#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture_root="$(mktemp -d)"
fixture_dir="$fixture_root/repository"
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
