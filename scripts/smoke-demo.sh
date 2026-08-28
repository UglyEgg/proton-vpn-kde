#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${PROTON_KDE_BUILD_DIR:-$project_dir/build}"
backend_pid=""
frontend_pid=""
app_pid=""

cleanup() {
    if [[ -n "$app_pid" ]]; then
        kill "$app_pid" 2>/dev/null || true
        wait "$app_pid" 2>/dev/null || true
    fi
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

if [[ -n "${PROTON_KDE_BACKEND_EXECUTABLE:-}" ]]; then
    "$PROTON_KDE_BACKEND_EXECUTABLE" --demo &
else
    PYTHONPATH="$project_dir/backend" \
        python3 -m proton_vpn_kde_backend --demo &
fi
backend_pid=$!

for _ in {1..40}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        proton.vpn.app.kde.backend 2>/dev/null)" == "(true,)" ]]; then
        break
    fi
    sleep 0.05
done

gdbus introspect --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend >/dev/null

xvfb-run -a "$build_dir/proton-vpn-kde" &
frontend_pid=$!

for _ in {1..100}; do
    app_pid="$(pgrep -P "$frontend_pid" -x proton-vpn-kde || true)"
    if [[ -n "$app_pid" ]]; then
        break
    fi
    sleep 0.05
done

if [[ -z "$app_pid" ]]; then
    echo "Frontend did not start" >&2
    exit 1
fi

sleep 0.25
if ! kill -0 "$app_pid" 2>/dev/null; then
    echo "Frontend exited while loading QML" >&2
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

location_search="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.SearchLocations zur)"
if [[ "$location_search" != *'"kind":"location"'* \
    || "$location_search" != *'"name":"Zurich"'* ]]; then
    echo "Backend did not return global location search results" >&2
    exit 1
fi

server_search="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.SearchLocations CH#)"
if [[ "$server_search" != *'"kind":"server"'* \
    || "$server_search" != *'"name":"CH#101"'* ]]; then
    echo "Backend did not return global server search results" >&2
    exit 1
fi

nps_survey="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetPendingNpsSurvey)"
if [[ "$nps_survey" != *'"available":false'* ]]; then
    echo "Backend did not return the demo survey state" >&2
    exit 1
fi

server_groups="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetServerGroups CH)"
if [[ "$server_groups" != *'"kind":"secure-core"'* \
    || "$server_groups" != *'"name":"Zurich"'* ]]; then
    echo "Backend did not return feature-aware server groups" >&2
    exit 1
fi

secure_core_servers="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetGroupServers \
    CH secure-core 'Via Secure Core')"
if [[ "$secure_core_servers" != *'"secureCore":true'* \
    || "$secure_core_servers" != *'"entryCountry":"DE"'* ]]; then
    echo "Backend did not return Secure Core servers" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetServerLoads CH

settings="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetSettings)"
if [[ "$settings" != *'"protocol":"wireguard"'* ]]; then
    echo "Backend did not return the demo VPN settings" >&2
    exit 1
fi

updated_settings="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.UpdateSettings \
    '{"netShield":2,"vpnAccelerator":false}')"
if [[ "$updated_settings" != *'"netShield":2'* \
    || "$updated_settings" != *'"vpnAccelerator":false'* ]]; then
    echo "Backend did not apply the demo VPN settings" >&2
    exit 1
fi

split_tunneling="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetSplitTunneling)"
if [[ "$split_tunneling" != *'"available":true'* \
    || "$split_tunneling" != *'"mode":"exclude"'* ]]; then
    echo "Backend did not return the demo split-tunneling settings" >&2
    exit 1
fi

updated_split_tunneling="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.UpdateSplitTunneling \
    '{"excludeAppPaths":["/usr/bin/demo-browser"],"excludeIpRanges":["192.168.1.50/24"],"enabled":true}')"
if [[ "$updated_split_tunneling" != *'"enabled":true'* \
    || "$updated_split_tunneling" != *'"excludeAppPaths":["/usr/bin/demo-browser"]'* \
    || "$updated_split_tunneling" != *'"excludeIpRanges":["192.168.1.0/24"]'* ]]; then
    echo "Backend did not apply the demo split-tunneling settings" >&2
    exit 1
fi

custom_dns="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetCustomDns)"
if [[ "$custom_dns" != *'"paidFeaturesAvailable":true'* \
    || "$custom_dns" != *'"enabled":false'* ]]; then
    echo "Backend did not return the demo custom-DNS settings" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.UpdateSettings \
    '{"netShield":0}' >/dev/null

updated_custom_dns="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.UpdateCustomDns \
    '{"servers":[{"address":"1.1.1.1","enabled":true}],"enabled":true}')"
if [[ "$updated_custom_dns" != *'"enabled":true'* \
    || "$updated_custom_dns" != *'"address":"1.1.1.1"'* ]]; then
    echo "Backend did not apply the demo custom-DNS settings" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.UpdateSettings \
    '{"protocol":"protun-udp","portForwarding":true}' >/dev/null
gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.ConnectGroup \
    CH secure-core 'Via Secure Core'
connected_snapshot="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetSnapshot)"
if [[ "$connected_snapshot" != *'"serverName":"CH-DE#1"'* \
    || "$connected_snapshot" != *'"forwardedPort":51820'* \
    || "$connected_snapshot" != *'"secureCore":true'* ]]; then
    echo "Backend did not publish live Secure Core connection details" >&2
    exit 1
fi
gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.StartPacketCapture /tmp
capture_snapshot="$(gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.GetSnapshot)"
if [[ "$capture_snapshot" != *'"packetCaptureActive":true'* ]]; then
    echo "Backend did not publish packet-capture state" >&2
    exit 1
fi
gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.StopPacketCapture
gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.Disconnect

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

if ! kill -0 "$app_pid" 2>/dev/null; then
    echo "Frontend exited during the smoke test" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.backend \
    --object-path /proton/vpn/app/kde/backend \
    --method proton.vpn.app.kde.Backend1.SetReconnectionEnabled true

ps -o pid=,rss=,comm= -p "$backend_pid" "$app_pid"
