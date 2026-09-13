#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture_root="$(mktemp -d)"
fixture_dir="$fixture_root/repository"
trap 'rm -rf -- "$fixture_root"' EXIT

mkdir -p "$fixture_dir/.github/workflows" "$fixture_dir/scripts"
cp -- "$project_dir/scripts/check-ci-policy.sh" "$fixture_dir/scripts/"

reset_workflows() {
    cp -- "$project_dir/.github/workflows/ci.yml" \
        "$fixture_dir/.github/workflows/ci.yml"
    cp -- "$project_dir/.github/workflows/rpm.yml" \
        "$fixture_dir/.github/workflows/rpm.yml"
}

expect_rejection() {
    local expected="$1"
    local output="$fixture_root/output"
    if "$fixture_dir/scripts/check-ci-policy.sh" >"$output" 2>&1; then
        echo "CI policy accepted an invalid fixture" >&2
        exit 1
    fi
    if ! rg -q "$expected" "$output"; then
        echo "CI policy rejected a fixture for an unexpected reason" >&2
        sed -n '1,120p' "$output" >&2
        exit 1
    fi
}

reset_workflows
sed -i '/plasma-breeze-common/d' "$fixture_dir/.github/workflows/ci.yml"
expect_rejection 'must install plasma-breeze-common'
echo "CI policy rejects missing visual fixture packages"

reset_workflows
sed -i '/fetch-depth: 0/d' "$fixture_dir/.github/workflows/ci.yml"
expect_rejection 'must use a full Git checkout'
echo "CI policy rejects shallow history-sensitive checkouts"

reset_workflows
sed -i '/      - main/d' "$fixture_dir/.github/workflows/ci.yml"
expect_rejection 'once per pull request'
echo "CI policy rejects duplicate feature-branch triggers"

reset_workflows
sed -i 's/-${{ github.run_attempt }}//' \
    "$fixture_dir/.github/workflows/ci.yml"
expect_rejection 'without blocking manual retries'
echo "CI policy keeps manual reruns out of their original concurrency group"

reset_workflows
sed -i "/if: github.event_name != 'pull_request'/d" \
    "$fixture_dir/.github/workflows/rpm.yml"
expect_rejection 'must remain release-only'
echo "CI policy reserves repeated RPM builds for release runs"
