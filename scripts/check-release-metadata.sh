#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cmake_version="$(sed -n \
    's/^project(proton-vpn-kde VERSION \([^ ]*\) LANGUAGES CXX)$/\1/p' \
    "$project_dir/CMakeLists.txt")"
spec_version="$(sed -n 's/^Version:[[:space:]]*//p' \
    "$project_dir/packaging/fedora/proton-vpn-kde.spec" | head -n 1)"
python_project_version="$(sed -n 's/^version = "\([^"]*\)"$/\1/p' \
    "$project_dir/backend/pyproject.toml" | head -n 1)"
python_runtime_version="$(sed -n \
    's/^__version__ = "\([^"]*\)"$/\1/p' \
    "$project_dir/backend/proton_vpn_kde_backend/__init__.py")"
release_notes_version="$(sed -n 's/^[[:space:]]*text: "\([0-9][^"]*\)"$/\1/p' \
    "$project_dir/qml/ReleaseNotesPage.qml" | head -n 1)"

if [[ -z "$cmake_version" ]]; then
    echo "Unable to read the canonical CMake project version" >&2
    exit 1
fi

for version_source in \
        "$spec_version" \
        "$python_project_version" \
        "$python_runtime_version" \
        "$release_notes_version"; do
    if [[ "$version_source" != "$cmake_version" ]]; then
        echo "Release metadata does not match version $cmake_version" >&2
        printf 'spec=%s python-project=%s python-runtime=%s release-notes=%s\n' \
            "$spec_version" \
            "$python_project_version" \
            "$python_runtime_version" \
            "$release_notes_version" >&2
        exit 1
    fi
done

echo "Release metadata matches version $cmake_version"
