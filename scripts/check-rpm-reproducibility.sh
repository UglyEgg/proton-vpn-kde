#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "usage: $0 FIRST_RPM_TOPDIR SECOND_RPM_TOPDIR" >&2
    exit 2
fi

first_topdir="$(realpath "$1")"
second_topdir="$(realpath "$2")"

mapfile -t first_artifacts < <(
    cd "$first_topdir"
    find RPMS SRPMS -type f -name '*.rpm' -printf '%p\n' | sort
)
mapfile -t second_artifacts < <(
    cd "$second_topdir"
    find RPMS SRPMS -type f -name '*.rpm' -printf '%p\n' | sort
)

if [[ ${#first_artifacts[@]} -eq 0 \
        || "${first_artifacts[*]}" != "${second_artifacts[*]}" ]]; then
    echo "Clean rebuilds did not produce the same RPM output set" >&2
    exit 1
fi

for relative_path in "${first_artifacts[@]}"; do
    if ! cmp --silent \
            "$first_topdir/$relative_path" \
            "$second_topdir/$relative_path"; then
        echo "RPM is not byte-reproducible: $relative_path" >&2
        exit 1
    fi
done

echo "RPM output set is byte-reproducible (${#first_artifacts[@]} artifacts)"
