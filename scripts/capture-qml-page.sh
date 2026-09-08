#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

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

demo_mode="--demo"
if [[ "$page_name" == "sign-in" || "$page_name" == "sign-in-two-factor" ]]; then
    demo_mode="--demo-logged-out"
fi

PYTHONPATH="$project_dir/backend" \
    /usr/bin/python3 -m proton_vpn_kde_backend "$demo_mode" \
    >"$staging_dir/backend.log" 2>&1 &
backend_pid=$!

for _ in {1..40}; do
    if [[ "$(gdbus call --session \
        --dest org.freedesktop.DBus \
        --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner \
        quest.entropy.PlasmaVPN.Backend 2>/dev/null)" == "(true,)" ]]; then
        break
    fi
    sleep 0.05
done

owner_reply="$(gdbus call --session \
    --dest org.freedesktop.DBus \
    --object-path /org/freedesktop/DBus \
    --method org.freedesktop.DBus.GetNameOwner \
    quest.entropy.PlasmaVPN.Backend)"
backend_owner="${owner_reply#*\'}"
backend_owner="${backend_owner%%\'*}"

if [[ "$page_name" == "sign-in-two-factor" ]]; then
    /usr/bin/python3 "$project_dir/scripts/auth-dbus-client.py" \
        --stop-after-challenge >/dev/null
    page_name="sign-in"
fi

capture_color_scheme="${PROTON_KDE_CAPTURE_COLOR_SCHEME:-}"
capture_platform_theme="${QT_QPA_PLATFORMTHEME:-generic}"
if [[ -n "$capture_color_scheme" ]]; then
    if [[ ! "$capture_color_scheme" =~ ^[A-Za-z0-9_.-]+$ ]]; then
        echo "Invalid Plasma color-scheme name" >&2
        exit 2
    fi
    color_scheme_path="/usr/share/color-schemes/$capture_color_scheme.colors"
    if [[ ! -f "$color_scheme_path" ]]; then
        echo "Plasma color scheme not found: $capture_color_scheme" >&2
        exit 2
    fi
    mkdir -p -- "$staging_dir/config"
    cp -- "$color_scheme_path" "$staging_dir/config/kdeglobals"
    XDG_CONFIG_HOME="$staging_dir/config" \
        kwriteconfig6 --file kdeglobals --group General \
        --key ColorScheme "$capture_color_scheme"
    if [[ -z "${QT_QPA_PLATFORMTHEME:-}" ]]; then
        capture_platform_theme="kde"
    fi
fi

if [[ "${PROTON_KDE_CAPTURE_HIGH_CONTRAST:-0}" == "1" ]]; then
    if [[ ! -f "$staging_dir/config/kdeglobals" ]]; then
        contrast_base="/usr/share/color-schemes/BreezeDark.colors"
        if [[ ! -f "$contrast_base" ]]; then
            echo "Contrast fixture base scheme not found: $contrast_base" >&2
            exit 2
        fi
        mkdir -p -- "$staging_dir/config"
        cp -- "$contrast_base" "$staging_dir/config/kdeglobals"
    fi
    for color_group in Window View Button Tooltip Complementary Header; do
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key BackgroundNormal "0,0,0"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key BackgroundAlternate "24,24,24"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key ForegroundNormal "255,255,255"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key ForegroundInactive "210,210,210"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key ForegroundLink "0,255,255"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key ForegroundNegative "255,128,128"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key ForegroundNeutral "255,255,0"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key ForegroundPositive "128,255,128"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key DecorationFocus "0,255,255"
        XDG_CONFIG_HOME="$staging_dir/config" \
            kwriteconfig6 --file kdeglobals --group "Colors:$color_group" \
            --key DecorationHover "255,255,0"
    done
    XDG_CONFIG_HOME="$staging_dir/config" \
        kwriteconfig6 --file kdeglobals --group Colors:Selection \
        --key BackgroundNormal "0,80,160"
    XDG_CONFIG_HOME="$staging_dir/config" \
        kwriteconfig6 --file kdeglobals --group Colors:Selection \
        --key ForegroundNormal "255,255,255"
    XDG_CONFIG_HOME="$staging_dir/config" \
        kwriteconfig6 --file kdeglobals --group General \
        --key ColorScheme "PlasmaVPNContrastStress"
    if [[ -z "${QT_QPA_PLATFORMTHEME:-}" ]]; then
        capture_platform_theme="kde"
    fi
fi

if [[ "${PROTON_KDE_CAPTURE_REDUCED_MOTION:-0}" == "1" ]]; then
    mkdir -p -- "$staging_dir/config"
    XDG_CONFIG_HOME="$staging_dir/config" \
        kwriteconfig6 --file kdeglobals --group KDE \
        --key AnimationDurationFactor 0
fi

if [[ "$page_name" == *"-connected" ]]; then
    gdbus call --session \
        --dest quest.entropy.PlasmaVPN.Backend \
        --object-path /quest/entropy/PlasmaVPN/Backend \
        --method quest.entropy.PlasmaVPN.Backend1.ConnectFastest \
        >/dev/null
    for _ in {1..20}; do
        snapshot="$(gdbus call --session \
            --dest quest.entropy.PlasmaVPN.Backend \
            --object-path /quest/entropy/PlasmaVPN/Backend \
            --method quest.entropy.PlasmaVPN.Backend1.GetSnapshot)"
        if [[ "$snapshot" == *'"state":"connected"'* ]]; then
            break
        fi
        sleep 0.05
    done
    if [[ "$snapshot" != *'"state":"connected"'* ]]; then
        echo "Demo backend did not reach the connected state" >&2
        exit 1
    fi
    page_name="${page_name%-connected}"
fi

if [[ "$page_name" == "overview-split" ]]; then
    gdbus call --session \
        --dest quest.entropy.PlasmaVPN.Backend \
        --object-path /quest/entropy/PlasmaVPN/Backend \
        --method quest.entropy.PlasmaVPN.Backend1.UpdateSplitTunneling \
        '{"enabled":true}' >/dev/null
    page_name="overview"
fi

env \
    GTK_USE_PORTAL=0 \
    QT_QPA_PLATFORM=offscreen \
    QT_QUICK_BACKEND=software \
    QT_QPA_PLATFORMTHEME="$capture_platform_theme" \
    QT_ACCESSIBILITY=0 \
    QT_NO_XDG_DESKTOP_PORTAL=1 \
    XDG_CACHE_HOME="$staging_dir/cache" \
    XDG_CONFIG_HOME="$staging_dir/config" \
    PROTON_VPN_KDE_TEST_BACKEND_OWNER="$backend_owner" \
    "$build_dir/proton-vpn-kde" \
        --visual-page "$page_name" \
        --visual-snapshot "$output_path"
