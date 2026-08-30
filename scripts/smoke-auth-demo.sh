#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
backend_pid=""

cleanup() {
    if [[ -n "$backend_pid" ]]; then
        kill "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
    fi
}
trap cleanup EXIT

if [[ -n "${PROTON_KDE_BACKEND_EXECUTABLE:-}" ]]; then
    "$PROTON_KDE_BACKEND_EXECUTABLE" --demo-logged-out &
else
    PYTHONPATH="$project_dir/backend" \
        /usr/bin/python3 -m proton_vpn_kde_backend --demo-logged-out &
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

descriptor_count_before="$(find "/proc/$backend_pid/fd" -mindepth 1 -maxdepth 1 -printf '.' | wc -c)"
/usr/bin/python3 "$project_dir/scripts/auth-dbus-client.py"
sleep 0.05
descriptor_count_after="$(find "/proc/$backend_pid/fd" -mindepth 1 -maxdepth 1 -printf '.' | wc -c)"
if [[ "$descriptor_count_after" -ne "$descriptor_count_before" ]]; then
    echo "Authentication smoke leaked backend file descriptors: $descriptor_count_before -> $descriptor_count_after" >&2
    exit 1
fi
