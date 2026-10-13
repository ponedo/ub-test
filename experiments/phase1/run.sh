#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
out=${PHASE1_OUTPUT:-experiments/phase1/output}
mkdir -p "$out/traces" "$out/analysis"
python3 -m unittest discover -s workloads/tests -v 2>&1 | tee "$out/tests.txt"
python3 -m workloads.generators.synthetic --output "$out/traces/synthetic_mixed.csv" --seed 42
python3 -m workloads.generators.synthetic --output "$out/traces/synthetic_equal.csv" --sizes 256 --seed 42
python3 -m workloads.generators.synthetic --output "$out/traces/synthetic_burst.csv" --arrival burst --seed 42
python3 -m workloads.generators.synthetic --output "$out/traces/synthetic_poisson.csv" --arrival poisson --seed 42
common=(--hidden-size 1024 --top-k 4 --experts 64 --ranks 8 --aivs 16 --seed 42)
python3 -m workloads.generators.moe_dispatch --output "$out/traces/moe_low.csv" "${common[@]}" --tokens 32 --capacity 32
python3 -m workloads.generators.moe_dispatch --output "$out/traces/moe_high.csv" "${common[@]}" --tokens 4096 --capacity 4096
python3 -m workloads.generators.moe_dispatch --output "$out/traces/moe_skew.csv" "${common[@]}" --tokens 4096 --capacity 4096 --score-factor 2 --hot-rank 1
python3 -m workloads.generators.moe_dispatch --output "$out/traces/moe_low_fixed_capacity.csv" "${common[@]}" --tokens 32 --capacity 4096
python3 -m workloads.generators.moe_dispatch --output "$out/traces/moe_high_staggered.csv" "${common[@]}" --tokens 4096 --capacity 4096 --aiv-stagger-ns 100 --token-prep-ns 10
for trace in "$out"/traces/*.csv; do python3 -m workloads.schema.validate "$trace"; done
python3 -m evaluation.analyze_traces --traces "$out"/traces/*.csv --output-dir "$out/analysis" | tee "$out/analysis.txt"
python3 -m evaluation.plot_phase1 --input-dir "$out/analysis"
# Reproduce the high-token case in a fresh destination and compare all trace bytes.
repeat=$(mktemp -d)
trap 'rm -rf "$repeat"' EXIT
python3 -m workloads.generators.moe_dispatch --output "$repeat/repeat.csv" "${common[@]}" --tokens 4096 --capacity 4096
for suffix in '' .meta.json .moe.jsonl .routes.jsonl; do cmp "$out/traces/moe_high.csv$suffix" "$repeat/repeat.csv$suffix"; done
echo 'PASS: trace tests, schema validation, conservation and deterministic high-token rerun; no simulator invoked' | tee "$out/validation.txt"
