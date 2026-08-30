#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

python3 scripts/check-spdx-headers.py
python3 scripts/generate-dbus-contracts.py --check
python3 scripts/check-compatibility-metadata.py
ruff check backend packaging/fedora/api-core-overlay scripts
shellcheck \
    scripts/*.sh \
    packaging/fedora/api-core-overlay/*.sh \
    packaging/fedora/keyring-overlay/*.sh
desktop-file-validate data/proton-vpn-kde.desktop
xmllint --noout data/plasma-vpn.svg \
    data/plasma-vpn-light.svg \
    data/plasma-vpn-dark.svg
python3 -m json.tool kcm/kcm_proton_vpn_kde.json >/dev/null
python3 -m json.tool \
    packaging/fedora/keyring-overlay/overlay-manifest.json >/dev/null
python3 -m json.tool packaging/fedora/core-compatibility.json >/dev/null
if rg --pcre2 -n \
        'uses:\s+[^./\s][^@\s]+@(?![0-9a-f]{40}(?:\s|#|$))' \
        .github/workflows; then
    echo "GitHub Actions must be pinned to complete commit hashes" >&2
    exit 1
fi
python3 scripts/check-documentation-links.py
