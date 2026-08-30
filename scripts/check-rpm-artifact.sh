#!/usr/bin/bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "usage: $0 /path/to/proton-vpn-kde.rpm" >&2
    exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
package_path="$(realpath "$1")"

if [[ ! -f "$package_path" ]]; then
    echo "RPM does not exist: $package_path" >&2
    exit 1
fi

expected_version="$(sed -n 's/^Version:[[:space:]]*//p' \
    "$project_dir/packaging/fedora/proton-vpn-kde.spec" | head -n 1)"
actual_name="$(rpm -qp --qf '%{NAME}' "$package_path")"
actual_version="$(rpm -qp --qf '%{VERSION}' "$package_path")"
actual_license="$(rpm -qp --qf '%{LICENSE}' "$package_path")"

[[ "$actual_name" == "proton-vpn-kde" ]]
[[ "$actual_version" == "$expected_version" ]]
[[ "$actual_license" == "GPL-3.0-or-later" ]]

payload="$(rpm -qpl "$package_path")"
required_paths=(
    /usr/bin/proton-vpn-kde
    /usr/bin/proton-vpn-kde-agent
    /usr/bin/proton-vpn-kde-backend
    /usr/lib/systemd/user/proton-vpn-kde-agent.service
    /usr/lib/systemd/user/proton-vpn-kde-backend.service
    /usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/__main__.py
    /usr/share/applications/proton-vpn-kde.desktop
    /usr/share/dbus-1/services/quest.entropy.PlasmaVPN.Backend.service
    /usr/share/icons/hicolor/scalable/apps/plasma-vpn.svg
    /usr/share/doc/proton-vpn-kde/docs/images/overview.png
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
        ./usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/_build_features.py
)
feature_file="$extract_dir/usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/_build_features.py"
grep -Fxq 'SUPPORT_REPORT_SUBMISSION_ENABLED = False' "$feature_file"
grep -Fxq 'CRASH_REPORT_SUBMISSION_ENABLED = False' "$feature_file"

rpmkeys --checksig "$package_path"
echo "RPM artifact checks passed: $package_path"
