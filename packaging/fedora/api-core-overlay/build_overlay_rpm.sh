#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

overlay_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest="$overlay_dir/overlay-manifest.json"
vendor_rpm="${1:-}"
topdir="${2:-}"
signing_key="${3:-}"

vendor_rpm_url="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["vendor"]["rpmUrl"])' \
    "$manifest")"
vendor_rpm_name="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["vendor"]["rpmFilename"])' \
    "$manifest")"
vendor_rpm_sha256="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["vendor"]["rpmSha256"])' \
    "$manifest")"
signing_key_url="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["vendor"]["signingKey"]["url"])' \
    "$manifest")"
signing_key_name="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["vendor"]["signingKey"]["filename"])' \
    "$manifest")"
signing_key_sha256="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["vendor"]["signingKey"]["sha256"])' \
    "$manifest")"

if [[ -z "$topdir" ]]; then
    topdir="$(mktemp -d /tmp/proton-api-core-overlay.XXXXXX)"
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
    "$topdir/tmp"

if [[ -z "$vendor_rpm" ]]; then
    vendor_rpm="$topdir/tmp/$vendor_rpm_name"
    curl --fail --location --silent --show-error \
        --output "$vendor_rpm" "$vendor_rpm_url"
elif [[ ! -f "$vendor_rpm" ]]; then
    echo "Vendor RPM does not exist: $vendor_rpm" >&2
    exit 1
fi

actual_vendor_rpm_sha256="$(sha256sum "$vendor_rpm" | cut -d ' ' -f 1)"
if [[ "$actual_vendor_rpm_sha256" != "$vendor_rpm_sha256" ]]; then
    echo "Vendor RPM SHA-256 mismatch" >&2
    echo "expected: $vendor_rpm_sha256" >&2
    echo "actual:   $actual_vendor_rpm_sha256" >&2
    exit 1
fi

if [[ -z "$signing_key" ]]; then
    signing_key="$topdir/tmp/$signing_key_name"
    curl --fail --location --silent --show-error \
        --output "$signing_key" "$signing_key_url"
elif [[ ! -f "$signing_key" ]]; then
    echo "Vendor signing key does not exist: $signing_key" >&2
    exit 1
fi

actual_signing_key_sha256="$(sha256sum "$signing_key" | cut -d ' ' -f 1)"
if [[ "$actual_signing_key_sha256" != "$signing_key_sha256" ]]; then
    echo "Vendor signing-key SHA-256 mismatch" >&2
    echo "expected: $signing_key_sha256" >&2
    echo "actual:   $actual_signing_key_sha256" >&2
    exit 1
fi

install -m 0644 "$vendor_rpm" "$topdir/SOURCES/"
install -m 0644 "$signing_key" "$topdir/SOURCES/"
install -m 0644 "$manifest" "$topdir/SOURCES/"
install -m 0755 "$overlay_dir/rebuild_overlay.py" "$topdir/SOURCES/"
install -m 0644 "$overlay_dir/patches/"*.patch "$topdir/SOURCES/"
install -m 0644 \
    "$overlay_dir/python3-proton-vpn-api-core-overlay.spec" \
    "$topdir/SPECS/"

rpmbuild -ba \
    --define "_topdir $topdir" \
    --define "_tmppath $topdir/tmp" \
    "$topdir/SPECS/python3-proton-vpn-api-core-overlay.spec"

overlay_nevra="$(python3 -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["overlay"]["nevra"])' \
    "$manifest")"
overlay_rpm="$topdir/RPMS/x86_64/$overlay_nevra.rpm"
"$overlay_dir/rebuild_overlay.py" verify-rpm \
    --manifest "$overlay_dir/overlay-manifest.json" \
    --vendor-rpm "$vendor_rpm" \
    --signing-key "$signing_key" \
    --overlay-rpm "$overlay_rpm"

mapfile -t source_rpms < <(
    find "$topdir/SRPMS" -type f \
        -name 'python3-proton-vpn-api-core-*.src.rpm' -print
)
if [[ ${#source_rpms[@]} -ne 1 ]]; then
    echo "Expected one source API Core overlay RPM" >&2
    exit 1
fi
source_checks=(
    "$vendor_rpm_name=$(realpath "$vendor_rpm")"
    "overlay-manifest.json=$manifest"
    "rebuild_overlay.py=$overlay_dir/rebuild_overlay.py"
    "$signing_key_name=$(realpath "$signing_key")"
)
for patch_path in "$overlay_dir"/patches/*.patch; do
    source_checks+=("$(basename "$patch_path")=$patch_path")
done
bash "$overlay_dir/../../../scripts/check-source-rpm-content.sh" \
    "$overlay_rpm" \
    "${source_rpms[0]}" \
    "$overlay_dir/python3-proton-vpn-api-core-overlay.spec" \
    "${source_checks[@]}"

sha256sum "$overlay_rpm" "${source_rpms[0]}"
printf '%s\n%s\n' "$overlay_rpm" "${source_rpms[0]}"
