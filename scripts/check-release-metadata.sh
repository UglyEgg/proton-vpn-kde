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
readme_document="$(cat "$project_dir/README.md")"
readme_posture="$(sed -n \
    '/^## Engineering posture$/,/^## Evaluate or contribute$/p' \
    "$project_dir/README.md")"
security_document="$(cat "$project_dir/docs/SECURITY-AUDIT-2026-08-30.md")"
security_posture="$(sed -n '1,/^## Scope and assurance boundary$/p' \
    "$project_dir/docs/SECURITY-AUDIT-2026-08-30.md")"
about_page="$(cat "$project_dir/qml/AboutPage.qml")"
release_notes_page="$(cat "$project_dir/qml/ReleaseNotesPage.qml")"
compatibility_document="$(cat "$project_dir/docs/COMPATIBILITY.md")"
compatibility_posture="$(sed -n '1,/^## API-Core overlay$/p' \
    "$project_dir/docs/COMPATIBILITY.md")"

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
    if [[ "$readme_posture" != *"Version $cmake_version is the current public release"* \
            || "$security_posture" != *"Release: $cmake_version"* ]]; then
        echo "Release-facing posture does not identify release $cmake_version" >&2
        exit 1
    fi
    if [[ ! "$spec_release" =~ ^[1-9][0-9]*%\{\?dist\}$ ]]; then
        echo "A dated public release requires a final Fedora release number" >&2
        exit 1
    fi
    if [[ ! "$debian_full_version" =~ ^${release_version_pattern}-[1-9][0-9]*plasmavpn[1-9][0-9]*$ ]]; then
        echo "A dated public release requires a final Debian package revision" >&2
        exit 1
    fi
    if [[ "$about_page" == *"preview"* \
            || "$release_notes_page" == *"Unreleased"* \
            || "$release_notes_page" == *"preview changes are not published"* ]]; then
        echo "A dated public release cannot retain preview-facing in-app metadata" >&2
        exit 1
    fi
    if [[ "$compatibility_posture" != *"Plasma VPN $cmake_version is the current public package release"* ]]; then
        echo "Compatibility metadata does not identify the current release" >&2
        exit 1
    fi
    stale_status_pattern="(unreleased[^.]*${release_version_pattern}|${release_version_pattern}[^.]*(unreleased|candidate|not yet a public|pending focused|before publication))"
    if grep -Eiq "$stale_status_pattern" <<<"$readme_document"; then
        echo "A dated public release cannot retain contradictory README status" >&2
        exit 1
    fi
    if grep -Eiq "$stale_status_pattern" <<<"$security_document"; then
        echo "A dated public release cannot retain contradictory security status" >&2
        exit 1
    fi
    if grep -Eiq "$stale_status_pattern" <<<"$compatibility_document"; then
        echo "A dated public release cannot retain contradictory compatibility status" >&2
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
    if [[ "$readme_posture" == *"Version $cmake_version is the current public release"* \
            || "$security_posture" == *"Release: $cmake_version" \
            || "$compatibility_posture" == *"Plasma VPN $cmake_version is the current public package release"* ]]; then
        echo "An unreleased version cannot claim current public release status" >&2
        exit 1
    fi
fi

echo "Release metadata matches version $cmake_version"
