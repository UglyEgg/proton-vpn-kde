#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -gt 2 ]]; then
    echo "usage: $0 [output-directory] [upstream-archive]" >&2
    exit 2
fi

overlay_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project_dir="$(cd "$overlay_dir/../../.." && pwd)"
shared_overlay_dir="$project_dir/packaging/fedora/keyring-overlay"
manifest="$shared_overlay_dir/overlay-manifest.json"
output_dir="${1:-$project_dir/deb-build/keyring}"
archive="${2:-}"
mkdir -p "$output_dir"
output_dir="$(realpath "$output_dir")"

for command in curl dpkg-buildpackage filterdiff gzip patch python3 tar; do
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
print(manifest["upstream"]["archiveUrl"])
print(manifest["upstream"]["archiveFilename"])
print(manifest["upstream"]["archiveSha256"])
print(manifest["upstream"]["tag"].removeprefix("v"))
print(manifest["upstream"].get("sourceDateEpoch", 1781172000))
PY
)
archive_url="${manifest_values[0]}"
archive_name="${manifest_values[1]}"
archive_sha256="${manifest_values[2]}"
version="${manifest_values[3]}"
source_date_epoch="${manifest_values[4]}"

work_root="$(mktemp -d /tmp/proton-keyring-deb.XXXXXX)"
cleanup() {
    rm -rf -- "$work_root"
}
trap cleanup EXIT

if [[ -z "$archive" ]]; then
    archive="$work_root/$archive_name"
    curl --fail --location --silent --show-error \
        --output "$archive" "$archive_url"
elif [[ ! -f "$archive" ]]; then
    echo "Upstream archive does not exist: $archive" >&2
    exit 1
else
    archive="$(realpath "$archive")"
fi

actual_archive_sha256="$(sha256sum "$archive" | cut -d ' ' -f 1)"
if [[ "$actual_archive_sha256" != "$archive_sha256" ]]; then
    echo "Upstream archive SHA-256 mismatch" >&2
    echo "expected: $archive_sha256" >&2
    echo "actual:   $actual_archive_sha256" >&2
    exit 1
fi

python3 - "$manifest" "$shared_overlay_dir/patches" <<'PY'
import hashlib
import json
from pathlib import Path
import sys

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
patch_dir = Path(sys.argv[2])
for record in manifest["overlay"]["patches"]:
    path = patch_dir / record["file"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != record["sha256"]:
        raise SystemExit(f"Patch SHA-256 mismatch: {path.name}")
PY

unpack_dir="$work_root/unpack"
mkdir -p "$unpack_dir"
tar -xzf "$archive" -C "$unpack_dir"
source_dir="$work_root/proton-keyring-linux-$version"
mv "$unpack_dir/python-proton-keyring-linux-$version" "$source_dir"

rm -rf -- "$source_dir/debian"
mkdir -p "$source_dir/debian/patches" "$source_dir/debian/source"
cp -a "$overlay_dir/debian/." "$source_dir/debian/"

filterdiff -x '*/debian/control' \
    "$shared_overlay_dir/patches/0001-provider-agnostic-secret-service.patch" \
    >"$source_dir/debian/patches/0001-provider-agnostic-secret-service.patch"
install -m 0644 \
    "$shared_overlay_dir/patches/0002-avoid-missing-entry-traceback.patch" \
    "$source_dir/debian/patches/0002-avoid-missing-entry-traceback.patch"
install -m 0644 \
    "$shared_overlay_dir/patches/0003-pin-secret-service-provider.patch" \
    "$source_dir/debian/patches/0003-pin-secret-service-provider.patch"
printf '%s\n' \
    0001-provider-agnostic-secret-service.patch \
    0002-avoid-missing-entry-traceback.patch \
    0003-pin-secret-service-provider.patch \
    >"$source_dir/debian/patches/series"

export SOURCE_DATE_EPOCH="$source_date_epoch"
orig_tar="$work_root/proton-keyring-linux_${version}.orig.tar.gz"
tar \
    --sort=name \
    --mtime="@$SOURCE_DATE_EPOCH" \
    --owner=0 \
    --group=0 \
    --numeric-owner \
    --exclude="proton-keyring-linux-$version/debian" \
    -C "$work_root" \
    -cf - "proton-keyring-linux-$version" \
    | gzip -n >"$orig_tar"

(
    cd "$source_dir"
    DEB_BUILD_OPTIONS="${DEB_BUILD_OPTIONS:-parallel=2}" \
        dpkg-buildpackage -us -uc
)

mapfile -t artifacts < <(
    find "$work_root" -maxdepth 1 -type f \
        \( -name 'proton-keyring-linux_*' \
        -o -name 'python3-proton-keyring-linux_*' \) -print | sort
)
if [[ ${#artifacts[@]} -lt 6 ]]; then
    echo "The keyring overlay build did not produce the complete artifact set" >&2
    printf '%s\n' "${artifacts[@]}" >&2
    exit 1
fi

install -m 0644 "${artifacts[@]}" "$output_dir/"
find "$output_dir" -maxdepth 1 -type f \
    \( -name 'proton-keyring-linux_*' \
    -o -name 'python3-proton-keyring-linux_*' \) -print | sort
