#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
    echo "usage: $0 client.deb keyring.deb api-core.deb [vendor-api-core.deb]" >&2
    exit 2
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
client_deb="$(realpath "$1")"
keyring_deb="$(realpath "$2")"
api_core_deb="$(realpath "$3")"
vendor_api_core_deb="${4:-}"

for package_path in "$client_deb" "$keyring_deb" "$api_core_deb"; do
    if [[ ! -f "$package_path" ]]; then
        echo "Debian package does not exist: $package_path" >&2
        exit 1
    fi
done

expected_version="$(sed -n \
    's/^project(proton-vpn-kde VERSION \([^ ]*\) LANGUAGES CXX)$/\1/p' \
    "$project_dir/CMakeLists.txt")"
client_version="$(dpkg-deb --field "$client_deb" Version)"
[[ "${client_version%%-*}" == "$expected_version" ]]
[[ "$(dpkg-deb --field "$client_deb" Package)" == proton-vpn-kde ]]
[[ "$(dpkg-deb --field "$client_deb" Architecture)" == amd64 ]]
[[ "$(dpkg-deb --field "$keyring_deb" Package)" == python3-proton-keyring-linux ]]
[[ "$(dpkg-deb --field "$keyring_deb" Architecture)" == all ]]

client_depends="$(dpkg-deb --field "$client_deb" Depends)"
required_dependencies=(
    plasma-integration
    proton-vpn-daemon
    proton-keyring-secret-service-provider-agnostic
    proton-keyring-secret-service-owner-pinned
    proton-vpn-api-core-plasma-protun-secret
    python3-proton-vpn-api-core
    qml6-module-org-kde-kirigami
    qt6-svg-plugins
    systemsettings
)
for dependency in "${required_dependencies[@]}"; do
    if ! grep -Eq "(^|, )${dependency}([[:space:](,]|$)" <<<"$client_depends"; then
        echo "Client package is missing dependency: $dependency" >&2
        exit 1
    fi
done

for forbidden_dependency in \
        gnome-keyring \
        proton-vpn-gnome-desktop \
        proton-vpn-gtk-app; do
    if grep -Eq "(^|, )${forbidden_dependency}([[:space:](,]|$)" \
            <<<"$client_depends"; then
        echo "Client package directly depends on $forbidden_dependency" >&2
        exit 1
    fi
done

keyring_depends="$(dpkg-deb --field "$keyring_deb" Depends)"
if grep -Eq '(^|, )gnome-keyring([[:space:](,]|$)' <<<"$keyring_depends"; then
    echo "Provider-neutral keyring package depends on GNOME Keyring" >&2
    exit 1
fi
keyring_provides="$(dpkg-deb --field "$keyring_deb" Provides)"
grep -Eq '(^|, )proton-keyring-secret-service-provider-agnostic *\(= *1\)(,|$)' \
    <<<"$keyring_provides"
grep -Eq '(^|, )proton-keyring-secret-service-owner-pinned *\(= *1\)(,|$)' \
    <<<"$keyring_provides"
keyring_payload="$(dpkg-deb --contents "$keyring_deb")"
if awk '$NF ~ /\/(\.coverage|htmlcov)(\/|$)/ { print; found = 1 }
        END { exit !found }' <<<"$keyring_payload"; then
    echo "Keyring package contains test coverage artifacts" >&2
    exit 1
fi

client_payload="$(dpkg-deb --contents "$client_deb")"
required_payload_patterns=(
    './usr/bin/proton-vpn-kde'
    './usr/bin/proton-vpn-kde-agent'
    './usr/bin/proton-vpn-kde-backend'
    './usr/lib/systemd/user/proton-vpn-kde-agent.service'
    './usr/lib/systemd/user/proton-vpn-kde-backend.service'
    './usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/__main__.py'
    './usr/share/applications/proton-vpn-kde.desktop'
    './usr/share/dbus-1/interfaces/quest.entropy.PlasmaVPN.Backend1.xml'
    './usr/share/dbus-1/services/quest.entropy.PlasmaVPN.Backend.service'
    './usr/share/icons/hicolor/scalable/apps/plasma-vpn.svg'
)
for payload_path in "${required_payload_patterns[@]}"; do
    if ! awk -v required="$payload_path" '$NF == required { found = 1 } END { exit !found }' \
            <<<"$client_payload"; then
        echo "Client package payload is missing $payload_path" >&2
        exit 1
    fi
done

for plugin_suffix in \
        '/kf6/krunner/proton-vpn-kde-runner.so' \
        '/plasma/kcms/systemsettings/kcm_proton_vpn_kde.so'; do
    if ! awk -v suffix="$plugin_suffix" \
            'substr($NF, length($NF) - length(suffix) + 1) == suffix { found = 1 }
             END { exit !found }' <<<"$client_payload"; then
        echo "Client package payload is missing plugin $plugin_suffix" >&2
        exit 1
    fi
done

if awk '$2 != "root/root" { print; unsafe = 1 } END { exit !unsafe }' \
        <<<"$client_payload"; then
    echo "Client package contains a payload entry not owned by root:root" >&2
    exit 1
fi
if awk '
    substr($1, 1, 1) != "l" &&
    (substr($1, 6, 1) == "w" || substr($1, 9, 1) == "w" || $1 ~ /[sS]/) {
        print
        unsafe = 1
    }
    END { exit !unsafe }
' <<<"$client_payload"; then
    echo "Client package contains writable or set-ID payload entries" >&2
    exit 1
fi

extract_dir="$(mktemp -d /tmp/proton-vpn-kde-deb-check.XXXXXX)"
cleanup() {
    rm -rf -- "$extract_dir"
}
trap cleanup EXIT

manifest="$project_dir/packaging/debian/api-core-overlay/overlay-manifest.json"
if [[ -z "$vendor_api_core_deb" ]]; then
    vendor_filename="$(python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1]))["vendor"]["filename"])' \
        "$manifest")"
    vendor_url="$(python3 -c \
        'import json,sys; print(json.load(open(sys.argv[1]))["vendor"]["url"])' \
        "$manifest")"
    vendor_api_core_deb="$extract_dir/$vendor_filename"
    curl --fail --location --silent --show-error \
        --output "$vendor_api_core_deb" "$vendor_url"
else
    vendor_api_core_deb="$(realpath "$vendor_api_core_deb")"
fi
python3 "$project_dir/packaging/debian/api-core-overlay/rebuild_overlay.py" verify-deb \
    --manifest "$manifest" \
    --vendor-deb "$vendor_api_core_deb" \
    --overlay-deb "$api_core_deb"

api_core_root="$extract_dir/api-core"
dpkg-deb --extract "$api_core_deb" "$api_core_root"
python3 "$project_dir/packaging/fedora/api-core-overlay/rebuild_overlay.py" verify-behavior \
    --root "$api_core_root" \
    --site-packages usr/lib/python3/dist-packages

client_root="$extract_dir/client"
dpkg-deb --extract "$client_deb" "$client_root"
[[ $(stat -c '%a' \
    "$client_root/usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/__main__.py") \
    == 644 ]]
feature_file="$client_root/usr/libexec/proton-vpn-kde/proton_vpn_kde_backend/_build_features.py"
grep -Fqx 'SUPPORT_REPORT_SUBMISSION_ENABLED = False' "$feature_file"
grep -Fqx 'CRASH_REPORT_SUBMISSION_ENABLED = False' "$feature_file"

echo "Debian artifact checks passed"
