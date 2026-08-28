#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:?Pass the CMake build directory}"
staging_dir="$(mktemp -d)"

cleanup() {
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

DESTDIR="$staging_dir" cmake --install "$build_dir" --prefix /usr >/dev/null

launcher="$staging_dir/usr/bin/proton-vpn-kde-backend"
dbus_service="$staging_dir/usr/share/dbus-1/services/proton.vpn.app.kde.backend.service"
systemd_service="$staging_dir/usr/lib64/systemd/user/proton-vpn-kde-backend.service"

test -x "$launcher"
test -d "$staging_dir/usr/libexec/proton-vpn-kde/proton_vpn_kde_backend"
grep -qx 'Exec=/usr/bin/env proton-vpn-kde-backend' "$dbus_service"
grep -qx 'ExecStart=proton-vpn-kde-backend' "$systemd_service"
if grep -q '/usr/local' "$launcher" "$dbus_service" "$systemd_service"; then
    echo "Installed launch metadata contains the configure-time prefix" >&2
    exit 1
fi

smoke_log="$staging_dir/smoke.log"
if ! env \
        PROTON_KDE_BUILD_DIR="$staging_dir/usr/bin" \
        PROTON_KDE_BACKEND_EXECUTABLE="$launcher" \
        dbus-run-session -- "$project_dir/scripts/smoke-demo.sh" \
        >"$smoke_log" 2>&1; then
    cat "$smoke_log" >&2
    exit 1
fi
