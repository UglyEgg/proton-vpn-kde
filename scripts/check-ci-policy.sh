#!/usr/bin/bash
# SPDX-FileCopyrightText: 2026 Plasma VPN contributors
# SPDX-License-Identifier: GPL-3.0-or-later

set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_workflow="$project_dir/.github/workflows/ci.yml"
rpm_workflow="$project_dir/.github/workflows/rpm.yml"

if ! rg -Uq \
        '^on:\n  push:\n    branches:\n      - main\n  pull_request:\n' \
        "$source_workflow"; then
    echo "Source CI must run once per pull request and on main pushes only" >&2
    exit 1
fi

if ! rg -Uq \
        '^on:\n  pull_request:\n  push:\n    tags:\n      - "v\*"\n  workflow_dispatch:\n' \
        "$rpm_workflow"; then
    echo "RPM CI must validate pull requests and reserve push builds for release tags" >&2
    exit 1
fi

workflow_job_block() {
    local workflow="$1"
    local job_name="$2"
    awk -v header="  $job_name:" '
        $0 == header { in_job = 1; seen_header = 1 }
        in_job && seen_header && $0 != header && \
            $0 ~ /^  [[:alnum:]_-]+:/ { exit }
        in_job { print }
    ' "$workflow"
}

for source_job in fedora native-analysis; do
    job_block="$(workflow_job_block "$source_workflow" "$source_job")"
    if [[ -z "$job_block" ]]; then
        echo "Source CI job '$source_job' is missing" >&2
        exit 1
    fi
    for dependency in plasma-breeze-common plasma-integration; do
        if ! grep -Eq \
                "(^|[[:space:]])$dependency([[:space:]\\\\]|$)" \
                <<<"$job_block"; then
            echo "Source CI job '$source_job' must install $dependency" >&2
            exit 1
        fi
    done
    if ! grep -Fq 'fetch-depth: 0' <<<"$job_block"; then
        echo "Source CI job '$source_job' must use a full Git checkout for history-sensitive tests" >&2
        exit 1
    fi
done

for release_step in \
        'Verify API Core overlay reproducibility' \
        'Verify package reproducibility' \
        'Stage release artifacts' \
        'Upload RPM artifacts'; do
    step_block="$(awk -v header="      - name: $release_step" '
        $0 == header { in_step = 1; seen_header = 1 }
        in_step && seen_header && $0 != header && $0 ~ /^      - name:/ { exit }
        in_step { print }
    ' "$rpm_workflow")"
    if [[ -z "$step_block" ]] \
            || ! grep -Fq "if: github.event_name != 'pull_request'" \
                <<<"$step_block"; then
        echo "RPM step '$release_step' must remain release-only" >&2
        exit 1
    fi
done

echo "CI policy is aligned"
