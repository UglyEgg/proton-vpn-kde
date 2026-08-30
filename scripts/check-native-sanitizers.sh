#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
build_dir="${1:-$project_dir/build-native-analysis}"
compiler="${CXX:-clang++}"
sanitizer_flags="-fsanitize=address,undefined"

if ! command -v "$compiler" >/dev/null; then
    echo "The C++ compiler '$compiler' is required" >&2
    exit 1
fi

cmake \
    -S "$project_dir" \
    -B "$build_dir" \
    -G Ninja \
    -DBUILD_TESTING=ON \
    -DCMAKE_BUILD_TYPE=Debug \
    -DCMAKE_CXX_COMPILER="$compiler" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
    -DCMAKE_CXX_FLAGS_DEBUG="-O1 -g $sanitizer_flags -fno-omit-frame-pointer -fno-sanitize-recover=all" \
    -DCMAKE_EXE_LINKER_FLAGS="$sanitizer_flags" \
    -DCMAKE_MODULE_LINKER_FLAGS="$sanitizer_flags" \
    -DCMAKE_SHARED_LINKER_FLAGS="$sanitizer_flags"
cmake --build "$build_dir" \
    --parallel "${PROTON_VPN_KDE_ANALYSIS_JOBS:-2}"

export ASAN_OPTIONS="${ASAN_OPTIONS:-abort_on_error=1:detect_leaks=1:strict_string_checks=1}"
export UBSAN_OPTIONS="${UBSAN_OPTIONS:-halt_on_error=1:print_stacktrace=1}"
export CTEST_OUTPUT_ON_FAILURE=1
ctest --test-dir "$build_dir" --output-on-failure \
    --parallel "${PROTON_VPN_KDE_ANALYSIS_JOBS:-2}"
