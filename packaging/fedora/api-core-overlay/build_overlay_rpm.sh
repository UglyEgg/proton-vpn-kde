#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

overlay_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
vendor_rpm="${1:-}"
topdir="${2:-}"

if [[ -z "$vendor_rpm" || ! -f "$vendor_rpm" ]]; then
    echo "usage: $0 /path/to/python3-proton-vpn-api-core-5.6.10-1.fc44.x86_64.rpm [rpmbuild-dir]" >&2
    exit 2
fi

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

install -m 0644 "$vendor_rpm" "$topdir/SOURCES/"
install -m 0644 "$overlay_dir/overlay-manifest.json" "$topdir/SOURCES/"
install -m 0755 "$overlay_dir/rebuild_overlay.py" "$topdir/SOURCES/"
install -m 0644 "$overlay_dir/patches/"*.patch "$topdir/SOURCES/"
install -m 0644 \
    "$overlay_dir/python3-proton-vpn-api-core-overlay.spec" \
    "$topdir/SPECS/"

rpmbuild -ba \
    --define "_topdir $topdir" \
    --define "_tmppath $topdir/tmp" \
    "$topdir/SPECS/python3-proton-vpn-api-core-overlay.spec"

overlay_rpm="$topdir/RPMS/x86_64/python3-proton-vpn-api-core-5.6.10-6.plasmavpn1.fc44.x86_64.rpm"
"$overlay_dir/rebuild_overlay.py" verify-rpm \
    --manifest "$overlay_dir/overlay-manifest.json" \
    --vendor-rpm "$vendor_rpm" \
    --overlay-rpm "$overlay_rpm"

sha256sum "$overlay_rpm"
echo "$overlay_rpm"
