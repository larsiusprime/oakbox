#!/usr/bin/env bash
# Run every step on one locality, stopping at the first failure.
set -euo pipefail
base=$1; slug=$2; tier=${3:-thorough}
for s in assemble clean check_values model; do
  echo "=== $s"
  uv run python "$(dirname "$0")/stage.py" "$base" "$slug" "$s" "$tier" > "$base/$slug.$s.log" 2>&1 || { tail -25 "$base/$slug.$s.log"; exit 1; }
  grep "@@OAKBOX" "$base/$slug.$s.log" | cut -c1-200
done
