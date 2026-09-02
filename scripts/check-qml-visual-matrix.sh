#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"
output_dir="${2:-$build_dir/visual-matrix}"

if [[ ! -x "$build_dir/proton-vpn-kde" ]]; then
    echo "Missing Control Center executable: $build_dir/proton-vpn-kde" >&2
    exit 1
fi
mkdir -p -- "$output_dir"

validate_png() {
    local image_path="$1"
    local minimum_width="$2"
    local minimum_height="$3"
    python3 - "$image_path" "$minimum_width" "$minimum_height" <<'PY'
import pathlib
import struct
import sys

image_path = pathlib.Path(sys.argv[1])
minimum_width = int(sys.argv[2])
minimum_height = int(sys.argv[3])
header = image_path.read_bytes()[:24]
if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
    raise SystemExit(f"Invalid PNG capture: {image_path}")
width, height = struct.unpack(">II", header[16:24])
if width < minimum_width or height < minimum_height:
    raise SystemExit(
        f"Capture is smaller than its requested viewport: "
        f"{image_path} is {width}x{height}"
    )
print(f"{image_path.name}: {width}x{height}")
PY
}

capture() {
    local name="$1"
    local page="$2"
    local width="$3"
    local height="$4"
    shift 4

    local image_path="$output_dir/$name.png"
    local log_path="$output_dir/$name.log"
    local -a capture_environment=(
        "PROTON_KDE_DIAGNOSTIC_WIDTH=$width"
        "PROTON_KDE_DIAGNOSTIC_HEIGHT=$height"
        "PROTON_KDE_SNAPSHOT_DELAY_MS=900"
        "$@"
    )

    if ! dbus-run-session -- env "${capture_environment[@]}" \
            "$project_dir/scripts/capture-qml-page.sh" \
            "$build_dir" "$page" "$image_path" \
            >"$log_path" 2>&1; then
        echo "Visual capture failed: $name" >&2
        sed -n '1,240p' "$log_path" >&2
        return 1
    fi
    validate_png "$image_path" "$width" "$height"
}

capture wide-light overview-connected 1280 720 \
    PROTON_KDE_CAPTURE_COLOR_SCHEME=BreezeLight
capture compact-dark locations 480 640 \
    PROTON_KDE_CAPTURE_COLOR_SCHEME=BreezeDark
capture scaled-settings settings-protection 640 720 \
    PROTON_KDE_CAPTURE_COLOR_SCHEME=BreezeLight \
    QT_SCALE_FACTOR=1.5
capture rtl-information about 900 560 \
    PROTON_KDE_CAPTURE_COLOR_SCHEME=BreezeDark \
    PROTON_KDE_DIAGNOSTIC_RTL=1
capture contrast-two-factor sign-in-two-factor 640 720 \
    PROTON_KDE_CAPTURE_HIGH_CONTRAST=1
capture reduced-motion overview-connected 900 560 \
    PROTON_KDE_CAPTURE_COLOR_SCHEME=BreezeLight \
    PROTON_KDE_CAPTURE_REDUCED_MOTION=1

printf 'Visual matrix written to %s\n' "$output_dir"
