#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"
staging_dir="$(mktemp -d)"
backend_pid=""
agent_pid=""
duplicate_pid=""

cleanup() {
    if [[ -n "$duplicate_pid" ]]; then
        kill "$duplicate_pid" 2>/dev/null || true
        wait "$duplicate_pid" 2>/dev/null || true
    fi
    if [[ -n "$agent_pid" ]]; then
        kill "$agent_pid" 2>/dev/null || true
        wait "$agent_pid" 2>/dev/null || true
    fi
    if [[ -n "$backend_pid" ]]; then
        kill "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
    fi
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

PYTHONPATH="$project_dir/backend" \
    PROTON_VPN_KDE_IDLE_TIMEOUT_SECONDS=2 \
    PROTON_VPN_KDE_CLIENT_POLL_SECONDS=0.05 \
    python3 -m proton_vpn_kde_backend --demo \
    >"$staging_dir/backend.log" 2>&1 &
backend_pid=$!

for _ in {1..40}; do
    owner_reply="$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.GetNameOwner \
        quest.entropy.PlasmaVPN.Backend 2>/dev/null || true)"
    backend_owner="${owner_reply#*\'}"
    backend_owner="${backend_owner%%\'*}"
    if [[ "$backend_owner" == :* ]]; then
        break
    fi
    sleep 0.05
done

env \
    QT_QPA_PLATFORM=offscreen \
    QT_QPA_PLATFORMTHEME=generic \
    QT_ACCESSIBILITY=0 \
    XDG_CONFIG_HOME="$staging_dir/config" \
    PROTON_VPN_KDE_TEST_BACKEND_OWNER="$backend_owner" \
    "$build_dir/proton-vpn-kde-agent" \
    >"$staging_dir/agent.log" 2>&1 &
agent_pid=$!

for _ in {1..80}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        quest.entropy.PlasmaVPN.Agent 2>/dev/null)" == "(true,)" ]]; then
        break
    fi
    sleep 0.05
done

if ! kill -0 "$agent_pid" 2>/dev/null; then
    echo "Plasma agent did not remain running" >&2
    cat "$staging_dir/agent.log" >&2
    exit 1
fi

env \
    QT_QPA_PLATFORM=offscreen \
    QT_QPA_PLATFORMTHEME=generic \
    QT_ACCESSIBILITY=0 \
    XDG_CONFIG_HOME="$staging_dir/config" \
    PROTON_VPN_KDE_TEST_BACKEND_OWNER="$backend_owner" \
    "$build_dir/proton-vpn-kde-agent" \
    >"$staging_dir/duplicate.log" 2>&1 &
duplicate_pid=$!
for _ in {1..40}; do
    if ! kill -0 "$duplicate_pid" 2>/dev/null; then
        break
    fi
    sleep 0.05
done
if kill -0 "$duplicate_pid" 2>/dev/null; then
    echo "A duplicate Plasma agent remained running" >&2
    exit 1
fi
wait "$duplicate_pid"
duplicate_pid=""

for _ in {1..100}; do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
        break
    fi
    sleep 0.05
done
if kill -0 "$backend_pid" 2>/dev/null; then
    echo "The lease-free Plasma agent kept an idle backend alive" >&2
    cat "$staging_dir/backend.log" >&2
    exit 1
fi
wait "$backend_pid"
backend_pid=""

if ! kill -0 "$agent_pid" 2>/dev/null; then
    echo "The Plasma agent exited with the idle backend" >&2
    cat "$staging_dir/agent.log" >&2
    exit 1
fi
