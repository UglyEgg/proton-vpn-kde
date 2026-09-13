#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" != "--in-session" ]]; then
    build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"
    runtime_dir="$(mktemp -d)"
    chmod 700 "$runtime_dir"
    if XDG_RUNTIME_DIR="$runtime_dir" \
            dbus-run-session -- "$0" --in-session "$build_dir"; then
        status=0
    else
        status=$?
    fi
    rm -rf -- "$runtime_dir"
    exit "$status"
fi

shift
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

PYTHONPATH="$project_dir/backend" \
    /usr/bin/python3 -m proton_vpn_kde_backend --demo \
    >"$staging_dir/backend.log" 2>&1 &
backend_pid=$!

owner_reply=""
for _ in {1..100}; do
    owner_reply="$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.GetNameOwner \
        quest.entropy.PlasmaVPN.Backend 2>/dev/null || true)"
    if [[ "$owner_reply" == *"':"* ]]; then
        break
    fi
    sleep 0.05
done
if [[ "$owner_reply" != *"':"* ]]; then
    echo "Demo backend did not become available" >&2
    exit 1
fi
backend_owner="${owner_reply#*\'}"
backend_owner="${backend_owner%%\'*}"

frontend_log="$staging_dir/frontend.log"
if ! env \
        LANG=C.UTF-8 \
        LC_ALL=C.UTF-8 \
        GTK_USE_PORTAL=0 \
        QT_QPA_PLATFORM=offscreen \
        QT_QUICK_BACKEND=software \
        QT_QPA_PLATFORMTHEME=generic \
        QT_ACCESSIBILITY=0 \
        QT_NO_XDG_DESKTOP_PORTAL=1 \
        QT_FORCE_STDERR_LOGGING=1 \
        XDG_CACHE_HOME="$staging_dir/cache" \
        XDG_CONFIG_HOME="$staging_dir/config" \
        PROTON_VPN_KDE_TEST_BACKEND_OWNER="$backend_owner" \
        timeout 20s "$build_dir/proton-vpn-kde" \
            --inspector-retention-smoke >"$frontend_log" 2>&1; then
    echo "Inspector retention measurement did not exit cleanly" >&2
    sed -n '1,240p' "$frontend_log" >&2
    exit 1
fi

measurement="$(sed -n 's/^inspector-retention: //p' "$frontend_log")"
if [[ -z "$measurement" ]]; then
    echo "Inspector retention measurement was not reported" >&2
    sed -n '1,240p' "$frontend_log" >&2
    exit 1
fi
printf '%s\n' "$measurement"
