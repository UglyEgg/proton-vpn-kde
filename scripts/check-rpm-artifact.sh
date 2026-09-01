#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "usage: $0 /path/to/proton-vpn-kde.rpm [/path/to/source.rpm]" >&2
    exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_path="$(realpath "$1")"
expected_commit="$(git -C "$project_dir" rev-parse --verify HEAD)"

if [[ ! -f "$package_path" ]]; then
    echo "RPM does not exist: $package_path" >&2
    exit 1
fi

spec_path="$project_dir/packaging/fedora/proton-vpn-kde.spec"
mapfile -t expected_identity < <(
    rpmspec -q --qf '%{NEVRA}\n%{SOURCERPM}\n' "$spec_path"
)
if [[ ${#expected_identity[@]} -ne 2 ]]; then
    echo "Unable to derive the expected client RPM identity from $spec_path" >&2
    exit 1
fi
expected_nevra="${expected_identity[0]}"
expected_source_rpm="${expected_identity[1]}"
actual_nevra="$(rpm -qp --qf '%{NEVRA}' "$package_path")"
actual_source_rpm="$(rpm -qp --qf '%{SOURCERPM}' "$package_path")"
actual_license="$(rpm -qp --qf '%{LICENSE}' "$package_path")"

[[ "$actual_nevra" == "$expected_nevra" ]]
[[ "$actual_source_rpm" == "$expected_source_rpm" ]]
[[ "$actual_license" == "GPL-3.0-or-later" ]]

if [[ $# -eq 2 ]]; then
    source_package_path="$(realpath "$2")"
    if [[ ! -f "$source_package_path" ]]; then
        echo "Source RPM does not exist: $source_package_path" >&2
        exit 1
    fi
    expected_source_nvr="${expected_source_rpm%.src.rpm}"
    actual_source_nvr="$(rpm -qp --qf '%{NAME}-%{VERSION}-%{RELEASE}' \
        "$source_package_path")"
    actual_source_flag="$(rpm -qp --qf '%{SOURCEPACKAGE}' \
        "$source_package_path")"
    if [[ "$(basename "$source_package_path")" != "$expected_source_rpm" \
            || "$actual_source_nvr" != "$expected_source_nvr" \
            || "$actual_source_flag" != "1" ]]; then
        echo "Unexpected source RPM identity: $actual_source_nvr" >&2
        exit 1
    fi
fi

payload="$(rpm -qpl "$package_path")"
required_paths=(
    /usr/bin/proton-vpn-kde
    /usr/bin/proton-vpn-kde-agent
    /usr/bin/proton-vpn-kde-backend
    /usr/lib/systemd/user/proton-vpn-kde-agent.service
    /usr/lib/systemd/user/proton-vpn-kde-backend.service
    /usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/__main__.py
    /usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/dbus_contract.py
    /usr/share/applications/proton-vpn-kde.desktop
    /usr/share/dbus-1/interfaces/quest.entropy.PlasmaVPN.Backend1.xml
    /usr/share/dbus-1/interfaces/quest.entropy.PlasmaVPN.Agent1.xml
    /usr/share/dbus-1/interfaces/quest.entropy.PlasmaVPN.ControlCenter1.xml
    /usr/share/dbus-1/services/quest.entropy.PlasmaVPN.Backend.service
    /usr/share/icons/hicolor/scalable/apps/plasma-vpn.svg
    /usr/share/doc/proton-vpn-kde/docs/images/overview.png
    /usr/share/doc/proton-vpn-kde/SOURCE_COMMIT
)

for required_path in "${required_paths[@]}"; do
    if ! grep -Fxq "$required_path" <<<"$payload"; then
        echo "RPM payload is missing $required_path" >&2
        exit 1
    fi
done

requires="$(rpm -qp --requires "$package_path")"
if ! grep -Fxq 'python3-proton-vpn-api-core >= 5.5.6' <<<"$requires"; then
    echo "RPM does not retain the official Proton VPN API Core dependency" >&2
    exit 1
fi
if ! grep -Fxq \
        'proton-vpn-api-core-plasma-protun-secret >= 1' \
        <<<"$requires"; then
    echo "RPM does not require the Plasma Protun secret capability" >&2
    exit 1
fi
if ! grep -Fxq \
        'proton-keyring-secret-service-owner-pinned >= 1' \
        <<<"$requires"; then
    echo "RPM does not require the owner-pinned Secret Service capability" >&2
    exit 1
fi
if ! grep -Fxq '/usr/bin/ip' <<<"$requires"; then
    echo "RPM does not declare the reconnect route-probe dependency" >&2
    exit 1
fi

for forbidden_dependency in \
        gtk3 \
        gtk4 \
        gnome-keyring \
        python3-gobject \
        proton-vpn-gnome-desktop; do
    if grep -Eq "^${forbidden_dependency}([[:space:]]|$)" <<<"$requires"; then
        echo "RPM unexpectedly depends on $forbidden_dependency" >&2
        exit 1
    fi
done

ownership="$(rpm -qp --qf '[%{FILEUSERNAME}:%{FILEGROUPNAME} %{FILENAMES}\n]' \
    "$package_path")"
if grep -Evq '^root:root ' <<<"$ownership"; then
    echo "RPM contains a payload entry not owned by root:root" >&2
    grep -Ev '^root:root ' <<<"$ownership" >&2
    exit 1
fi

permissions="$(rpm -qp --qf '[%{FILEMODES:perms} %{FILENAMES}\n]' "$package_path")"
if awk '
    substr($1, 1, 1) != "l" &&
    (substr($1, 6, 1) == "w" || substr($1, 9, 1) == "w" || $1 ~ /[sS]/) {
        print
        unsafe = 1
    }
    END { exit unsafe }
' <<<"$permissions"; then
    :
else
    echo "RPM contains group/world-writable or set-ID payload entries" >&2
    exit 1
fi

extract_dir="$(mktemp -d)"
trap 'rm -rf "$extract_dir"' EXIT
(
    cd "$extract_dir"
    rpm2cpio "$package_path" | cpio -id --quiet \
        ./usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/_build_features.py \
        ./usr/share/doc/proton-vpn-kde/SOURCE_COMMIT
)
feature_file="$extract_dir/usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/_build_features.py"
grep -Fxq 'SUPPORT_REPORT_SUBMISSION_ENABLED = False' "$feature_file"
grep -Fxq 'CRASH_REPORT_SUBMISSION_ENABLED = False' "$feature_file"
grep -Fxq "$expected_commit" \
    "$extract_dir/usr/share/doc/proton-vpn-kde/SOURCE_COMMIT"

if [[ $# -eq 2 ]]; then
    source_extract_dir="$extract_dir/source-rpm"
    mkdir -p "$source_extract_dir"
    (
        cd "$source_extract_dir"
        rpm2cpio "$source_package_path" | cpio -id --quiet
    )
    source_archive="$source_extract_dir/proton-vpn-kde-$(rpmspec -q \
        --qf '%{VERSION}' "$spec_path").tar.gz"
    archive_commit="$(tar -xOzf "$source_archive" \
        "proton-vpn-kde-$(rpmspec -q --qf '%{VERSION}' "$spec_path")/.source-commit")"
    if [[ "$archive_commit" != "$expected_commit" ]]; then
        echo "Source RPM was not built from commit $expected_commit" >&2
        exit 1
    fi
fi

rpmkeys --checksig "$package_path"
if [[ $# -eq 2 ]]; then
    rpmkeys --checksig "$source_package_path"
fi
echo "RPM artifact checks passed: $package_path"
