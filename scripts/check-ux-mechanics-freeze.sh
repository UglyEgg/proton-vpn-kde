#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
baseline_commit="f0f6960bf7b5dcd176ef8e804d4d49a059e37a5f"

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
    echo "The published 0.13.0 baseline is unavailable: $baseline_commit" >&2
    echo "Fetch complete Git history before running this release gate." >&2
    exit 1
fi
if ! git merge-base --is-ancestor "$baseline_commit" HEAD; then
    echo "The candidate does not descend from published 0.13.0." >&2
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
        echo "The recorded reviewed $label delta changed:" >&2
        printf '  expected %s\n  actual   %s\n' "$expected" "$actual" >&2
        exit 1
    fi
}

violations=()
while IFS= read -r path; do
    [[ -n "$path" ]] || continue

    case "$path" in
        .github/workflows/ci.yml|CHANGELOG.md|CONTRIBUTING.md|README.md|\
        SECURITY.md|SUPPORT.md|THIRD_PARTY_NOTICES.md|docs/*|\
        packaging/fedora/README.md|packaging/fedora/api-core-overlay/README.md|\
        qml/*)
            ;;
        .github/workflows/deb.yml|debian/*|packaging/debian/*|\
        scripts/check-static-analysis.sh|\
        scripts/create-release-artifact-manifest.py|\
        tests/xdg/menus/applications.menu)
            # Distribution packaging and hermetic package-test infrastructure.
            # Its own artifact, provenance, and transaction gates own this scope.
            ;;
        .editorconfig|.gitattributes|.gitignore|\
        CMakeLists.txt|.github/workflows/rpm.yml|kcm/CMakeLists.txt|\
        backend/pyproject.toml|backend/requirements-minimum.txt|\
        backend/proton-vpn-kde-backend.in|\
        backend/proton_vpn_kde_backend/__init__.py|\
        backend/proton_vpn_kde_backend/__main__.py|\
        backend/proton_vpn_kde_backend/_build_features.py.in|\
        backend/proton_vpn_kde_backend/adapters.py|\
        backend/proton_vpn_kde_backend/account_transition.py|\
        backend/proton_vpn_kde_backend/async_utils.py|\
        backend/proton_vpn_kde_backend/client_authorization.py|\
        backend/proton_vpn_kde_backend/controller.py|\
        backend/proton_vpn_kde_backend/core_settings.py|\
        backend/proton_vpn_kde_backend/demo_adapter.py|\
        backend/proton_vpn_kde_backend/core_compatibility.py|\
        backend/proton_vpn_kde_backend/core_snapshot.py|\
        backend/proton_vpn_kde_backend/core_support.py|\
        backend/proton_vpn_kde_backend/dbus_contract.py|\
        backend/proton_vpn_kde_backend/dbus_service.py|\
        backend/proton_vpn_kde_backend/errors.py|\
        backend/proton_vpn_kde_backend/features.py|\
        backend/proton_vpn_kde_backend/fido_interaction.py|\
        backend/proton_vpn_kde_backend/lifetime.py|\
        backend/proton_vpn_kde_backend/models.py|\
        backend/proton_vpn_kde_backend/packet_capture.py|\
        backend/proton_vpn_kde_backend/reconnector.py|\
        backend/proton_vpn_kde_backend/refresher_events.py|\
        backend/proton_vpn_kde_backend/snapshot_contract.py|\
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
        data/snapshot-schema-v1.json.license|data/snapshot-schema-v2.json|\
        data/snapshot-schema-v2.json.license|\
        data/dbus/quest.entropy.PlasmaVPN.Backend1.xml|\
        packaging/fedora/api-core-overlay/rebuild_overlay.py|\
        packaging/fedora/api-core-overlay/build_overlay_rpm.sh|\
        packaging/fedora/api-core-overlay/overlay-manifest.json|\
        packaging/fedora/api-core-overlay/overlay-manifest.json.license|\
        packaging/fedora/api-core-overlay/python3-proton-vpn-api-core-overlay.spec|\
        packaging/fedora/api-core-overlay/patches/0005-explicitly-activate-protection-profiles.patch|\
        packaging/fedora/api-core-overlay/patches/0003-avoid-deprecated-fido2-capability-query.patch|\
        packaging/fedora/api-core-overlay/tests/test_rebuild_overlay.py|\
        packaging/fedora/api-core-overlay/tests/test_killswitch_activation.py|\
        packaging/fedora/core-compatibility.json|\
        packaging/fedora/core-compatibility.json.license|\
        packaging/fedora/keyring-overlay/README.md|\
        packaging/fedora/keyring-overlay/build_overlay_rpm.sh|\
        packaging/fedora/keyring-overlay/check_overlay_rpm.sh|\
        packaging/fedora/keyring-overlay/overlay-manifest.json|\
        packaging/fedora/keyring-overlay/overlay-manifest.json.license|\
        packaging/fedora/keyring-overlay/patches/0001-provider-agnostic-secret-service.patch|\
        packaging/fedora/keyring-overlay/patches/0003-pin-secret-service-provider.patch|\
        packaging/fedora/keyring-overlay/python3-proton-keyring-linux.spec|\
        packaging/fedora/proton-vpn-kde.spec|\
        kcm/kcm_proton_vpn_kde.json.license|\
        runner/proton-vpn-kde-runner.json.in.license|\
        src/AgentVpnClient.cpp|src/AgentVpnClient.h|src/TrayIntegration.cpp|\
        src/BackendIdentity.cpp|src/BackendIdentity.h|\
        src/NotificationIntegration.cpp|src/NotificationIntegration.h|\
        src/AppSettings.cpp|src/AppSettings.h|kcm/ui/main.qml|\
        src/AgentControl.cpp|src/AgentControl.h|\
        src/AutostartSettings.cpp|src/AutostartSettings.h|\
        src/BackendCallPolicy.h|src/BackgroundQuitCoordinator.cpp|\
        src/ConnectionAction.h|src/OperationCompletion.h|src/ShortcutIntegration.cpp|\
        src/CommunityReport.cpp|src/CommunityReport.h|\
        src/CommunityReportFormat.cpp|src/CommunityReportFormat.h|\
        src/DesktopReadiness.cpp|src/DesktopReadiness.h|\
        src/SettingsRequestState.h|src/VpnSettingsModel.cpp|src/VpnSettingsModel.h|\
        src/SnapshotContract.generated.h|src/SnapshotCompatibility.h|\
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
        tests/LocalReadinessReportTest.cpp|tests/SnapshotContractTest.cpp|\
        tests/SnapshotTestData.h|\
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
        scripts/check-ci-policy.sh|scripts/test-ci-policy-negative.sh|\
        scripts/check-qml-ui-hygiene.sh|scripts/check-qml-visual-matrix.sh|\
        scripts/check-compatibility-metadata.py|scripts/check-spdx-headers.py|\
        scripts/check-patch-whitespace.py|\
        scripts/check-core-compatibility.sh|\
        scripts/check-core-contract.py|\
        scripts/generate-snapshot-contract.py|\
        scripts/check-native-startup.py|\
        scripts/smoke-control-center-activation.sh|\
        scripts/check-release-metadata.sh|scripts/check-rpm-artifact.sh|\
        scripts/check-rpm-reproducibility.sh|\
        scripts/check-ux-mechanics-freeze.sh|\
        scripts/benchmark-search.py|\
        scripts/smoke-qml-diagnostics.sh|scripts/smoke-qml-layout-variants.sh|\
        scripts/smoke-settings-route.sh|scripts/smoke-staged-install.sh|\
        scripts/test-ux-mechanics-freeze-negative.sh|\
        translations/provenance.json.license)
            # Presentation verification and its hermetic test drivers.
            ;;
        *)
            violations+=("$path")
            ;;
    esac
done <<<"$changed_files"

if ((${#violations[@]} > 0)); then
    echo "Files outside the reviewed 0.14 change boundary changed:" >&2
    printf '  %s\n' "${violations[@]}" >&2
    echo "Move behavioral work to a separate release or deliberately rebaseline after review." >&2
    exit 1
fi

assert_diff_hash \
    "5ff1ab23cd2993728f02362fe67cd31985b64870dc8ed12680b879acbad20ed9" \
    "build-system" CMakeLists.txt
assert_diff_hash \
    "1d259cc2b1dd1d08025f69c3aa622a122079a24ea761545e42ac37915e79e260" \
    "Python dependency floor" backend/requirements-minimum.txt
assert_diff_hash \
    "4b02e3bfd6f19af7466f46e0d0a7bc191eeb6ba35c8ece7f38d2578cf2862f4f" \
    "backend metadata" \
    backend/pyproject.toml backend/proton_vpn_kde_backend/__init__.py
assert_diff_hash \
    "0b67b0c496bf17d67c67c94a5fcb9fb3c7ee6f886b4315f121cb64daa25d8e8e" \
    "backend ownership and recovery" \
    backend/proton_vpn_kde_backend backend/tests \
    data/snapshot-schema-v2.json data/snapshot-schema-v2.json.license \
    scripts/generate-snapshot-contract.py \
    src/SnapshotContract.generated.h tests/SnapshotContractTest.cpp \
    tests/SnapshotTestData.h
assert_diff_hash \
    "644bf05ea2e42847b51c67c6290a94b54752e4a54759a0567a9d2dda98a7478f" \
    "current Core runtime contract" \
    packaging/fedora/api-core-overlay/rebuild_overlay.py \
    packaging/fedora/api-core-overlay/patches/0003-avoid-deprecated-fido2-capability-query.patch \
    packaging/fedora/api-core-overlay/tests/test_rebuild_overlay.py \
    packaging/fedora/core-compatibility.json \
    scripts/check-compatibility-metadata.py \
    scripts/check-patch-whitespace.py \
    scripts/check-core-compatibility.sh scripts/check-core-contract.py
assert_diff_hash \
    "5de064928602ca45f28c6c6a3b06e274d5b7b825c9d2d4cbeb7e61ced635753f" \
    "protection activation overlay" \
    packaging/fedora/api-core-overlay/build_overlay_rpm.sh \
    packaging/fedora/api-core-overlay/overlay-manifest.json \
    packaging/fedora/api-core-overlay/python3-proton-vpn-api-core-overlay.spec \
    packaging/fedora/api-core-overlay/patches/0005-explicitly-activate-protection-profiles.patch \
    packaging/fedora/api-core-overlay/tests/test_killswitch_activation.py
assert_diff_hash \
    "2767d7621c543ec536b3d9798a9e80b97c76dd061f7f46ffb41fc4dcefb49eb7" \
    "finite process-stop packaging" \
    data/proton-vpn-kde-backend.service.in \
    scripts/check-rpm-artifact.sh scripts/smoke-staged-install.sh
assert_diff_hash \
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" \
    "D-Bus completion-classification contract" \
    data/dbus/quest.entropy.PlasmaVPN.Backend1.xml \
    backend/proton_vpn_kde_backend/dbus_contract.py src/DbusContract.h
assert_diff_hash \
    "7b07075ad38ce7103981aed6527df9ec3901050fbbdec924ae8206d54c171e3e" \
    "Fedora metadata" packaging/fedora/proton-vpn-kde.spec
assert_diff_hash \
    "ed9fc06f2491cbe3457a0aef6fd7c5de888a34240df33004f630d782cf3f2c76" \
    "RPM test dependencies" .github/workflows/rpm.yml \
    scripts/check-rpm-reproducibility.sh
assert_diff_hash \
    "ed48be8ab69639c3dcc7f5733171debea065af0cfa022d8191630c430aaa6242" \
    "CI" .github/workflows/ci.yml
assert_diff_hash \
    "a5cf6e091b90d281dced46ea7aa0876c46988be1178d643e6898e2ec4499b481" \
    "frontend presentation contract" \
    src runner kcm tests
assert_diff_hash \
    "63192b438dc5e1ec4582c42ba6e337e876edf6afaf59e34da690e37068a7e946" \
    "QML presentation" qml

assert_diff_hash \
    "0d6bbe14e82f34479d233df594fbcd04bc65b5214bdf108535985853ff9317c5" \
    "licensing and upstream provenance" \
    .editorconfig .gitattributes .gitignore \
    backend/proton-vpn-kde-backend.in \
    backend/proton_vpn_kde_backend/_build_features.py.in \
    data/snapshot-schema-v1.json.license \
    kcm/kcm_proton_vpn_kde.json.license \
    packaging/fedora/api-core-overlay/overlay-manifest.json.license \
    packaging/fedora/core-compatibility.json.license \
    packaging/fedora/keyring-overlay \
    runner/proton-vpn-kde-runner.json.in.license \
    scripts/check-spdx-headers.py \
    translations/provenance.json.license

assert_diff_hash \
    "bafb48c97fb400717561b71ff7e41f6591ad4d9527d35df59986c586462a2060" \
    "Ubuntu packaging" \
    .github/workflows/deb.yml debian packaging/debian \
    scripts/check-static-analysis.sh \
    scripts/create-release-artifact-manifest.py \
    tests/xdg/menus/applications.menu

# Empty hashes explicitly prohibit post-0.13.0 changes in these scopes.
assert_diff_hash \
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" \
    "native startup regression" scripts/check-native-startup.py \
    scripts/smoke-control-center-activation.sh

assert_diff_hash \
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" \
    "offline search measurement" scripts/benchmark-search.py

assert_diff_hash \
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855" \
    "unambiguous desktop icon" data/proton-vpn-kde.desktop.in

echo "0.14.1 release source matches published baseline $baseline_commit plus recorded reviewed deltas"
