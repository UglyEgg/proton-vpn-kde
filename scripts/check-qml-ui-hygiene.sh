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

if rg -n '(Timer|WorkerScript|WebSocket)\s*\{' \
        "$qml_dir/ConnectionInspectorPage.qml"; then
    echo "The on-demand Connection Inspector must not collect in the background" >&2
    exit 1
fi

if ! rg -q 'onSnapshotChanged' \
        "$qml_dir/ConnectionInspectorPage.qml" \
        || ! rg -q 'ensureInspectorModels\(\)' \
        "$qml_dir/ConnectionInspectorPage.qml"; then
    echo "The open Connection Inspector must recover its models after a backend snapshot changes" >&2
    exit 1
fi

if ! rg -q 'root\.mirrored.*go-previous-symbolic.*go-next-symbolic' \
        "$qml_dir/PlasmaListItem.qml"; then
    echo "The shared navigation row must preserve RTL directionality" >&2
    exit 1
fi

if ! rg -q 'id: connectionFacts' "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'signal copyPortRequested\(\)' \
        "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'onCopyPortRequested' "$qml_dir/OverviewPage.qml" \
        || ! rg -q 'root\.navigateRequested\("inspector"\)' \
        "$qml_dir/ConnectionScene.qml" \
        || rg -q 'connectionDetails(Dialog|Expanded|Toggle)' \
        "$qml_dir/OverviewPage.qml"; then
    echo "Overview must present compact connection facts and keep deeper inspection on demand" >&2
    exit 1
fi

if ! rg -q 'id: routeDiagram' "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'qsTr\("This device"\)' "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'qsTr\("Encrypted tunnel"\)' \
        "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'onNavigateRequested' "$qml_dir/OverviewPage.qml"; then
    echo "Overview must present the connection as a graphical device-to-destination route" >&2
    exit 1
fi

if ! rg -q 'objectName: "fastestServerCard"' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'qsTr\("Fastest suitable server"\)' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'qsTr\("Must support"\)' \
        "$qml_dir/LocationsPage.qml" \
        || ! rg -q 'ServerCapabilitySelector' \
        "$qml_dir/LocationsPage.qml"; then
    echo "Server discovery must lead with a visible fastest-suitable intent and capability criteria" >&2
    exit 1
fi

if ! rg -q 'id: moreAction' "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'text: qsTr\("More options"\)' \
        "$qml_dir/ConnectionScene.qml" \
        || ! rg -q 'icon.name: "configure"' \
        "$qml_dir/ConnectionScene.qml" \
        || rg -q 'globalDrawer\s*:' "$qml_dir/Main.qml"; then
    echo "Overview must own application navigation without a persistent sidebar or drawer" >&2
    exit 1
fi
