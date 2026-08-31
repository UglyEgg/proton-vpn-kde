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

overlay_rpm="$topdir/RPMS/x86_64/python3-proton-vpn-api-core-5.6.10-8.plasmavpn1.fc44.x86_64.rpm"
"$overlay_dir/rebuild_overlay.py" verify-rpm \
    --manifest "$overlay_dir/overlay-manifest.json" \
    --vendor-rpm "$vendor_rpm" \
    --signing-key "$signing_key" \
    --overlay-rpm "$overlay_rpm"

sha256sum "$overlay_rpm"
echo "$overlay_rpm"
