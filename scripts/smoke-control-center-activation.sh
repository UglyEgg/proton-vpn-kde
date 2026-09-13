#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

build_dir="${1:?Pass the CMake build directory}"
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
staging_dir="$(mktemp -d)"
agent_pid=""
duplicate_pid=""
control_center_pid=""

cleanup() {
    if [[ -n "$control_center_pid" ]]; then
        kill "$control_center_pid" 2>/dev/null || true
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
        quest.entropy.PlasmaVPN.Agent 2>/dev/null)" == "(true,)" ]]; then
        break
    fi
    sleep 0.05
done
if ! kill -0 "$agent_pid" 2>/dev/null; then
    echo "Plasma agent did not start" >&2
    cat "$staging_dir/agent.log" >&2
    exit 1
fi

if gdbus call --session \
    --dest quest.entropy.PlasmaVPN.Agent \
    --object-path /quest/entropy/PlasmaVPN/Agent \
    --method quest.entropy.PlasmaVPN.Agent1.Quit \
    >/dev/null 2>&1; then
    echo "Agent exposed an unauthenticated Quit method" >&2
    exit 1
fi
if ! kill -0 "$agent_pid" 2>/dev/null; then
    echo "An unauthenticated Quit request stopped the Plasma agent" >&2
    exit 1
fi

gdbus call --session \
    --dest quest.entropy.PlasmaVPN.Agent \
    --object-path /quest/entropy/PlasmaVPN/Agent \
    --method quest.entropy.PlasmaVPN.Agent1.ShowControlCenter >/dev/null

for _ in {1..120}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        quest.entropy.PlasmaVPN.ControlCenter 2>/dev/null)" == "(true,)" ]]; then
        break
    fi
    sleep 0.05
done

control_center_count="$(pgrep -fc "^$build_dir/proton-vpn-kde( |$)" || true)"
if [[ "$control_center_count" != "1" ]]; then
    echo "Agent activation did not produce exactly one Control Center" >&2
    exit 1
fi
control_center_pid="$(pgrep -f "^$build_dir/proton-vpn-kde( |$)")"

# The private bus and direct agent inherit CTest's harmless QT_PLUGIN_PATH
# canary. Verify both real entry points satisfy the unchanged backend policy,
# not just a helper probe or libc's post-unset view of the environment.
PYTHONPATH="$project_dir/backend" python3 - "$agent_pid" "$control_center_pid" <<'PY'
from pathlib import Path
import sys

from proton_vpn_kde_backend.client_authorization import process_environment_is_safe

for process_id in sys.argv[1:]:
    entries = Path(f"/proc/{int(process_id)}/environ").read_bytes().split(b"\0")
    if not process_environment_is_safe(entries):
        raise SystemExit("A native entry point retained blocked startup configuration")
print("Both native entry points satisfy the backend environment policy")
PY

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
    --dest quest.entropy.PlasmaVPN.Agent \
    --object-path /quest/entropy/PlasmaVPN/Agent \
    --method quest.entropy.PlasmaVPN.Agent1.ShowControlCenter >/dev/null
sleep 0.2
control_center_count="$(pgrep -fc "^$build_dir/proton-vpn-kde( |$)" || true)"
if [[ "$control_center_count" != "1" ]]; then
    echo "Repeated agent activation created another Control Center" >&2
    exit 1
fi

if gdbus call --session \
    --dest quest.entropy.PlasmaVPN.ControlCenter \
    --object-path /quest/entropy/PlasmaVPN/ControlCenter \
    --method quest.entropy.PlasmaVPN.ControlCenter1.Quit \
    >/dev/null 2>&1; then
    echo "Control Center exposed an unauthenticated Quit method" >&2
    exit 1
fi
if ! kill -0 "$control_center_pid" 2>/dev/null; then
    echo "An unauthenticated Quit request stopped the Control Center" >&2
    exit 1
fi

kill "$control_center_pid"

for _ in {1..80}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        quest.entropy.PlasmaVPN.ControlCenter 2>/dev/null)" == "(false,)" ]]; then
        break
    fi
    sleep 0.05
done
if [[ "$(gdbus call --session \
    --dest org.freedesktop.DBus \
    --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.NameHasOwner \
    quest.entropy.PlasmaVPN.ControlCenter 2>/dev/null)" != "(false,)" ]]; then
    echo "Control Center did not exit on request" >&2
    exit 1
fi
control_center_pid=""

if ! kill -0 "$agent_pid" 2>/dev/null; then
    echo "Closing the Control Center stopped the Plasma agent" >&2
    exit 1
fi

disabled_config="$staging_dir/disabled-config"
mkdir -p "$disabled_config"
env XDG_CONFIG_HOME="$disabled_config" \
    /usr/bin/kwriteconfig6 \
    --file proton-vpn-kderc \
    --group General \
    --key CloseToTray false
env XDG_CONFIG_HOME="$disabled_config" \
    /usr/bin/dbus-update-activation-environment XDG_CONFIG_HOME
gdbus call --session \
    --dest quest.entropy.PlasmaVPN.ControlCenter \
    --object-path /quest/entropy/PlasmaVPN/ControlCenter \
    --method quest.entropy.PlasmaVPN.ControlCenter1.ShowControlCenter \
    >/dev/null
control_center_pid="$(pgrep -f "^$build_dir/proton-vpn-kde( |$)")"
for _ in {1..80}; do
    if ! kill -0 "$agent_pid" 2>/dev/null; then
        break
    fi
    sleep 0.05
done
if kill -0 "$agent_pid" 2>/dev/null; then
    echo "The packaged Control Center could not stop background controls" >&2
    exit 1
fi
wait "$agent_pid"
agent_pid=""
