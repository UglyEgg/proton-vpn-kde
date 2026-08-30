#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"

ruff check backend packaging/fedora/api-core-overlay scripts
shellcheck scripts/*.sh packaging/fedora/api-core-overlay/*.sh
desktop-file-validate data/proton-vpn-kde.desktop
xmllint --noout data/plasma-vpn.svg \
    data/plasma-vpn-light.svg \
    data/plasma-vpn-dark.svg
python3 -m json.tool kcm/kcm_proton_vpn_kde.json >/dev/null
python3 scripts/check-documentation-links.py
