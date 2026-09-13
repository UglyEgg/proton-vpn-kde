#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -gt 2 ]]; then
    echo "usage: $0 [output-directory] [vendor-deb]" >&2
    exit 2
fi

overlay_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$overlay_dir/../../.." && pwd)"
manifest="$overlay_dir/overlay-manifest.json"
output_dir="${1:-$project_dir/deb-build/api-core}"
vendor_deb="${2:-}"
mkdir -p "$output_dir"
output_dir="$(realpath "$output_dir")"

for command in curl dpkg-buildpackage dpkg-deb gzip patch python3 tar; do
    if ! command -v "$command" >/dev/null; then
        echo "Required overlay build command is unavailable: $command" >&2
        exit 1
    fi
done

readarray -t manifest_values < <(python3 - "$manifest" <<'PY'
import json
from pathlib import Path
import sys

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(manifest["vendor"]["url"])
print(manifest["vendor"]["filename"])
print(manifest["vendor"]["version"])
print(manifest["overlay"]["sourceDateEpoch"])
PY
)
vendor_url="${manifest_values[0]}"
vendor_filename="${manifest_values[1]}"
version="${manifest_values[2]}"
source_date_epoch="${manifest_values[3]}"

work_root="$(mktemp -d /tmp/proton-api-core-deb.XXXXXX)"
cleanup() {
    rm -rf -- "$work_root"
}
trap cleanup EXIT

if [[ -z "$vendor_deb" ]]; then
    vendor_deb="$work_root/$vendor_filename"
    curl --fail --location --silent --show-error \
        --output "$vendor_deb" "$vendor_url"
elif [[ ! -f "$vendor_deb" ]]; then
    echo "Vendor package does not exist: $vendor_deb" >&2
    exit 1
else
    vendor_deb="$(realpath "$vendor_deb")"
fi

source_name="proton-vpn-api-core-$version"
source_dir="$work_root/$source_name"
mkdir -p "$source_dir/patches"
install -m 0644 "$vendor_deb" "$source_dir/$vendor_filename"
install -m 0644 \
    "$manifest" \
    "$overlay_dir/overlay-manifest.json.license" \
    "$overlay_dir/README.md" \
    "$source_dir/"
install -m 0755 "$overlay_dir/rebuild_overlay.py" "$source_dir/"
install -m 0755 \
    "$project_dir/packaging/fedora/api-core-overlay/rebuild_overlay.py" \
    "$source_dir/api-core-overlay-verifier.py"
install -m 0644 \
    "$project_dir"/packaging/fedora/api-core-overlay/patches/*.patch \
    "$source_dir/patches/"
cp -a "$overlay_dir/debian" "$source_dir/"

export SOURCE_DATE_EPOCH="$source_date_epoch"
orig_tar="$work_root/proton-vpn-api-core_${version}.orig.tar.gz"
tar \
    --sort=name \
    --mtime="@$SOURCE_DATE_EPOCH" \
    --owner=0 \
    --group=0 \
    --numeric-owner \
    --exclude="$source_name/debian" \
    -C "$work_root" \
    -cf - "$source_name" \
    | gzip -n >"$orig_tar"

(
    cd "$source_dir"
    DEB_BUILD_OPTIONS="${DEB_BUILD_OPTIONS:-parallel=2}" \
        dpkg-buildpackage -us -uc
)

mapfile -t artifacts < <(
    find "$work_root" -maxdepth 1 -type f \
        \( -name 'proton-vpn-api-core_*' \
        -o -name 'python3-proton-vpn-api-core_*' \) -print | sort
)
if [[ ${#artifacts[@]} -lt 6 ]]; then
    echo "The API-Core overlay build did not produce the complete artifact set" >&2
    printf '%s\n' "${artifacts[@]}" >&2
    exit 1
fi

install -m 0644 "${artifacts[@]}" "$output_dir/"
find "$output_dir" -maxdepth 1 -type f \
    \( -name 'proton-vpn-api-core_*' \
    -o -name 'python3-proton-vpn-api-core_*' \) -print | sort
