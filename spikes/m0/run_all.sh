#!/usr/bin/env bash
# Full M0 benchmark matrix. Results append to bench-data/bench.jsonl.
set -uo pipefail
cd "$(dirname "$0")/../.."
for n in 50000 150000 500000; do
  slug="us-zz-synth$((n / 1000))k"
  [ -d "bench-data/data/$slug" ] || uv run python spikes/m0/make_synthetic.py "$n" bench-data
  uv run python spikes/m0/bench.py bench-data "$slug" quick
done
for n in 50000 150000 500000; do
  slug="us-zz-synth$((n / 1000))k"
  uv run python spikes/m0/bench.py bench-data "$slug" thorough model
done
