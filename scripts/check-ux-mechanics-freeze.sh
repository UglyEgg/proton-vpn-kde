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
        CMakeLists.txt|.github/workflows/rpm.yml|kcm/CMakeLists.txt|backend/pyproject.toml|\
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
        backend/tests/test_search_projection.py|\
        backend/tests/test_task_scope.py|\
        data/proton-vpn-kde-backend.service.in|\
        data/dbus/quest.entropy.PlasmaVPN.Backend1.xml|\
        packaging/fedora/api-core-overlay/rebuild_overlay.py|\
        packaging/fedora/core-compatibility.json|\
        packaging/fedora/proton-vpn-kde.spec|\
        src/AgentVpnClient.cpp|src/AgentVpnClient.h|src/TrayIntegration.cpp|\
        src/BackendIdentity.cpp|src/BackendIdentity.h|\
        src/NotificationIntegration.cpp|src/NotificationIntegration.h|\
        src/AppSettings.cpp|src/AppSettings.h|kcm/ui/main.qml|\
        src/AgentControl.cpp|src/AgentControl.h|\
        src/AutostartSettings.cpp|src/AutostartSettings.h|\
        src/BackendCallPolicy.h|src/BackgroundQuitCoordinator.cpp|\
        src/ConnectionAction.h|src/OperationCompletion.h|src/ShortcutIntegration.cpp|\
        src/SettingsRequestState.h|src/VpnSettingsModel.cpp|\
        src/SplitTunnelingModel.cpp|src/CustomDnsModel.cpp|\
        src/VpnConnectionController.h|\
        src/DbusContract.h|\
        src/VpnController.cpp|src/VpnController.h|\
        src/VpnControllerActions.cpp|\
        src/VpnControllerLifecycle.cpp|src/VpnControllerLocations.cpp|\
        src/VpnControllerSettings.cpp|src/VpnControllerSnapshot.cpp|\
        src/main.cpp|src/agent_main.cpp|src/NativeStartup.cpp|src/NativeStartup.h|\
        tests/NativeStartupProbe.cpp|\
        tests/AgentVpnClientTest.cpp|tests/GroupedNavigationTest.cpp|\
        tests/BackendIdentityTest.cpp|tests/NotificationIntegrationTest.cpp|\
        tests/AppSettingsTest.cpp|\
        tests/ControlCenterControlTest.cpp|\
        tests/ProtonVpnKcmTest.cpp|\
        tests/PresentationLayoutTest.cpp|\
        tests/BackendCallPolicyTest.cpp|tests/BackgroundQuitCoordinatorTest.cpp|\
        tests/ConnectionActionTest.cpp|\
        tests/VpnSettingsModelTest.cpp|tests/SplitTunnelingModelTest.cpp|\
        tests/CustomDnsModelTest.cpp|\
        tests/SignInPresentationTest.cpp)
            # Exact candidate deltas are checked below; this is not approval.
            ;;
        data/proton-vpn-kde.desktop.in|\
        scripts/auth-dbus-client.py|scripts/capture-qml-page.sh|\
        scripts/check-qml-ui-hygiene.sh|scripts/check-qml-visual-matrix.sh|\
        scripts/check-compatibility-metadata.py|\
        scripts/check-core-compatibility.sh|\
        scripts/check-core-contract.py|\
        scripts/check-native-startup.py|\
        scripts/smoke-control-center-activation.sh|\
        scripts/check-release-metadata.sh|scripts/check-rpm-artifact.sh|\
        scripts/check-ux-mechanics-freeze.sh|\
        scripts/benchmark-search.py|\
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
    "e49b26e7ad802eaf97a718469b3a6a83c6ee586f180a7f04dc1108dcb82014fb" \
    "build-system" CMakeLists.txt
assert_diff_hash \
    "2dc4dcb0671bfff07c756cdcd9ef0fb9af76e822e8177d3a4a1fd6d94bc95bee" \
    "backend version-only" \
    backend/pyproject.toml backend/proton_vpn_kde_backend/__init__.py
assert_diff_hash \
    "9eed191e8d44c37b4210c2501f8805ca297087db4325385fec0d9bdaa8bc201e" \
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
    "bc8919bb31d33cf967c48472656f217a0d7de017f4fb0c20ed1ff0aeb2095c97" \
    "finite process-stop packaging" \
    data/proton-vpn-kde-backend.service.in \
    scripts/check-rpm-artifact.sh scripts/smoke-staged-install.sh
assert_diff_hash \
    "f3dca36c733c8e515912de42c91c4c7c2faea9f1412ebcc5184b6c1bd8b19bff" \
    "D-Bus completion-classification contract" \
    data/dbus/quest.entropy.PlasmaVPN.Backend1.xml \
    backend/proton_vpn_kde_backend/dbus_contract.py src/DbusContract.h
assert_diff_hash \
    "80e9a8dbfd7e324eef93ca1882e95d25596c9488aa381f3388b3b11186e65099" \
    "Fedora metadata" packaging/fedora/proton-vpn-kde.spec
assert_diff_hash \
    "e97f135d1d57cac0e1970bf0b40b2c142268fe64f942fabdff829aa7d5a9c2af" \
    "RPM test dependencies" .github/workflows/rpm.yml
assert_diff_hash \
    "52bd7d395a8e4023f9d21a6af85dee3d259ac134232dc4b6912766ed080873f6" \
    "CI" .github/workflows/ci.yml
assert_diff_hash \
    "c7fbb9402a6fb490b8ab4e3adadd973de31683366a55292740b44d9b7cd3cdc3" \
    "frontend presentation contract" \
    src runner kcm tests
assert_diff_hash \
    "30d98e60634fe2d169a8f37f4d787e3cec2072b52d887479e1b29117c7f8f8ca" \
    "QML presentation" qml

# RC1–RC6: explicitly authorized startup/persistence/presentation corrections
# and offline measurement fixtures. These seals still do not grant approval.
# START-01 additionally admits direct native startup normalization and its
# kernel-environment regression probe; backend authorization stays unchanged.
assert_diff_hash \
    "0b9bc3a05869509205d9dbfe761bf4e9eb9ccd1a423c07d9d41603e353c0cc12" \
    "native startup regression" scripts/check-native-startup.py \
    scripts/smoke-control-center-activation.sh

assert_diff_hash \
    "2307b7ff215dd918276e71decb16703f3120702aee1ff6a61fa46c993ea9a3e6" \
    "offline search measurement" scripts/benchmark-search.py

assert_diff_hash \
    "5bfd83782480c0976b1b3cfe6ea8dd84d099329137b1b0f46c80acb4dde2f48a" \
    "unambiguous desktop icon" data/proton-vpn-kde.desktop.in

echo "0.13 change boundary matches baseline $baseline_commit plus recorded candidate deltas (not review approval)"
