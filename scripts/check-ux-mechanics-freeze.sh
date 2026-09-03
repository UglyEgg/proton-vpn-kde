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
        backend/proton_vpn_kde_backend/__main__.py|\
        backend/proton_vpn_kde_backend/adapters.py|\
        backend/proton_vpn_kde_backend/async_utils.py|\
        backend/proton_vpn_kde_backend/client_authorization.py|\
        backend/proton_vpn_kde_backend/controller.py|\
        backend/proton_vpn_kde_backend/core_compatibility.py|\
        backend/proton_vpn_kde_backend/core_snapshot.py|\
        backend/proton_vpn_kde_backend/core_support.py|\
        backend/proton_vpn_kde_backend/dbus_contract.py|\
        backend/proton_vpn_kde_backend/dbus_service.py|\
        backend/proton_vpn_kde_backend/errors.py|\
        backend/proton_vpn_kde_backend/fido_interaction.py|\
        backend/proton_vpn_kde_backend/lifetime.py|\
        backend/proton_vpn_kde_backend/reconnector.py|\
        backend/tests/test_async_utils.py|\
        backend/tests/test_client_authorization.py|\
        backend/tests/test_controller.py|\
        backend/tests/test_dbus_service.py|\
        backend/tests/test_lifetime.py|\
        backend/tests/test_main.py|\
        backend/tests/test_proton_core_adapter.py|\
        backend/tests/test_reconnector.py|\
        data/dbus/quest.entropy.PlasmaVPN.Backend1.xml|\
        packaging/fedora/proton-vpn-kde.spec|\
        src/AgentVpnClient.cpp|src/AgentVpnClient.h|src/TrayIntegration.cpp|\
        src/DbusContract.h|\
        src/VpnController.cpp|src/VpnController.h|\
        src/VpnControllerActions.cpp|\
        src/VpnControllerLifecycle.cpp|src/VpnControllerLocations.cpp|\
        src/VpnControllerSettings.cpp|src/VpnControllerSnapshot.cpp|\
        src/main.cpp|\
        tests/AgentVpnClientTest.cpp|tests/GroupedNavigationTest.cpp|\
        tests/SignInPresentationTest.cpp)
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
    echo "Files outside the reviewed 0.13 change boundary changed:" >&2
    printf '  %s\n' "${violations[@]}" >&2
    echo "Move behavioral work to a separate release or deliberately rebaseline after review." >&2
    exit 1
fi

assert_diff_hash \
    "89be18e1e42ead89a3c3a7c0c8f413e5610f7ae3e7d88d08dba0fac7d7532bdf" \
    "build-system" CMakeLists.txt
assert_diff_hash \
    "2dc4dcb0671bfff07c756cdcd9ef0fb9af76e822e8177d3a4a1fd6d94bc95bee" \
    "backend version-only" \
    backend/pyproject.toml backend/proton_vpn_kde_backend/__init__.py
assert_diff_hash \
    "11c609daa311358368202e022ae9106e9a1bad858484d00197597389017a86b1" \
    "backend reviewed behavior exceptions" \
    backend/proton_vpn_kde_backend/__main__.py \
    backend/proton_vpn_kde_backend/adapters.py \
    backend/proton_vpn_kde_backend/async_utils.py \
    backend/proton_vpn_kde_backend/client_authorization.py \
    backend/proton_vpn_kde_backend/controller.py \
    backend/proton_vpn_kde_backend/core_compatibility.py \
    backend/proton_vpn_kde_backend/core_snapshot.py \
    backend/proton_vpn_kde_backend/core_support.py \
    backend/proton_vpn_kde_backend/dbus_service.py \
    backend/proton_vpn_kde_backend/errors.py \
    backend/proton_vpn_kde_backend/fido_interaction.py \
    backend/proton_vpn_kde_backend/lifetime.py \
    backend/proton_vpn_kde_backend/reconnector.py \
    backend/tests/test_async_utils.py \
    backend/tests/test_client_authorization.py backend/tests/test_controller.py \
    backend/tests/test_dbus_service.py \
    backend/tests/test_lifetime.py \
    backend/tests/test_main.py \
    backend/tests/test_proton_core_adapter.py backend/tests/test_reconnector.py
assert_diff_hash \
    "f3dca36c733c8e515912de42c91c4c7c2faea9f1412ebcc5184b6c1bd8b19bff" \
    "D-Bus completion-classification contract" \
    data/dbus/quest.entropy.PlasmaVPN.Backend1.xml \
    backend/proton_vpn_kde_backend/dbus_contract.py src/DbusContract.h
assert_diff_hash \
    "ffa9da88a9be1301863d18e68e0c433f3233f9daa274bd124681f4297d938584" \
    "Fedora metadata" packaging/fedora/proton-vpn-kde.spec
assert_diff_hash \
    "43a01bcdc69688eef93952e1a50e124d86e28b344952d5495b9b2e22ea94d54d" \
    "CI" .github/workflows/ci.yml
assert_diff_hash \
    "d86348e478192506a61271ad12fb38c0b4037cc91315787cc185c3cbee10888c" \
    "frontend presentation contract" \
    src/AgentVpnClient.cpp src/AgentVpnClient.h src/TrayIntegration.cpp \
    src/VpnController.h src/VpnController.cpp src/VpnControllerActions.cpp \
    src/VpnControllerLifecycle.cpp src/VpnControllerLocations.cpp \
    src/VpnControllerSettings.cpp src/VpnControllerSnapshot.cpp src/main.cpp \
    tests/AgentVpnClientTest.cpp tests/GroupedNavigationTest.cpp \
    tests/SignInPresentationTest.cpp
assert_diff_hash \
    "6c44508e3caa0e457e600993d7dbe09d71167186de677fb8c410feee17f8aef9" \
    "QML presentation" qml

echo "0.13 change boundary matches accepted baseline $baseline_commit plus exact reviewed deltas"
