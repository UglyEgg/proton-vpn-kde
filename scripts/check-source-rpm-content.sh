#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -lt 4 ]]; then
    echo "usage: $0 BINARY_RPM SOURCE_RPM SPEC SOURCE_NAME=EXPECTED_FILE..." >&2
    exit 2
fi

binary_rpm="$(realpath "$1")"
source_rpm="$(realpath "$2")"
spec="$(realpath "$3")"
shift 3

expected_source_rpm="$(rpm -qp --qf '%{SOURCERPM}' "$binary_rpm")"
if [[ "$(basename "$source_rpm")" != "$expected_source_rpm" ]]; then
    echo "Binary/source RPM identity mismatch" >&2
    exit 1
fi
expected_nvr="${expected_source_rpm%.src.rpm}"
actual_nvr="$(rpm -qp --qf '%{NAME}-%{VERSION}-%{RELEASE}' "$source_rpm")"
actual_source_flag="$(rpm -qp --qf '%{SOURCEPACKAGE}' "$source_rpm")"
if [[ "$actual_nvr" != "$expected_nvr" || "$actual_source_flag" != "1" ]]; then
    echo "Unexpected source RPM identity: $actual_nvr" >&2
    exit 1
fi

extract_dir="$(mktemp -d)"
trap 'rm -rf "$extract_dir"' EXIT
(
    cd "$extract_dir"
    rpm2cpio "$source_rpm" | cpio -id --quiet
)

spec_name="$(basename "$spec")"
cmp --silent "$spec" "$extract_dir/$spec_name" || {
    echo "Source RPM spec differs from $spec_name" >&2
    exit 1
}

for mapping in "$@"; do
    source_name="${mapping%%=*}"
    expected_file="${mapping#*=}"
    if [[ "$source_name" == "$mapping" || ! -f "$expected_file" ]]; then
        echo "Invalid source comparison: $mapping" >&2
        exit 1
    fi
    cmp --silent "$expected_file" "$extract_dir/$source_name" || {
        echo "Source RPM content differs for $source_name" >&2
        exit 1
    }
done

rpmkeys --checksig "$source_rpm"
echo "Source RPM content checks passed: $source_rpm"
