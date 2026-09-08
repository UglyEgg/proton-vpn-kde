#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
baseline_commit="ec27fdce4967325d0f5e604c135caa23f5158474"

cd "$project_dir"

# A diff cannot seal untracked source. Require explicit staging before this
# gate is used locally; CI's clean checkout naturally satisfies the condition.
untracked_files="$(git ls-files --others --exclude-standard)"
if [[ -n "$untracked_files" ]]; then
    echo "Stage or remove untracked files before sealing the candidate:" >&2
    printf '  %s\n' "$untracked_files" >&2
    exit 1
fi

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
        echo "The recorded 0.13 $label delta changed:" >&2
        printf '  expected %s\n  actual   %s\n' "$expected" "$actual" >&2
        exit 1
    fi
}

violations=()
while IFS= read -r path; do
    [[ -n "$path" ]] || continue

    case "$path" in
        .github/workflows/ci.yml|CHANGELOG.md|README.md|docs/*|\
        packaging/fedora/README.md|packaging/fedora/api-core-overlay/README.md|\
        qml/*)
            ;;
        CMakeLists.txt|backend/pyproject.toml|\
        backend/proton_vpn_kde_backend/__init__.py|\
        backend/proton_vpn_kde_backend/__main__.py|\
        backend/proton_vpn_kde_backend/adapters.py|\
        backend/proton_vpn_kde_backend/account_transition.py|\
        backend/proton_vpn_kde_backend/async_utils.py|\
        backend/proton_vpn_kde_backend/client_authorization.py|\
        backend/proton_vpn_kde_backend/controller.py|\
        backend/proton_vpn_kde_backend/demo_adapter.py|\
        backend/proton_vpn_kde_backend/core_compatibility.py|\
        backend/proton_vpn_kde_backend/core_snapshot.py|\
        backend/proton_vpn_kde_backend/core_support.py|\
        backend/proton_vpn_kde_backend/dbus_contract.py|\
        backend/proton_vpn_kde_backend/dbus_service.py|\
        backend/proton_vpn_kde_backend/errors.py|\
        backend/proton_vpn_kde_backend/fido_interaction.py|\
        backend/proton_vpn_kde_backend/lifetime.py|\
        backend/proton_vpn_kde_backend/packet_capture.py|\
        backend/proton_vpn_kde_backend/reconnector.py|\
        backend/proton_vpn_kde_backend/refresher_events.py|\
        backend/proton_vpn_kde_backend/task_scope.py|\
        backend/tests/test_account_transition.py|\
        backend/tests/test_async_utils.py|\
        backend/tests/test_client_authorization.py|\
        backend/tests/test_controller.py|\
        backend/tests/test_core_lifecycle_conformance.py|\
        backend/tests/test_dbus_contract.py|\
        backend/tests/test_dbus_service.py|\
        backend/tests/test_lifetime.py|\
        backend/tests/test_main.py|\
        backend/tests/test_proton_core_adapter.py|\
        backend/tests/test_reconnector.py|\
        backend/tests/test_refresher_events.py|\
        backend/tests/test_task_scope.py|\
        data/proton-vpn-kde-backend.service.in|\
        data/dbus/quest.entropy.PlasmaVPN.Backend1.xml|\
        packaging/fedora/api-core-overlay/rebuild_overlay.py|\
        packaging/fedora/core-compatibility.json|\
        packaging/fedora/proton-vpn-kde.spec|\
        src/AgentVpnClient.cpp|src/AgentVpnClient.h|src/TrayIntegration.cpp|\
        src/BackendCallPolicy.h|src/BackgroundQuitCoordinator.cpp|\
        src/ConnectionAction.h|src/OperationCompletion.h|src/ShortcutIntegration.cpp|\
        src/VpnConnectionController.h|\
        src/DbusContract.h|\
        src/VpnController.cpp|src/VpnController.h|\
        src/VpnControllerActions.cpp|\
        src/VpnControllerLifecycle.cpp|src/VpnControllerLocations.cpp|\
        src/VpnControllerSettings.cpp|src/VpnControllerSnapshot.cpp|\
        src/main.cpp|\
        tests/AgentVpnClientTest.cpp|tests/GroupedNavigationTest.cpp|\
        tests/BackendCallPolicyTest.cpp|tests/BackgroundQuitCoordinatorTest.cpp|\
        tests/ConnectionActionTest.cpp|\
        tests/SignInPresentationTest.cpp)
            # Exact reviewed deltas are checked below.
            ;;
        scripts/auth-dbus-client.py|scripts/capture-qml-page.sh|\
        scripts/check-qml-ui-hygiene.sh|scripts/check-qml-visual-matrix.sh|\
        scripts/check-compatibility-metadata.py|\
        scripts/check-core-compatibility.sh|\
        scripts/check-core-contract.py|\
        scripts/check-release-metadata.sh|scripts/check-rpm-artifact.sh|\
        scripts/check-ux-mechanics-freeze.sh|\
        scripts/smoke-qml-diagnostics.sh|scripts/smoke-qml-layout-variants.sh|\
        scripts/smoke-settings-route.sh|scripts/smoke-staged-install.sh|\
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
    "eceb4a5872ad5d75efe4396f73043f5d1e189bd9e1448e081b46781b88832aea" \
    "build-system" CMakeLists.txt
assert_diff_hash \
    "2dc4dcb0671bfff07c756cdcd9ef0fb9af76e822e8177d3a4a1fd6d94bc95bee" \
    "backend version-only" \
    backend/pyproject.toml backend/proton_vpn_kde_backend/__init__.py
assert_diff_hash \
    "65c8e5ccbf8c3384cac60c28d9a19e036e86aef0f50a08a2ed15a7b2c1d0bbb2" \
    "backend ownership and recovery" \
    backend/proton_vpn_kde_backend backend/tests
assert_diff_hash \
    "fc1cefe07356bf5efb693f4369ea2361ab1e713f719f15941d5a99118a85060d" \
    "current Core runtime contract" \
    packaging/fedora/api-core-overlay/rebuild_overlay.py \
    packaging/fedora/core-compatibility.json \
    scripts/check-compatibility-metadata.py \
    scripts/check-core-compatibility.sh scripts/check-core-contract.py
assert_diff_hash \
    "3cf652676ae9f7eefc062c61a28c663942fbdf58d6a57707d8eb94c598021bff" \
    "finite process-stop packaging" \
    data/proton-vpn-kde-backend.service.in \
    scripts/check-rpm-artifact.sh scripts/smoke-staged-install.sh
assert_diff_hash \
    "f3dca36c733c8e515912de42c91c4c7c2faea9f1412ebcc5184b6c1bd8b19bff" \
    "D-Bus completion-classification contract" \
    data/dbus/quest.entropy.PlasmaVPN.Backend1.xml \
    backend/proton_vpn_kde_backend/dbus_contract.py src/DbusContract.h
assert_diff_hash \
    "d3fd94c768320df4542c3536194e79a81f2003a4fdf938152eb29ceac1be4eef" \
    "Fedora metadata" packaging/fedora/proton-vpn-kde.spec
assert_diff_hash \
    "52bd7d395a8e4023f9d21a6af85dee3d259ac134232dc4b6912766ed080873f6" \
    "CI" .github/workflows/ci.yml
assert_diff_hash \
    "e418c13ea27eb33037e3e5bb10e6b0065edd8b19a16d3fdf8226b0c673d60c64" \
    "frontend presentation contract" \
    src runner kcm tests
assert_diff_hash \
    "a2319e5d44bb424040119977ec9ddaa521b30ea56b7fd469fc984d4a47f0aa59" \
    "QML presentation" qml

echo "0.13 change boundary matches baseline $baseline_commit plus recorded candidate deltas (not review approval)"
