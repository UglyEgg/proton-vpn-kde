#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -gt 1 ]]; then
    echo "usage: $0 [output-directory]" >&2
    exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
output_dir="${1:-$project_dir/deb-build/client}"
mkdir -p "$output_dir"
output_dir="$(realpath "$output_dir")"

for command in dpkg-buildpackage git gzip tar; do
    if ! command -v "$command" >/dev/null; then
        echo "Required build command is unavailable: $command" >&2
        exit 1
    fi
done

version="$(sed -n \
    's/^project(proton-vpn-kde VERSION \([^ ]*\) LANGUAGES CXX)$/\1/p' \
    "$project_dir/CMakeLists.txt")"
debian_full_version="$(sed -n \
    '1s/^proton-vpn-kde (\([^)]*\)).*/\1/p' \
    "$project_dir/debian/changelog")"
debian_upstream_version="${debian_full_version%%-*}"
if [[ -z "$version" || "$debian_upstream_version" != "$version" ]]; then
    echo "CMake and Debian package versions are not aligned" >&2
    printf 'cmake=%s debian=%s\n' "$version" "$debian_full_version" >&2
    exit 1
fi

work_root="$(mktemp -d /tmp/proton-vpn-kde-deb.XXXXXX)"
cleanup() {
    rm -rf -- "$work_root"
}
trap cleanup EXIT

source_name="proton-vpn-kde-$version"
source_dir="$work_root/$source_name"
mkdir -p "$source_dir"

git -C "$project_dir" ls-files -z \
    | tar --null -C "$project_dir" --files-from=- -cf - \
    | tar -C "$source_dir" -xf -

source_date_epoch="$(git -C "$project_dir" log -1 --format=%ct)"
export SOURCE_DATE_EPOCH="$source_date_epoch"
orig_tar="$work_root/proton-vpn-kde_${version}.orig.tar.gz"
tar \
    --sort=name \
    --mtime="@$SOURCE_DATE_EPOCH" \
    --owner=0 \
    --group=0 \
    --numeric-owner \
    --exclude="$source_name/debian" \
    -C "$work_root" \
    -cf - "$source_name" \
    | gzip -n >"$orig_tar"

(
    cd "$source_dir"
    DEB_BUILD_OPTIONS="${DEB_BUILD_OPTIONS:-parallel=2}" \
        dpkg-buildpackage -us -uc
)

mapfile -t artifacts < <(
    find "$work_root" -maxdepth 1 -type f \
        \( -name 'proton-vpn-kde_*' \
        -o -name 'proton-vpn-kde-dbgsym_*' \) -print | sort
)
if [[ ${#artifacts[@]} -lt 7 ]]; then
    echo "The Debian client build did not produce the complete artifact set" >&2
    printf '%s\n' "${artifacts[@]}" >&2
    exit 1
fi

install -m 0644 "${artifacts[@]}" "$output_dir/"
find "$output_dir" -maxdepth 1 -type f \
    \( -name 'proton-vpn-kde_*' \
    -o -name 'proton-vpn-kde-dbgsym_*' \) -print | sort
