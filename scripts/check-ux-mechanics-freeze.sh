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

diff_hash() {
    git diff --no-ext-diff --no-renames --binary \
        "$baseline_commit" -- "$@" | sha256sum | cut -d' ' -f1
}

assert_diff_hash() {
    local expected="$1"
    local label="$2"
    shift 2
    local actual
    actual="$(diff_hash "$@")"
    if [[ "$actual" != "$expected" ]]; then
        echo "The reviewed 0.13 $label delta changed:" >&2
        printf '  expected %s\n  actual   %s\n' "$expected" "$actual" >&2
        exit 1
    fi
}

violations=()
while IFS= read -r path; do
    [[ -n "$path" ]] || continue

    case "$path" in
        .github/workflows/ci.yml|CHANGELOG.md|README.md|docs/*|qml/*)
            ;;
        CMakeLists.txt|backend/pyproject.toml|\
        backend/proton_vpn_kde_backend/__init__.py|\
        packaging/fedora/proton-vpn-kde.spec|\
        src/VpnController.cpp|src/VpnController.h|src/main.cpp|\
        tests/GroupedNavigationTest.cpp)
            # Exact reviewed deltas are checked below.
            ;;
        scripts/auth-dbus-client.py|scripts/capture-qml-page.sh|\
        scripts/check-qml-ui-hygiene.sh|scripts/check-qml-visual-matrix.sh|\
        scripts/check-release-metadata.sh|scripts/check-ux-mechanics-freeze.sh|\
        scripts/smoke-qml-diagnostics.sh|scripts/smoke-qml-layout-variants.sh|\
        scripts/smoke-settings-route.sh)
            # Presentation verification and its hermetic test drivers.
            ;;
        *)
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

assert_diff_hash \
    "9ce52e483f5b8828835ffe608ecd092f7310445480bdbec6f18ac4c651e40ccb" \
    "build-system" CMakeLists.txt
assert_diff_hash \
    "c501dd51a22e62bb85c587e880c6c1870db99ddc7864adb1ef8d90d168f5535f" \
    "backend version-only" \
    backend/pyproject.toml backend/proton_vpn_kde_backend/__init__.py
assert_diff_hash \
    "8c1aec6d9058e092862d24db352f8bae2c2e398d2c70f7fd789dea7916847063" \
    "Fedora metadata" packaging/fedora/proton-vpn-kde.spec
assert_diff_hash \
    "5fa967280d5f55544a7e7c6dc080c31ed4ba6c2e06999b46bdb9284efb330567" \
    "CI" .github/workflows/ci.yml
assert_diff_hash \
    "236ed49686386f1439d8e871ed712ca3e3d3f5bceeba62b106148e4676d7ce01" \
    "presentation recovery and measurement contract" \
    src/VpnController.h src/VpnController.cpp src/main.cpp \
    tests/GroupedNavigationTest.cpp

qml_operation_hash="$(
    rg -o --no-filename \
        'vpnController\.[A-Za-z_][A-Za-z0-9_]*[[:space:]]*\(' qml \
        | sed -E 's/[[:space:]]*\($//' \
        | LC_ALL=C sort \
        | sha256sum \
        | cut -d' ' -f1
)"
expected_qml_operation_hash=\
"8edff7a70970ae44bf3faa2af0da61126849266b042087050f723f3e4e8658ca"
if [[ "$qml_operation_hash" != "$expected_qml_operation_hash" ]]; then
    echo "The reviewed 0.13 QML controller-operation inventory changed:" >&2
    printf '  expected %s\n  actual   %s\n' \
        "$expected_qml_operation_hash" "$qml_operation_hash" >&2
    exit 1
fi

echo "0.13 UX mechanics freeze matches accepted baseline $baseline_commit"
