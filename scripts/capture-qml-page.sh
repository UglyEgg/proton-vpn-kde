#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"
page_name="${2:-overview}"
output_path="${3:?output path required}"
staging_dir="$(mktemp -d)"
backend_pid=""

cleanup() {
    if [[ -n "$backend_pid" ]]; then
        kill "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
    fi
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

PYTHONPATH="$project_dir/backend" \
    /usr/bin/python3 -m proton_vpn_kde_backend --demo \
    >"$staging_dir/backend.log" 2>&1 &
backend_pid=$!

for _ in {1..40}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        quest.entropy.PlasmaVPN.Backend 2>/dev/null)" == "(true,)" ]]; then
        break
    fi
    sleep 0.05
done

owner_reply="$(gdbus call --session \
    --dest org.freedesktop.DBus \
    --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.GetNameOwner \
    quest.entropy.PlasmaVPN.Backend)"
backend_owner="${owner_reply#*\'}"
backend_owner="${backend_owner%%\'*}"

if [[ "$page_name" == "overview-connected" ]]; then
    gdbus call --session \
        --dest quest.entropy.PlasmaVPN.Backend \
        --object-path /quest/entropy/PlasmaVPN/Backend \
        --method quest.entropy.PlasmaVPN.Backend1.ConnectFastest \
        >/dev/null
    for _ in {1..20}; do
        snapshot="$(gdbus call --session \
            --dest quest.entropy.PlasmaVPN.Backend \
            --object-path /quest/entropy/PlasmaVPN/Backend \
            --method quest.entropy.PlasmaVPN.Backend1.GetSnapshot)"
        if [[ "$snapshot" == *'"state":"connected"'* ]]; then
            break
        fi
        sleep 0.05
    done
    if [[ "$snapshot" != *'"state":"connected"'* ]]; then
        echo "Demo backend did not reach the connected state" >&2
        exit 1
    fi
    page_name="overview"
fi

env \
    QT_QPA_PLATFORM=offscreen \
    QT_QUICK_BACKEND=software \
    QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-generic}" \
    QT_ACCESSIBILITY=0 \
    XDG_CACHE_HOME="$staging_dir/cache" \
    XDG_CONFIG_HOME="$staging_dir/config" \
    PROTON_VPN_KDE_TEST_BACKEND_OWNER="$backend_owner" \
    "$build_dir/proton-vpn-kde" \
        --visual-page "$page_name" \
        --visual-snapshot "$output_path"
