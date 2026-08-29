#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"
page_name="${2:-overview}"
output_path="${3:?output path required}"
staging_dir="$(mktemp -d)"
backend_pid=""

cleanup() {
    if [[ -n "$backend_pid" ]]; then
        kill "$backend_pid" 2>/dev/null || true
        wait "$backend_pid" 2>/dev/null || true
    fi
    rm -rf -- "$staging_dir"
}
trap cleanup EXIT

PYTHONPATH="$project_dir/backend" \
    /usr/bin/python3 -m proton_vpn_kde_backend --demo \
    >"$staging_dir/backend.log" 2>&1 &
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

env \
    QT_QPA_PLATFORM=offscreen \
    QT_QUICK_BACKEND=software \
    QT_QPA_PLATFORMTHEME="${QT_QPA_PLATFORMTHEME:-generic}" \
    QT_ACCESSIBILITY=0 \
    XDG_CACHE_HOME="$staging_dir/cache" \
    XDG_CONFIG_HOME="$staging_dir/config" \
    "$build_dir/proton-vpn-kde" \
        --visual-page "$page_name" \
        --visual-snapshot "$output_path"
