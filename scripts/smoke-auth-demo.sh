#!/usr/bin/bash
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

PYTHONPATH="$project_dir/backend" \
    /usr/bin/python3 -m proton_vpn_kde_backend --demo-logged-out &
backend_pid=$!

for _ in {1..40}; do
    if gdbus introspect --session \
        --dest proton.vpn.app.kde.backend \
        --object-path /proton/vpn/app/kde/backend >/dev/null 2>&1; then
        break
    fi
    sleep 0.05
done

/usr/bin/python3 "$project_dir/scripts/auth-dbus-client.py"
