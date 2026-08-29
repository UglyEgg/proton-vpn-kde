#!/usr/bin/bash
set -euo pipefail

build_dir="${1:?Pass the CMake build directory}"
staging_dir="$(mktemp -d)"
agent_pid=""
duplicate_pid=""

cleanup() {
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        proton.vpn.app.kde.ControlCenter 2>/dev/null || true)" == "(true,)" ]]; then
        gdbus call --session \
            --dest proton.vpn.app.kde.ControlCenter \
            --object-path /proton/vpn/app/kde/controlcenter \
            --method proton.vpn.app.kde.ControlCenter1.Quit \
            >/dev/null 2>&1 || true
    fi
    if [[ -n "$agent_pid" ]]; then
        kill "$agent_pid" 2>/dev/null || true
        wait "$agent_pid" 2>/dev/null || true
    fi
    if [[ -n "$duplicate_pid" ]]; then
        kill "$duplicate_pid" 2>/dev/null || true
        wait "$duplicate_pid" 2>/dev/null || true
    fi
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

env XDG_CONFIG_HOME="$staging_dir/config" \
    "$build_dir/proton-vpn-kde-agent" \
    >"$staging_dir/agent.log" 2>&1 &
agent_pid=$!

for _ in {1..80}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        proton.vpn.app.kde.Agent 2>/dev/null)" == "(true,)" ]]; then
        break
    fi
    sleep 0.05
done
if ! kill -0 "$agent_pid" 2>/dev/null; then
    echo "Plasma agent did not start" >&2
    cat "$staging_dir/agent.log" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.Agent \
    --object-path /proton/vpn/app/kde/agent \
    --method proton.vpn.app.kde.Agent1.ShowControlCenter >/dev/null

for _ in {1..120}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        proton.vpn.app.kde.ControlCenter 2>/dev/null)" == "(true,)" ]]; then
        break
    fi
    sleep 0.05
done

control_center_count="$(pgrep -fc "^$build_dir/proton-vpn-kde( |$)" || true)"
if [[ "$control_center_count" != "1" ]]; then
    echo "Agent activation did not produce exactly one Control Center" >&2
    exit 1
fi

env XDG_CONFIG_HOME="$staging_dir/config" \
    "$build_dir/proton-vpn-kde" --show \
    >"$staging_dir/duplicate.log" 2>&1 &
duplicate_pid=$!
for _ in {1..40}; do
    if ! kill -0 "$duplicate_pid" 2>/dev/null; then
        break
    fi
    sleep 0.05
done
if kill -0 "$duplicate_pid" 2>/dev/null; then
    echo "A duplicate Control Center remained running" >&2
    exit 1
fi
wait "$duplicate_pid"
duplicate_pid=""

control_center_count="$(pgrep -fc "^$build_dir/proton-vpn-kde( |$)" || true)"
if [[ "$control_center_count" != "1" ]]; then
    echo "A duplicate launch disturbed the active Control Center" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.Agent \
    --object-path /proton/vpn/app/kde/agent \
    --method proton.vpn.app.kde.Agent1.ShowControlCenter >/dev/null
sleep 0.2
control_center_count="$(pgrep -fc "^$build_dir/proton-vpn-kde( |$)" || true)"
if [[ "$control_center_count" != "1" ]]; then
    echo "Repeated agent activation created another Control Center" >&2
    exit 1
fi

gdbus call --session \
    --dest proton.vpn.app.kde.ControlCenter \
    --object-path /proton/vpn/app/kde/controlcenter \
    --method proton.vpn.app.kde.ControlCenter1.Quit >/dev/null

for _ in {1..80}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        proton.vpn.app.kde.ControlCenter 2>/dev/null)" == "(false,)" ]]; then
        break
    fi
    sleep 0.05
done
if [[ "$(gdbus call --session \
    --dest org.freedesktop.DBus \
    --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.NameHasOwner \
    proton.vpn.app.kde.ControlCenter 2>/dev/null)" != "(false,)" ]]; then
    echo "Control Center did not exit on request" >&2
    exit 1
fi

if ! kill -0 "$agent_pid" 2>/dev/null; then
    echo "Closing the Control Center stopped the Plasma agent" >&2
    exit 1
fi
