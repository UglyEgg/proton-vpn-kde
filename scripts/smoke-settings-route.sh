#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"
staging_dir="$(mktemp -d)"
backend_pid=""
frontend_pid=""

cleanup() {
    if [[ -n "$frontend_pid" ]]; then
        kill "$frontend_pid" 2>/dev/null || true
        wait "$frontend_pid" 2>/dev/null || true
    fi
    if [[ -n "$backend_pid" ]]; then
        kill "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
    fi
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

if [[ -n "${PROTON_KDE_BACKEND_EXECUTABLE:-}" ]]; then
    "$PROTON_KDE_BACKEND_EXECUTABLE" --demo \
        >"$staging_dir/backend.log" 2>&1 &
else
    PYTHONPATH="$project_dir/backend" \
        /usr/bin/python3 -m proton_vpn_kde_backend --demo \
        >"$staging_dir/backend.log" 2>&1 &
fi
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

frontend_log="$staging_dir/frontend.log"
env \
    QT_QPA_PLATFORM=offscreen \
    QT_QUICK_BACKEND=software \
    QT_QPA_PLATFORMTHEME=generic \
    QT_ACCESSIBILITY=0 \
    QT_FORCE_STDERR_LOGGING=1 \
    XDG_CACHE_HOME="$staging_dir/cache" \
    XDG_CONFIG_HOME="$staging_dir/config" \
    PROTON_VPN_KDE_TEST_BACKEND_OWNER="$backend_owner" \
    PROTON_KDE_SNAPSHOT_DELAY_MS=1400 \
    timeout 10s "$build_dir/proton-vpn-kde" \
        --settings-route-smoke \
        --visual-page settings \
        --visual-snapshot "$staging_dir/settings.png" \
        >"$frontend_log" 2>&1 &
frontend_pid=$!

sleep 0.5
if ! wait "$frontend_pid"; then
    frontend_pid=""
    echo "Settings navigation check did not exit cleanly" >&2
    cat "$frontend_log" >&2
    exit 1
fi
frontend_pid=""

if ! grep -Fqx -- \
        "visual-snapshot: current section settings" "$frontend_log"; then
    echo "A settings update unexpectedly changed the current page" >&2
    cat "$frontend_log" >&2
    exit 1
fi

if ! grep -Fqx -- \
        "qml: settings-route-smoke: current section settings" "$frontend_log"; then
    echo "The frontend settings update did not preserve its current page" >&2
    cat "$frontend_log" >&2
    exit 1
fi

if ! grep -Fqx -- \
        "qml: settings-route-smoke: owned pages 1" "$frontend_log"; then
    echo "Removed navigation pages were not destroyed" >&2
    cat "$frontend_log" >&2
    exit 1
fi
