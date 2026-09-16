#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cmake_version="$(sed -n \
    's/^project(proton-vpn-kde VERSION \([^ ]*\) LANGUAGES CXX)$/\1/p' \
    "$project_dir/CMakeLists.txt")"
release_version_pattern="${cmake_version//./\\.}"
spec_version="$(sed -n 's/^Version:[[:space:]]*//p' \
    "$project_dir/packaging/fedora/proton-vpn-kde.spec" | head -n 1)"
spec_release="$(sed -n 's/^Release:[[:space:]]*//p' \
    "$project_dir/packaging/fedora/proton-vpn-kde.spec" | head -n 1)"
debian_version="$(sed -n \
    '1s/^proton-vpn-kde (\([^-]*\)-[^)]*).*/\1/p' \
    "$project_dir/debian/changelog")"
debian_full_version="$(sed -n \
    '1s/^proton-vpn-kde (\([^)]*\)).*/\1/p' \
    "$project_dir/debian/changelog")"
python_project_version="$(sed -n 's/^version = "\([^"]*\)"$/\1/p' \
    "$project_dir/backend/pyproject.toml" | head -n 1)"
python_runtime_version="$(sed -n \
    's/^__version__ = "\([^"]*\)"$/\1/p' \
    "$project_dir/backend/proton_vpn_kde_backend/__init__.py")"
release_notes_version="$(sed -n 's/^[[:space:]]*text: "\([0-9][^"]*\)"$/\1/p' \
    "$project_dir/qml/ReleaseNotesPage.qml" | head -n 1)"
readme_posture="$(sed -n \
    '/^## Engineering posture$/,/^## Current status$/p' \
    "$project_dir/README.md")"
security_posture="$(sed -n '1,/^## Scope and assurance boundary$/p' \
    "$project_dir/docs/SECURITY-AUDIT-2026-08-30.md")"

if [[ -z "$cmake_version" ]]; then
    echo "Unable to read the canonical CMake project version" >&2
    exit 1
fi

for version_source in \
        "$spec_version" \
        "$debian_version" \
        "$python_project_version" \
        "$python_runtime_version" \
        "$release_notes_version"; do
    if [[ "$version_source" != "$cmake_version" ]]; then
        echo "Release metadata does not match version $cmake_version" >&2
        printf 'spec=%s debian=%s python-project=%s python-runtime=%s release-notes=%s\n' \
            "$spec_version" \
            "$debian_version" \
            "$python_project_version" \
            "$python_runtime_version" \
            "$release_notes_version" >&2
        exit 1
    fi
done

if grep -Eq "^## \[$release_version_pattern\] - [0-9]{4}-[0-9]{2}-[0-9]{2}$" \
        "$project_dir/CHANGELOG.md"; then
    if [[ "$readme_posture" != *"$cmake_version release"* \
            || "$security_posture" != *"Release: $cmake_version"* ]]; then
        echo "Release-facing posture does not identify release $cmake_version" >&2
        exit 1
    fi
    if [[ "$spec_release" == 0.* ]]; then
        echo "A dated public release requires a final Fedora release number" >&2
        exit 1
    fi
else
    for posture in "$readme_posture" "$security_posture"; do
        if [[ "$posture" != *"unreleased $cmake_version"* \
                && "$posture" != *"unreleased \`$cmake_version\`"* ]]; then
            echo "Release-facing posture does not identify unreleased $cmake_version" >&2
            exit 1
        fi
    done
    if [[ "$spec_release" != 0.* \
            || "$debian_full_version" != "$cmake_version"-0~* ]]; then
        echo "An unreleased version needs pre-final Fedora and Debian package revisions" >&2
        exit 1
    fi
fi

echo "Release metadata matches version $cmake_version"
