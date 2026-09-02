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
    git \
        -c color.ui=false \
        -c core.abbrev=40 \
        -c diff.algorithm=myers \
        -c diff.context=3 \
        -c diff.indentHeuristic=false \
        -c diff.mnemonicPrefix=false \
        -c diff.noprefix=false \
        -c diff.renames=false \
        diff --no-ext-diff --no-textconv --no-color --no-renames --binary \
        --full-index --abbrev=40 --diff-algorithm=myers \
        --no-indent-heuristic --unified=3 --src-prefix=a/ --dst-prefix=b/ \
        --output-indicator-new=+ --output-indicator-old=- \
        --output-indicator-context=' ' -O/dev/null \
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
        src/VpnController.cpp|src/VpnController.h|\
        src/VpnControllerActions.cpp|\
        src/VpnControllerLifecycle.cpp|src/VpnControllerLocations.cpp|\
        src/VpnControllerSnapshot.cpp|\
        src/main.cpp|\
        tests/GroupedNavigationTest.cpp|tests/SignInPresentationTest.cpp)
            # Exact reviewed deltas are checked below.
            ;;
        scripts/auth-dbus-client.py|scripts/capture-qml-page.sh|\
        scripts/check-qml-ui-hygiene.sh|scripts/check-qml-visual-matrix.sh|\
        scripts/check-release-metadata.sh|scripts/check-ux-mechanics-freeze.sh|\
        scripts/smoke-qml-diagnostics.sh|scripts/smoke-qml-layout-variants.sh|\
        scripts/smoke-settings-route.sh|\
        scripts/test-ux-mechanics-freeze-negative.sh)
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
    "eb07ba5f573264d3a6a1add2d65cabedf45b1dcba4bed912dc9f9017d06442de" \
    "build-system" CMakeLists.txt
assert_diff_hash \
    "2dc4dcb0671bfff07c756cdcd9ef0fb9af76e822e8177d3a4a1fd6d94bc95bee" \
    "backend version-only" \
    backend/pyproject.toml backend/proton_vpn_kde_backend/__init__.py
assert_diff_hash \
    "ffa9da88a9be1301863d18e68e0c433f3233f9daa274bd124681f4297d938584" \
    "Fedora metadata" packaging/fedora/proton-vpn-kde.spec
assert_diff_hash \
    "43a01bcdc69688eef93952e1a50e124d86e28b344952d5495b9b2e22ea94d54d" \
    "CI" .github/workflows/ci.yml
assert_diff_hash \
    "92c8153515a87d3f59dc54dc48a931dbf30547d879d8d3ac8b50495d649ebc89" \
    "frontend presentation contract" \
    src/VpnController.h src/VpnController.cpp src/VpnControllerActions.cpp \
    src/VpnControllerLifecycle.cpp src/VpnControllerLocations.cpp \
    src/VpnControllerSnapshot.cpp src/main.cpp \
    tests/GroupedNavigationTest.cpp tests/SignInPresentationTest.cpp
assert_diff_hash \
    "57b39bd434d70f1f07cf950e048cb1720789da3aabda632086a3cfd8b99e2832" \
    "QML presentation" qml

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
