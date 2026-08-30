#!/usr/bin/bash
set -euo pipefail

project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
analysis_dir="$(mktemp -d /tmp/plasma-vpn-python-analysis.XXXXXX)"
trap 'rm -rf "$analysis_dir"' EXIT

export PYTHONPATH="$project_dir/backend${PYTHONPATH:+:$PYTHONPATH}"
export COVERAGE_FILE="$analysis_dir/coverage"

python3 -m mypy \
    --config-file "$project_dir/backend/pyproject.toml" \
    "$project_dir/backend/proton_vpn_kde_backend"
python3 -m coverage erase
python3 -m coverage run \
    --rcfile="$project_dir/backend/pyproject.toml" \
    -m unittest discover -s "$project_dir/backend/tests"
python3 -m coverage report \
    --rcfile="$project_dir/backend/pyproject.toml"

