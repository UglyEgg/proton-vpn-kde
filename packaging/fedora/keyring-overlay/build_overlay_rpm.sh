#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

overlay_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest="$overlay_dir/overlay-manifest.json"
archive="${1:-}"
topdir="${2:-}"

archive_url="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["upstream"]["archiveUrl"])' \
    "$manifest")"
archive_name="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["upstream"]["archiveFilename"])' \
    "$manifest")"
archive_sha256="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["upstream"]["archiveSha256"])' \
    "$manifest")"

if [[ -z "$topdir" ]]; then
    topdir="$(mktemp -d /tmp/proton-keyring-overlay.XXXXXX)"
else
    mkdir -p "$topdir"
fi

mkdir -p \
    "$topdir/BUILD" \
    "$topdir/BUILDROOT" \
    "$topdir/RPMS" \
    "$topdir/SOURCES" \
    "$topdir/SPECS" \
    "$topdir/SRPMS" \
    "$topdir/TMP"

if [[ -z "$archive" ]]; then
    archive="$topdir/TMP/$archive_name"
    curl --fail --location --silent --show-error \
        --output "$archive" "$archive_url"
elif [[ ! -f "$archive" ]]; then
    echo "Upstream archive does not exist: $archive" >&2
    exit 1
fi

actual_archive_sha256="$(sha256sum "$archive" | cut -d ' ' -f 1)"
if [[ "$actual_archive_sha256" != "$archive_sha256" ]]; then
    echo "Upstream archive SHA-256 mismatch" >&2
    echo "expected: $archive_sha256" >&2
    echo "actual:   $actual_archive_sha256" >&2
    exit 1
fi

install -m 0644 "$archive" "$topdir/SOURCES/$archive_name"
install -m 0644 "$manifest" "$topdir/SOURCES/overlay-manifest.json"
install -m 0644 "$overlay_dir/README.md" \
    "$topdir/SOURCES/keyring-overlay-README.md"
install -m 0644 "$overlay_dir/patches/"*.patch "$topdir/SOURCES/"
install -m 0644 "$overlay_dir/python3-proton-keyring-linux.spec" \
    "$topdir/SPECS/"

python3 - "$manifest" "$overlay_dir/patches" \
    "$overlay_dir/python3-proton-keyring-linux.spec" <<'PY'
import hashlib
import json
from pathlib import Path
import re
import sys

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
patch_dir = Path(sys.argv[2])
spec_text = Path(sys.argv[3]).read_text(encoding="utf-8")
if manifest.get("schemaVersion") != 1:
    raise SystemExit("Unsupported overlay manifest schema")
records = manifest["overlay"]["patches"]
listed = {record["file"] for record in records}
present = {path.name for path in patch_dir.glob("*.patch")}
if listed != present:
    raise SystemExit(
        f"Manifest patch set differs from patches directory: "
        f"missing={sorted(present - listed)}, extra={sorted(listed - present)}"
    )
declared = {
    match.group(1)
    for match in re.finditer(r"^Patch\d*:\s*(\S+)\s*$", spec_text, re.MULTILINE)
}
if listed != declared:
    raise SystemExit(
        f"Manifest patch set differs from spec declarations: "
        f"missing={sorted(declared - listed)}, extra={sorted(listed - declared)}"
    )
for record in records:
    path = patch_dir / record["file"]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != record["sha256"]:
        raise SystemExit(f"Patch SHA-256 mismatch: {path.name}")
PY

rpmbuild -ba \
    --define "_topdir $topdir" \
    --define "_tmppath $topdir/TMP" \
    "$topdir/SPECS/python3-proton-keyring-linux.spec"

mapfile -t binary_rpms < <(
    find "$topdir/RPMS" -type f \
        -name 'python3-proton-keyring-linux-*.noarch.rpm' -print
)
mapfile -t source_rpms < <(
    find "$topdir/SRPMS" -type f \
        -name 'python3-proton-keyring-linux-*.src.rpm' -print
)
if [[ ${#binary_rpms[@]} -ne 1 || ${#source_rpms[@]} -ne 1 ]]; then
    echo "Expected one binary and one source keyring overlay RPM" >&2
    exit 1
fi

"$overlay_dir/check_overlay_rpm.sh" "${binary_rpms[0]}"
source_checks=(
    "$archive_name=$(realpath "$archive")"
    "overlay-manifest.json=$manifest"
    "keyring-overlay-README.md=$overlay_dir/README.md"
)
for patch_path in "$overlay_dir"/patches/*.patch; do
    source_checks+=("$(basename "$patch_path")=$patch_path")
done
bash "$overlay_dir/../../../scripts/check-source-rpm-content.sh" \
    "${binary_rpms[0]}" \
    "${source_rpms[0]}" \
    "$overlay_dir/python3-proton-keyring-linux.spec" \
    "${source_checks[@]}"
sha256sum "${binary_rpms[0]}" "${source_rpms[0]}"
printf '%s\n%s\n' "${binary_rpms[0]}" "${source_rpms[0]}"
