#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

python3 scripts/check-spdx-headers.py
python3 scripts/check-patch-whitespace.py
python3 scripts/generate-dbus-contracts.py --check
python3 scripts/generate-snapshot-contract.py --check
python3 scripts/check-compatibility-metadata.py
ruff check \
    backend \
    packaging/debian/api-core-overlay \
    packaging/fedora/api-core-overlay \
    scripts
shellcheck \
    scripts/*.sh \
    packaging/debian/*.sh \
    packaging/debian/api-core-overlay/*.sh \
    packaging/debian/keyring-overlay/*.sh \
    packaging/fedora/api-core-overlay/*.sh \
    packaging/fedora/keyring-overlay/*.sh \
    debian/tests/installed-layout
desktop_validation_file="$(mktemp --suffix=.desktop)"
trap 'rm -f -- "$desktop_validation_file"' EXIT
sed 's|@CMAKE_INSTALL_FULL_BINDIR@|/usr/bin|g' \
    data/proton-vpn-kde.desktop.in >"$desktop_validation_file"
desktop-file-validate "$desktop_validation_file"
xmllint --noout data/plasma-vpn.svg \
    data/plasma-vpn-light.svg \
    data/plasma-vpn-dark.svg
python3 -m json.tool kcm/kcm_proton_vpn_kde.json >/dev/null
python3 -m json.tool \
    packaging/fedora/keyring-overlay/overlay-manifest.json >/dev/null
python3 -m json.tool \
    packaging/debian/api-core-overlay/overlay-manifest.json >/dev/null
python3 -m json.tool packaging/fedora/core-compatibility.json >/dev/null
python3 -m json.tool data/snapshot-schema-v1.json >/dev/null
python3 -m json.tool translations/provenance.json >/dev/null
python3 scripts/import-proton-translations.py --check-outputs
scripts/check-source-archive-reproducibility.sh
if rg --pcre2 -n \
        'uses:\s+[^./\s][^@\s]+@(?![0-9a-f]{40}(?:\s|#|$))' \
        .github/workflows; then
    echo "GitHub Actions must be pinned to complete commit hashes" >&2
    exit 1
fi
python3 scripts/check-documentation-links.py
