#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:?Pass the CMake build directory}"
install_bindir="${2:?Pass CMAKE_INSTALL_FULL_BINDIR}"
install_libexecdir="${3:?Pass CMAKE_INSTALL_FULL_LIBEXECDIR}"
install_datadir="${4:?Pass CMAKE_INSTALL_FULL_DATADIR}"
install_systemd_user_unit_dir="${5:?Pass KDE_INSTALL_FULL_SYSTEMDUSERUNITDIR}"
staging_dir="$(mktemp -d)"

cleanup() {
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

DESTDIR="$staging_dir" cmake --install "$build_dir" >/dev/null

launcher="$staging_dir$install_bindir/proton-vpn-kde-backend"
agent="$staging_dir$install_bindir/proton-vpn-kde-agent"
dbus_service="$staging_dir$install_datadir/dbus-1/services/quest.entropy.PlasmaVPN.Backend.service"
agent_dbus_service="$staging_dir$install_datadir/dbus-1/services/quest.entropy.PlasmaVPN.Agent.service"
control_center_dbus_service="$staging_dir$install_datadir/dbus-1/services/quest.entropy.PlasmaVPN.ControlCenter.service"
systemd_service="$staging_dir$install_systemd_user_unit_dir/proton-vpn-kde-backend.service"
agent_systemd_service="$staging_dir$install_systemd_user_unit_dir/proton-vpn-kde-agent.service"
control_center_systemd_service="$staging_dir$install_systemd_user_unit_dir/proton-vpn-kde-control-center.service"
icon="$staging_dir$install_datadir/icons/hicolor/scalable/apps/plasma-vpn.svg"
light_icon="$staging_dir$install_datadir/icons/hicolor/scalable/apps/plasma-vpn-light.svg"
dark_icon="$staging_dir$install_datadir/icons/hicolor/scalable/apps/plasma-vpn-dark.svg"
build_features="$staging_dir$install_libexecdir/proton-vpn-kde/proton_vpn_kde_backend/_build_features.py"
environment_contract="$staging_dir$install_libexecdir/proton-vpn-kde/proton_vpn_kde_backend/unsafe_environment.txt"
desktop_file="$staging_dir$install_datadir/applications/proton-vpn-kde.desktop"

test -x "$launcher"
test -x "$agent"
test -d "$staging_dir$install_libexecdir/proton-vpn-kde/proton_vpn_kde_backend"
test -r "$icon"
test -r "$light_icon"
test -r "$dark_icon"
test -r "$build_features"
test -r "$environment_contract"
test -r "$desktop_file"
grep -Fqx 'SUPPORT_REPORT_SUBMISSION_ENABLED = False' "$build_features"
grep -Fqx "Exec=$install_bindir/proton-vpn-kde-backend" "$dbus_service"
grep -Fqx "Name=quest.entropy.PlasmaVPN.Backend" "$dbus_service"
grep -Fqx "ExecStart=$install_bindir/proton-vpn-kde-backend" "$systemd_service"
grep -Fqx "BusName=quest.entropy.PlasmaVPN.Backend" "$systemd_service"
grep -Fqx "TimeoutStopSec=35s" "$systemd_service"
grep -Fqx "Exec=$install_bindir/proton-vpn-kde-agent" "$agent_dbus_service"
grep -Fqx "Name=quest.entropy.PlasmaVPN.Agent" "$agent_dbus_service"
grep -Fqx "Exec=$install_bindir/proton-vpn-kde --show" "$control_center_dbus_service"
grep -Fqx "Name=quest.entropy.PlasmaVPN.ControlCenter" "$control_center_dbus_service"
grep -Fqx "SystemdService=proton-vpn-kde-control-center.service" \
    "$control_center_dbus_service"
grep -Fqx "ExecStart=$install_bindir/proton-vpn-kde --show" \
    "$control_center_systemd_service"
grep -Fqx "BusName=quest.entropy.PlasmaVPN.ControlCenter" \
    "$control_center_systemd_service"
grep -Fqx "ExecStart=$install_bindir/proton-vpn-kde-agent" "$agent_systemd_service"
grep -Fqx "BusName=quest.entropy.PlasmaVPN.Agent" "$agent_systemd_service"
grep -Fqx "Exec=$install_bindir/proton-vpn-kde --show" "$desktop_file"
grep -qx 'NoNewPrivileges=true' "$systemd_service"
grep -qx 'NoNewPrivileges=true' "$agent_systemd_service"
grep -qx 'NoNewPrivileges=true' "$control_center_systemd_service"
expected_unset_environment="UnsetEnvironment=$(grep -Ev '^[[:space:]]*(#|$)' \
    "$environment_contract" | paste -sd ' ' -)"
grep -Fqx "$expected_unset_environment" "$systemd_service"
grep -Fqx "$expected_unset_environment" "$agent_systemd_service"
grep -Fqx "$expected_unset_environment" "$control_center_systemd_service"
python3 "$project_dir/scripts/check-backend-launcher-environment.py" \
    "$launcher" "$environment_contract"
if grep -Eq '^(PrivateTmp|ProtectSystem)=' \
        "$systemd_service" "$agent_systemd_service" \
        "$control_center_systemd_service"; then
    echo "Mount namespace hardening breaks procfs peer authentication" >&2
    exit 1
fi

smoke_log="$staging_dir/smoke.log"
if ! env \
        PROTON_KDE_BUILD_DIR="$staging_dir$install_bindir" \
        PROTON_KDE_BACKEND_EXECUTABLE="$launcher" \
        dbus-run-session -- "$project_dir/scripts/smoke-demo.sh" \
        >"$smoke_log" 2>&1; then
    cat "$smoke_log" >&2
    exit 1
fi
