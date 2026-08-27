#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${PROTON_KDE_BUILD_DIR:-$project_dir/build}"
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
}
trap cleanup EXIT

PYTHONPATH="$project_dir/backend" \
    python3 -m proton_vpn_kde_backend --demo &
backend_pid=$!

for _ in {1..40}; do
    if gdbus introspect --session \
        --dest proton.vpn.app.kde.backend \
        --object-path /proton/vpn/app/kde/backend >/dev/null 2>&1; then
        break
    fi
    sleep 0.05
done

gdbus introspect --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend >/dev/null

xvfb-run -a "$build_dir/proton-vpn-kde" &
frontend_pid=$!

app_pid=""
for _ in {1..100}; do
    app_pid="$(pgrep -n -x proton-vpn-kde || true)"
    if [[ -n "$app_pid" ]]; then
        break
    fi
    sleep 0.05
done

if [[ -z "$app_pid" ]]; then
    echo "Frontend did not start" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetSnapshot

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetCountries

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetServers CH

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetServerLoads CH

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.SetReconnectionEnabled false

snapshot="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetSnapshot)"
if [[ "$snapshot" != *'"reconnectEnabled":false'* ]]; then
    echo "Backend did not retain the reconnection preference" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.SetReconnectionEnabled true

ps -o pid=,rss=,comm= -p "$backend_pid" "$app_pid"
