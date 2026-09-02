#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
baseline_commit="ec27fdce4967325d0f5e604c135caa23f5158474"

cd "$project_dir"

if ! git cat-file -e "${baseline_commit}^{commit}" 2>/dev/null; then
    echo "The 0.13 UX mechanics baseline is unavailable: $baseline_commit" >&2
    echo "Fetch complete Git history before running this release gate." >&2
    exit 1
fi

changed_files="$({
    git diff --no-renames --name-only --diff-filter=ACDMRTUXB \
        "$baseline_commit" HEAD
    git diff --no-renames --name-only --diff-filter=ACDMRTUXB
    git diff --cached --no-renames --name-only --diff-filter=ACDMRTUXB
} | LC_ALL=C sort -u)"

violations=()
while IFS= read -r path; do
    [[ -n "$path" ]] || continue

    case "$path" in
        backend/pyproject.toml|backend/proton_vpn_kde_backend/__init__.py)
            # These two files carry synchronized release-version metadata only.
            ;;
        backend/*|src/*|runner/*|tests/*)
            violations+=("$path")
            ;;
        data/plasma-vpn.svg|data/plasma-vpn-light.svg|data/plasma-vpn-dark.svg)
            ;;
        data/proton-vpn-kde.desktop.in|data/proton-vpn-kde.notifyrc)
            ;;
        data/*)
            violations+=("$path")
            ;;
        kcm/ui/*|kcm/kcm_proton_vpn_kde.json)
            ;;
        kcm/*)
            violations+=("$path")
            ;;
        packaging/fedora/proton-vpn-kde.spec|packaging/fedora/README.md)
            ;;
        packaging/fedora/*)
            violations+=("$path")
            ;;
    esac
done <<<"$changed_files"

if ((${#violations[@]} > 0)); then
    echo "0.13 is presentation-only, but mechanics-owned files changed:" >&2
    printf '  %s\n' "${violations[@]}" >&2
    echo "Move behavioral work to a separate release or deliberately rebaseline after review." >&2
    exit 1
fi

echo "0.13 UX mechanics freeze matches accepted baseline $baseline_commit"
