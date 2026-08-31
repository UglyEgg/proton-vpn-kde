#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
topdir="${1:?Usage: prepare-rpmbuild-tree.sh RPM_TOPDIR [SPEC_FILE]}"
spec_file="${2:-$project_dir/packaging/fedora/proton-vpn-kde.spec}"

if [[ ! -f "$spec_file" ]]; then
    echo "RPM spec not found: $spec_file" >&2
    exit 1
fi

name="$(sed -n 's/^Name:[[:space:]]*//p' "$spec_file" | head -n 1)"
version="$(sed -n 's/^Version:[[:space:]]*//p' "$spec_file" | head -n 1)"
if [[ -z "$name" || -z "$version" ]]; then
    echo "Could not read Name and Version from $spec_file" >&2
    exit 1
fi

mkdir -p "$topdir"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS,TMP}
git -C "$project_dir" archive \
    --format=tar.gz \
    --prefix="${name}-${version}/" \
    --output="$topdir/SOURCES/${name}-${version}.tar.gz" \
    HEAD
install -m 0644 "$spec_file" "$topdir/SPECS/"
