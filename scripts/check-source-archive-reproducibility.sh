#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_ref="${1:-HEAD}"
first_topdir="$(mktemp -d)"
second_topdir="$(mktemp -d)"
trap 'rm -rf "$first_topdir" "$second_topdir"' EXIT

"$project_dir/packaging/fedora/prepare-rpmbuild-tree.sh" \
    "$first_topdir" "$project_dir/packaging/fedora/proton-vpn-kde.spec" \
    "$source_ref" >/dev/null
"$project_dir/packaging/fedora/prepare-rpmbuild-tree.sh" \
    "$second_topdir" "$project_dir/packaging/fedora/proton-vpn-kde.spec" \
    "$source_ref" >/dev/null

first_archive="$(find "$first_topdir/SOURCES" -maxdepth 1 -type f \
    -name 'proton-vpn-kde-*.tar.gz' -print -quit)"
second_archive="$(find "$second_topdir/SOURCES" -maxdepth 1 -type f \
    -name 'proton-vpn-kde-*.tar.gz' -print -quit)"
if [[ -z "$first_archive" || -z "$second_archive" ]]; then
    echo "The source-archive helper did not create both archives" >&2
    exit 1
fi
cmp --silent "$first_archive" "$second_archive" || {
    echo "Source archives differ for the same commit" >&2
    exit 1
}

source_commit="$(git -C "$project_dir" rev-parse --verify "${source_ref}^{commit}")"
source_timestamp="$(git -C "$project_dir" show -s --format=%ct "$source_commit")"
python3 - "$first_archive" "$source_commit" "$source_timestamp" <<'PY'
from pathlib import Path
import sys
import tarfile

archive = Path(sys.argv[1])
expected_commit = sys.argv[2]
expected_timestamp = int(sys.argv[3])
with tarfile.open(archive, "r:gz") as source:
    markers = [item for item in source.getmembers() if item.name.endswith("/.source-commit")]
    if len(markers) != 1:
        raise SystemExit("Source archive must contain exactly one .source-commit")
    marker = markers[0]
    if (marker.uid, marker.gid, marker.mode, int(marker.mtime)) != (
        0,
        0,
        0o644,
        expected_timestamp,
    ):
        raise SystemExit(".source-commit metadata is not normalized")
    extracted = source.extractfile(marker)
    if extracted is None or extracted.read().decode().strip() != expected_commit:
        raise SystemExit(".source-commit does not name the archived commit")
PY

echo "Source archive reproducibility checks passed: $source_commit"
