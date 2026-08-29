#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-${PROTON_KDE_BUILD_DIR:-$project_dir/build}}"

PROTON_KDE_DIAGNOSTIC_WIDTH=480 \
PROTON_KDE_DIAGNOSTIC_HEIGHT=640 \
    "$project_dir/scripts/smoke-qml-diagnostics.sh" "$build_dir"

PROTON_KDE_DIAGNOSTIC_RTL=1 \
    "$project_dir/scripts/smoke-qml-diagnostics.sh" "$build_dir"

QT_SCALE_FACTOR=1.5 \
PROTON_KDE_DIAGNOSTIC_WIDTH=640 \
PROTON_KDE_DIAGNOSTIC_HEIGHT=720 \
    "$project_dir/scripts/smoke-qml-diagnostics.sh" "$build_dir"
