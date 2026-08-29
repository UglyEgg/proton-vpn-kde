#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"
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

if [[ -n "${PROTON_KDE_BACKEND_EXECUTABLE:-}" ]]; then
    "$PROTON_KDE_BACKEND_EXECUTABLE" --demo \
        >"$staging_dir/backend.log" 2>&1 &
else
    PYTHONPATH="$project_dir/backend" \
        /usr/bin/python3 -m proton_vpn_kde_backend --demo \
        >"$staging_dir/backend.log" 2>&1 &
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

if [[ "$(gdbus call --session \
    --dest org.freedesktop.DBus \
    --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.NameHasOwner \
    proton.vpn.app.kde.backend 2>/dev/null)" != "(true,)" ]]; then
    echo "Demo backend did not become available" >&2
    cat "$staging_dir/backend.log" >&2
    exit 1
fi

frontend_log="$staging_dir/frontend.log"
if ! env \
        QT_QPA_PLATFORM=offscreen \
        QT_QUICK_BACKEND=software \
        QT_QPA_PLATFORMTHEME=generic \
        QT_ACCESSIBILITY=0 \
        QT_FORCE_STDERR_LOGGING=1 \
        XDG_CACHE_HOME="$staging_dir/cache" \
        XDG_CONFIG_HOME="$staging_dir/config" \
        timeout 15s "$build_dir/proton-vpn-kde" --diagnostics-smoke \
        >"$frontend_log" 2>&1; then
    echo "Native diagnostics navigation did not exit cleanly" >&2
    cat "$frontend_log" >&2
    exit 1
fi

kirigami_version="$(rpm -q --qf '%{VERSION}' kf6-kirigami 2>/dev/null || true)"
qt_version="$(rpm -q --qf '%{VERSION}' qt6-qtdeclarative 2>/dev/null || true)"
allow_isolated_framework_diagnostics=false
if [[ "$kirigami_version" == "6.29.0" && "$qt_version" == "6.11.1" ]]; then
    allow_isolated_framework_diagnostics=true
fi

declare -A expected_lines=()
expected_lines["diagnostics-smoke: loading native interface"]=1
expected_lines["diagnostics-smoke: native interface loaded"]=1
for page in \
    Overview Locations Country Servers Account Settings "Custom DNS" \
    "Settings reload" "Split tunneling" "Release notes" "Report issue" \
    About "Sign in" "Overview reload"; do
    expected_lines["qml: diagnostics-smoke: $page"]=1
done
expected_lines["qml: diagnostics-smoke: complete"]=1

unexpected_log="$staging_dir/unexpected.log"
while IFS= read -r line; do
    if [[ -z "$line" || -n "${expected_lines[$line]:-}" ]]; then
        continue
    fi
    if $allow_isolated_framework_diagnostics; then
        case "$line" in
            "A connection to the bus can't be made"|\
            "kf.statusnotifieritem: KDE platform plugin is loaded but SNI unavailable"|\
            "Couldn't start kglobalaccel from org.kde.kglobalaccel.service: QDBusError(\"org.freedesktop.DBus.Error.ServiceUnknown\", \"The name org.kde.kglobalaccel was not provided by any .service files\")")
                continue
                ;;
        esac
    fi
    printf '%s\n' "$line" >>"$unexpected_log"
done <"$frontend_log"

for line in "${!expected_lines[@]}"; do
    if ! grep -Fqx -- "$line" "$frontend_log"; then
        echo "Missing diagnostics navigation marker: $line" >&2
        cat "$frontend_log" >&2
        exit 1
    fi
done

if [[ -s "$unexpected_log" ]]; then
    echo "Unexpected native runtime diagnostics detected" >&2
    if ! $allow_isolated_framework_diagnostics; then
        echo "The framework allowlist requires review for Kirigami $kirigami_version and Qt $qt_version" >&2
    fi
    cat "$unexpected_log" >&2
    exit 1
fi
