#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_pid=""
duplicate_pid=""

cleanup() {
    if [[ -n "$duplicate_pid" ]]; then
        kill "$duplicate_pid" 2>/dev/null || true
        wait "$duplicate_pid" 2>/dev/null || true
    fi
    if [[ -n "$backend_pid" ]]; then
        kill "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT

start_backend() {
    PYTHONPATH="$project_dir/backend" \
        PROTON_VPN_KDE_IDLE_TIMEOUT_SECONDS=2 \
        PROTON_VPN_KDE_CLIENT_POLL_SECONDS=0.05 \
        python3 -m proton_vpn_kde_backend --demo
}

start_backend &
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

if ! kill -0 "$backend_pid" 2>/dev/null; then
    echo "Primary backend did not acquire the D-Bus name" >&2
    exit 1
fi

start_backend &
duplicate_pid=$!
for _ in {1..40}; do
    if ! kill -0 "$duplicate_pid" 2>/dev/null; then
        break
    fi
    sleep 0.05
done

if kill -0 "$duplicate_pid" 2>/dev/null; then
    echo "Duplicate backend remained queued behind the primary owner" >&2
    exit 1
fi
wait "$duplicate_pid"
duplicate_pid=""

if ! kill -0 "$backend_pid" 2>/dev/null; then
    echo "Duplicate launch disturbed the primary backend" >&2
    exit 1
fi

for _ in {1..60}; do
    if ! kill -0 "$backend_pid" 2>/dev/null; then
        break
    fi
    sleep 0.05
done

if kill -0 "$backend_pid" 2>/dev/null; then
    echo "Disconnected backend did not exit after its idle grace period" >&2
    exit 1
fi
wait "$backend_pid"
backend_pid=""
