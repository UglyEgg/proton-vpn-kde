#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
    echo "usage: $0 /path/to/python3-proton-keyring-linux.rpm" >&2
    exit 2
fi

package_path="$(realpath "$1")"
overlay_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
manifest="$overlay_dir/overlay-manifest.json"
spec="$overlay_dir/python3-proton-keyring-linux.spec"
mapfile -t manifest_identity < <(
    python3 -c \
        'import json,sys; o=json.load(open(sys.argv[1]))["overlay"]; print(o["packageName"]); print(o["version"]); print(o["release"])' \
        "$manifest"
)
if [[ ${#manifest_identity[@]} -ne 3 ]]; then
    echo "Unable to read package identity from keyring overlay manifest" >&2
    exit 1
fi
expected_nevra="${manifest_identity[0]}-${manifest_identity[1]}-${manifest_identity[2]}$(rpm --eval '%{?dist}').noarch"
spec_nevra="$(rpmspec -q --qf '%{NEVRA}' "$spec")"
if [[ "$spec_nevra" != "$expected_nevra" ]]; then
    echo "Keyring overlay manifest/spec identity mismatch" >&2
    echo "manifest: $expected_nevra" >&2
    echo "spec:     $spec_nevra" >&2
    exit 1
fi
actual_nevra="$(rpm -qp --qf '%{NEVRA}' "$package_path")"
if [[ "$actual_nevra" != "$expected_nevra" ]]; then
    echo "Unexpected keyring overlay NEVRA: $actual_nevra" >&2
    exit 1
fi

provides="$(rpm -qp --provides "$package_path")"
mapfile -t expected_capabilities < <(
    python3 -c \
        'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["overlay"]["capabilities"]))' \
        "$manifest"
)
for capability in "${expected_capabilities[@]}"; do
    grep -Fxq "$capability" <<<"$provides"
done

requires="$(rpm -qp --requires "$package_path")"
for required in python3-keyring python3-proton-core python3-secretstorage; do
    grep -Fxq "$required" <<<"$requires"
done
if grep -Eq '^gnome-keyring([[:space:]]|$)' <<<"$requires"; then
    echo "The provider-neutral overlay unexpectedly requires GNOME Keyring" >&2
    exit 1
fi

payload="$(rpm -qpl "$package_path")"
grep -Eq '/proton/keyring_linux/core/keyring_linux\.py$' <<<"$payload"
grep -Eq '/proton/keyring_linux/secretservice/secretservice_backend\.py$' <<<"$payload"
grep -Eq '/doc/python3-proton-keyring-linux/overlay-manifest\.json$' <<<"$payload"

extract_dir="$(mktemp -d)"
trap 'rm -rf "$extract_dir"' EXIT
(
    cd "$extract_dir"
    rpm2cpio "$package_path" | cpio -id --quiet \
        './usr/share/doc/python3-proton-keyring-linux/overlay-manifest.json'
)
cmp --silent "$manifest" \
    "$extract_dir/usr/share/doc/python3-proton-keyring-linux/overlay-manifest.json"

rpmkeys --checksig "$package_path"
echo "Keyring overlay RPM checks passed: $package_path"
