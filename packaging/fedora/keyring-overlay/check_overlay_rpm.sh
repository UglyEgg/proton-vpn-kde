#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -ne 1 || ! -f "$1" ]]; then
    echo "usage: $0 /path/to/python3-proton-keyring-linux.rpm" >&2
    exit 2
fi

package_path="$(realpath "$1")"
expected_nevra='python3-proton-keyring-linux-0.2.3-4.plasmavpn1.fc44.noarch'
actual_nevra="$(rpm -qp --qf '%{NEVRA}' "$package_path")"
if [[ "$actual_nevra" != "$expected_nevra" ]]; then
    echo "Unexpected keyring overlay NEVRA: $actual_nevra" >&2
    exit 1
fi

provides="$(rpm -qp --provides "$package_path")"
grep -Fxq 'proton-keyring-secret-service-provider-agnostic = 1' <<<"$provides"

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

rpmkeys --checksig "$package_path"
echo "Keyring overlay RPM checks passed: $package_path"
