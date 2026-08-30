#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-$project_dir/build-native-analysis}"

if [[ ! -f "$build_dir/compile_commands.json" ]]; then
    echo "Missing compilation database: $build_dir/compile_commands.json" >&2
    exit 1
fi
if ! command -v run-clang-tidy >/dev/null; then
    echo "run-clang-tidy is required" >&2
    exit 1
fi

mapfile -t source_files < <(
    find "$project_dir/src" "$project_dir/runner" "$project_dir/kcm" \
        -maxdepth 1 -type f -name '*.cpp' -print | sort
)
if [[ ${#source_files[@]} -eq 0 ]]; then
    echo "No production C++ sources were found" >&2
    exit 1
fi

run-clang-tidy \
    -p "$build_dir" \
    -j "${PROTON_VPN_KDE_ANALYSIS_JOBS:-2}" \
    -quiet \
    -config-file "$project_dir/.clang-tidy" \
    "${source_files[@]}"
