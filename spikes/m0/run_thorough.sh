#!/usr/bin/env bash
# Thorough-tier model benchmark from a clean slate: saved tuning params and Optuna
# journals under out/models survive delete_checkpoints and would be reused otherwise.
set -uo pipefail
cd "$(dirname "$0")/../.."
for n in 50000 150000 500000; do
  slug="us-zz-synth$((n / 1000))k"
  rm -rf "bench-data/data/$slug/out/models"
  uv run python spikes/m0/bench.py bench-data "$slug" thorough model
done
