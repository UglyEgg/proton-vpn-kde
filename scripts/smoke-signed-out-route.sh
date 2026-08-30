#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"
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

if [[ -n "${PROTON_KDE_BACKEND_EXECUTABLE:-}" ]]; then
    "$PROTON_KDE_BACKEND_EXECUTABLE" --demo-logged-out \
        >"$staging_dir/backend.log" 2>&1 &
else
    PYTHONPATH="$project_dir/backend" \
        /usr/bin/python3 -m proton_vpn_kde_backend --demo-logged-out \
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
if ! env \
        QT_QPA_PLATFORM=offscreen \
        QT_QUICK_BACKEND=software \
        QT_QPA_PLATFORMTHEME=generic \
        QT_ACCESSIBILITY=0 \
        QT_FORCE_STDERR_LOGGING=1 \
        XDG_CACHE_HOME="$staging_dir/cache" \
        XDG_CONFIG_HOME="$staging_dir/config" \
        PROTON_VPN_KDE_TEST_BACKEND_OWNER="$backend_owner" \
        PROTON_KDE_SNAPSHOT_DELAY_MS=800 \
        timeout 10s "$build_dir/proton-vpn-kde" \
            --visual-page overview \
            --visual-snapshot "$staging_dir/signed-out.png" \
            >"$frontend_log" 2>&1; then
    echo "Signed-out startup route did not exit cleanly" >&2
    cat "$frontend_log" >&2
    exit 1
fi

if ! grep -Fqx -- \
        "visual-snapshot: current section account" "$frontend_log"; then
    echo "Signed-out startup did not route to the account sign-in page" >&2
    cat "$frontend_log" >&2
    exit 1
fi
