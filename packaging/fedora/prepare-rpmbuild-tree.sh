#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
topdir="${1:?Usage: prepare-rpmbuild-tree.sh RPM_TOPDIR [SPEC_FILE] [SOURCE_REF]}"
spec_file="${2:-$project_dir/packaging/fedora/proton-vpn-kde.spec}"
source_ref="${3:-HEAD}"

if [[ ! -f "$spec_file" ]]; then
    echo "RPM spec not found: $spec_file" >&2
    exit 1
fi

if [[ -e "$topdir" ]] && find "$topdir" -mindepth 1 -print -quit | grep -q .; then
    echo "RPM output directory must be empty: $topdir" >&2
    exit 1
fi

name="$(sed -n 's/^Name:[[:space:]]*//p' "$spec_file" | head -n 1)"
version="$(sed -n 's/^Version:[[:space:]]*//p' "$spec_file" | head -n 1)"
if [[ -z "$name" || -z "$version" ]]; then
    echo "Could not read Name and Version from $spec_file" >&2
    exit 1
fi

mkdir -p "$topdir"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS,TMP}
source_commit="$(git -C "$project_dir" rev-parse --verify "${source_ref}^{commit}")"
source_timestamp="$(git -C "$project_dir" show -s --format=%ct "$source_commit")"
archive_dir="$(mktemp -d)"
trap 'rm -rf "$archive_dir"' EXIT
archive_tar="$archive_dir/${name}-${version}.tar"
git -C "$project_dir" archive \
    --format=tar \
    --prefix="${name}-${version}/" \
    --output="$archive_tar" \
    "$source_commit"
mkdir -p "$archive_dir/${name}-${version}"
printf '%s\n' "$source_commit" \
    >"$archive_dir/${name}-${version}/.source-commit"
chmod 0644 "$archive_dir/${name}-${version}/.source-commit"
tar --append --file "$archive_tar" \
    --directory "$archive_dir" \
    --owner=0 --group=0 --numeric-owner \
    --mtime="@$source_timestamp" --mode=0644 \
    "${name}-${version}/.source-commit"
gzip --no-name --stdout "$archive_tar" \
    >"$topdir/SOURCES/${name}-${version}.tar.gz"
install -m 0644 "$spec_file" "$topdir/SPECS/"
printf 'Prepared %s from commit %s\n' "$name" "$source_commit"
