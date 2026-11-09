#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

# Replay crash aftermath only in disposable user/network namespaces. Never
# substitute sudo, the host network namespace, or a live NetworkManager client.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 || $EUID == 0 ]]; then
    echo "Usage (unprivileged): $0 CORE_SITE_PACKAGES [SSO_SITE_PACKAGES]" >&2
    exit 2
fi
extra_environment=()
if [[ $# == 2 ]]; then
    sso_fixture="$(realpath -e -- "$2")"
    if [[ ! -f "$sso_fixture/proton/sso/sso.py" ]]; then
        echo "A hash-checked extracted SSO fixture is required." >&2
        exit 2
    fi
    extra_environment+=("PLASMA_VPN_TEST_SSO_SITE_PACKAGES=$sso_fixture")
fi

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
core_fixture="$(realpath -e -- "$1")"
if [[ ! -f "$core_fixture/proton/vpn/core/vpnconnector.py" ]]; then
    echo "A hash-checked extracted Core fixture is required." >&2
    exit 2
fi
parent_net_namespace="$(readlink /proc/self/ns/net)"
parent_user_namespace="$(readlink /proc/self/ns/user)"

cd "$project_dir"
exec timeout --kill-after=5s 30s \
    unshare --user --map-current-user --keep-caps --net -- \
    env PYTHONPATH="$project_dir/backend:$project_dir/backend/tests" \
        "${extra_environment[@]}" \
        PLASMA_VPN_TEST_CORE_SITE_PACKAGES="$core_fixture" \
        PLASMA_VPN_TEST_NAMESPACE_PARENT="$parent_net_namespace" \
        PLASMA_VPN_TEST_USER_NAMESPACE_PARENT="$parent_user_namespace" \
        python3 -m unittest test_core_lifecycle_conformance -v
