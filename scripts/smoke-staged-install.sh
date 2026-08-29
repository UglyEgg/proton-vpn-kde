#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:?Pass the CMake build directory}"
install_bindir="${2:?Pass CMAKE_INSTALL_FULL_BINDIR}"
install_libexecdir="${3:?Pass CMAKE_INSTALL_FULL_LIBEXECDIR}"
install_datadir="${4:?Pass CMAKE_INSTALL_FULL_DATADIR}"
install_libdir="${5:?Pass CMAKE_INSTALL_FULL_LIBDIR}"
staging_dir="$(mktemp -d)"

cleanup() {
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

DESTDIR="$staging_dir" cmake --install "$build_dir" >/dev/null

launcher="$staging_dir$install_bindir/proton-vpn-kde-backend"
agent="$staging_dir$install_bindir/proton-vpn-kde-agent"
dbus_service="$staging_dir$install_datadir/dbus-1/services/proton.vpn.app.kde.backend.service"
agent_dbus_service="$staging_dir$install_datadir/dbus-1/services/proton.vpn.app.kde.Agent.service"
control_center_dbus_service="$staging_dir$install_datadir/dbus-1/services/proton.vpn.app.kde.ControlCenter.service"
systemd_service="$staging_dir$install_libdir/systemd/user/proton-vpn-kde-backend.service"
agent_systemd_service="$staging_dir$install_libdir/systemd/user/proton-vpn-kde-agent.service"

test -x "$launcher"
test -x "$agent"
test -d "$staging_dir$install_libexecdir/proton-vpn-kde/proton_vpn_kde_backend"
grep -Fqx "Exec=$install_bindir/proton-vpn-kde-backend" "$dbus_service"
grep -Fqx "ExecStart=$install_bindir/proton-vpn-kde-backend" "$systemd_service"
grep -Fqx "Exec=$install_bindir/proton-vpn-kde-agent" "$agent_dbus_service"
grep -Fqx "Exec=$install_bindir/proton-vpn-kde --show" "$control_center_dbus_service"
grep -Fqx "ExecStart=$install_bindir/proton-vpn-kde-agent" "$agent_systemd_service"
grep -Fqx "BusName=proton.vpn.app.kde.Agent" "$agent_systemd_service"
grep -qx 'NoNewPrivileges=true' "$systemd_service"
grep -qx 'PrivateTmp=true' "$systemd_service"
grep -qx 'ProtectSystem=full' "$systemd_service"

smoke_log="$staging_dir/smoke.log"
if ! env \
        PROTON_KDE_BUILD_DIR="$staging_dir$install_bindir" \
        PROTON_KDE_BACKEND_EXECUTABLE="$launcher" \
        dbus-run-session -- "$project_dir/scripts/smoke-demo.sh" \
        >"$smoke_log" 2>&1; then
    cat "$smoke_log" >&2
    exit 1
fi
