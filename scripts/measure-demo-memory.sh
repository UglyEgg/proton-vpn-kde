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
agent_pid=""
control_center_pid=""

cleanup() {
    local pid
    for pid in "$control_center_pid" "$agent_pid" "$backend_pid"; do
        if [[ -n "$pid" ]]; then
            kill "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
        fi
    done
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

for executable in proton-vpn-kde proton-vpn-kde-agent; do
    if [[ ! -x "$build_dir/$executable" ]]; then
        echo "Missing executable: $build_dir/$executable" >&2
        exit 1
    fi
done

wait_for_service() {
    local service_name="$1"
    local owner_reply
    for _ in {1..100}; do
        owner_reply="$(gdbus call --session \
            --dest org.freedesktop.DBus \
            --object-path /org/freedesktop/DBus \
            --method org.freedesktop.DBus.GetNameOwner \
            "$service_name" 2>/dev/null || true)"
        if [[ "$owner_reply" == *"':"* ]]; then
            return 0
        fi
        sleep 0.05
    done
    echo "Service did not become available: $service_name" >&2
    return 1
}

service_owner() {
    local service_name="$1"
    local owner_reply
    owner_reply="$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.GetNameOwner \
        "$service_name")"
    owner_reply="${owner_reply#*\'}"
    printf '%s\n' "${owner_reply%%\'*}"
}

read_metric() {
    local pid="$1"
    local metric="$2"
    awk -v metric="$metric" '$1 == metric ":" { print $2; found = 1 }
        END { if (!found) exit 1 }' "/proc/$pid/smaps_rollup"
}

PYTHONPATH="$project_dir/backend" \
    /usr/bin/python3 -m proton_vpn_kde_backend --demo \
    >"$staging_dir/backend.log" 2>&1 &
backend_pid=$!
wait_for_service quest.entropy.PlasmaVPN.Backend
backend_owner="$(service_owner quest.entropy.PlasmaVPN.Backend)"

common_environment=(
    GTK_USE_PORTAL=0
    QT_ACCESSIBILITY=0
    QT_NO_XDG_DESKTOP_PORTAL=1
    QT_QPA_PLATFORM=offscreen
    QT_QPA_PLATFORMTHEME=generic
    QT_QUICK_BACKEND=software
    XDG_CACHE_HOME="$staging_dir/cache"
    XDG_CONFIG_HOME="$staging_dir/config"
    PROTON_VPN_KDE_TEST_BACKEND_OWNER="$backend_owner"
)

env "${common_environment[@]}" "$build_dir/proton-vpn-kde-agent" \
    >"$staging_dir/agent.log" 2>&1 &
agent_pid=$!
wait_for_service quest.entropy.PlasmaVPN.Agent

env "${common_environment[@]}" "$build_dir/proton-vpn-kde" --show \
    >"$staging_dir/control-center.log" 2>&1 &
control_center_pid=$!
wait_for_service quest.entropy.PlasmaVPN.ControlCenter

sleep 5
for pid in "$backend_pid" "$agent_pid" "$control_center_pid"; do
    if ! kill -0 "$pid" 2>/dev/null; then
        echo "A measured process exited before sampling" >&2
        exit 1
    fi
done

backend_pss="$(read_metric "$backend_pid" Pss)"
backend_rss="$(read_metric "$backend_pid" Rss)"
agent_pss="$(read_metric "$agent_pid" Pss)"
agent_rss="$(read_metric "$agent_pid" Rss)"
control_center_pss="$(read_metric "$control_center_pid" Pss)"
control_center_rss="$(read_metric "$control_center_pid" Rss)"
combined_pss=$((backend_pss + agent_pss + control_center_pss))

printf '{\n'
printf '  "backend": {"pssKiB": %d, "rssKiB": %d},\n' \
    "$backend_pss" "$backend_rss"
printf '  "agent": {"pssKiB": %d, "rssKiB": %d},\n' \
    "$agent_pss" "$agent_rss"
printf '  "controlCenter": {"pssKiB": %d, "rssKiB": %d},\n' \
    "$control_center_pss" "$control_center_rss"
printf '  "combinedPssKiB": %d\n' "$combined_pss"
printf '}\n'
