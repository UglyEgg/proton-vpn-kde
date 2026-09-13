#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -ne 4 ]]; then
    echo "usage: $0 client-dir keyring-dir api-core-dir output-dir" >&2
    exit 2
fi

client_dir="$(realpath "$1")"
keyring_dir="$(realpath "$2")"
api_core_dir="$(realpath "$3")"
output_dir="$4"
mkdir -p "$output_dir"
output_dir="$(realpath "$output_dir")"
if find "$output_dir" -mindepth 1 -print -quit | grep -q .; then
    echo "Release artifact directory is not empty: $output_dir" >&2
    exit 1
fi

mapfile -t client_artifacts < <(
    find "$client_dir" -maxdepth 1 -type f \
        \( -name 'proton-vpn-kde_*' \
        -o -name 'proton-vpn-kde-dbgsym_*' \) -print | sort
)
mapfile -t keyring_artifacts < <(
    find "$keyring_dir" -maxdepth 1 -type f \
        \( -name 'proton-keyring-linux_*' \
        -o -name 'python3-proton-keyring-linux_*' \) -print | sort
)
mapfile -t api_core_artifacts < <(
    find "$api_core_dir" -maxdepth 1 -type f \
        \( -name 'proton-vpn-api-core_*' \
        -o -name 'python3-proton-vpn-api-core_*' \) -print | sort
)

if [[ ${#client_artifacts[@]} -lt 7 \
        || ${#keyring_artifacts[@]} -lt 6 \
        || ${#api_core_artifacts[@]} -lt 6 ]]; then
    echo "Cannot stage an incomplete Debian release artifact set" >&2
    exit 1
fi

install -m 0644 \
    "${client_artifacts[@]}" \
    "${keyring_artifacts[@]}" \
    "${api_core_artifacts[@]}" \
    "$output_dir/"

[[ $(find "$output_dir" -maxdepth 1 -type f -name '*.deb' | wc -l) -eq 3 ]]
[[ $(find "$output_dir" -maxdepth 1 -type f -name '*.ddeb' | wc -l) -eq 1 ]]
[[ $(find "$output_dir" -maxdepth 1 -type f -name '*.dsc' | wc -l) -eq 3 ]]
find "$output_dir" -maxdepth 1 -type f -print | sort
