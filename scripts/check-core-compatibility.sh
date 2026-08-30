#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if (( $# > 1 )); then
    echo "usage: $0 [python3-proton-vpn-api-core.rpm]" >&2
    exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifest="$project_dir/packaging/fedora/core-compatibility.json"
mapfile -t fixture < <(
    python3 -c \
        'import json,sys; item=json.load(open(sys.argv[1]))["minimum"]; print(item["version"], item["nevra"], item["url"], item["sha256"], sep="\n")' \
        "$manifest"
)
expected_version="${fixture[0]}"
expected_nevra="${fixture[1]}"
fixture_url="${fixture[2]}"
expected_sha256="${fixture[3]}"

work_dir="$(mktemp -d "${TMPDIR:-/tmp}/plasma-vpn-core-compatibility.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT

fixture_rpm="${1:-$work_dir/core.rpm}"
if (( $# == 0 )); then
    curl --proto '=https' --tlsv1.2 --location --fail --silent --show-error \
        "$fixture_url" --output "$fixture_rpm"
fi

actual_sha256="$(sha256sum "$fixture_rpm" | cut -d' ' -f1)"
if [[ "$actual_sha256" != "$expected_sha256" ]]; then
    echo "Core fixture SHA-256 does not match the pinned manifest" >&2
    exit 1
fi

actual_nevra="$(rpm -qp --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}' "$fixture_rpm")"
if [[ "$actual_nevra" != "$expected_nevra" ]]; then
    echo "Expected Core fixture $expected_nevra, found $actual_nevra" >&2
    exit 1
fi

extract_root="$work_dir/root"
mkdir -p "$extract_root"
(
    cd "$extract_root"
    rpm2cpio "$fixture_rpm" | cpio -idm --quiet
)
python3 "$project_dir/scripts/check-core-contract.py" \
    --root "$extract_root" \
    --expected-version "$expected_version"
