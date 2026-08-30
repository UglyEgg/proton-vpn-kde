#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
qml_dir="$project_dir/qml"

if rg -n 'font\.(pixelSize|pointSize)\s*:' "$qml_dir"; then
    echo "Use theme fonts and heading levels instead of fixed font sizes" >&2
    exit 1
fi

if rg -n "color\\s*:\\s*(['\"]#|Qt\\.(rgba|hsla)\\()" "$qml_dir"; then
    echo "Use Kirigami semantic colors instead of literal colors" >&2
    exit 1
fi

if rg -n '(NumberAnimation|ColorAnimation|PropertyAnimation)\s*\{' "$qml_dir"; then
    echo "Custom animation must explicitly honor the Plasma motion setting" >&2
    exit 1
fi

if ! rg -q 'root\.mirrored.*go-previous-symbolic.*go-next-symbolic' \
        "$qml_dir/PlasmaListItem.qml"; then
    echo "The shared navigation row must preserve RTL directionality" >&2
    exit 1
fi
