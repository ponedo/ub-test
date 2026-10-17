# Qwen3-30B-A3B dimension sensitivity experiment

Baseline application: `099f6bcb15204afbd572fe860c7d0955c624973c`.
Native protocol stays at `2fde39d02920e639f5b200d0c5262a517326deb8`.
Official model revision and formulas: `MODEL_PARAMETERS.md`.

Only the MoE dimensions change to H2048/I768. This does not execute Qwen3 or obtain real router traces. The routing is the original fixed Zipf 1.1, seed 20261016, E128, top-k8 at EP64. Compute throughput is an unchanged assumption.

Build from repository root:

```sh
NS3_ROOT=/absolute/path/to/fixed-native OUT=/absolute/fresh/build \
  bash experiments/pair-jetty/build.sh
```

Run the first capacity gate (always summary, pair by default):

```sh
python3 experiments/qwen3-model-size/test-parameters.py
python3 experiments/qwen3-model-size/run.py \
  --raw /absolute/fresh/qwen-results \
  --binary /absolute/fresh/build/pair-layer \
  --lib /absolute/path/to/fixed-native/build/lib \
  --graph-tool /absolute/path/to/graph-tool \
  --tokens 256
```

The exact workload and supported capacity ceilings are in `fixed-config.json`.
Read `CAPACITY_DESIGN.md` before further scale points: configured logical budgets are not guaranteed memory availability, and the existing guarded runner stops at the first failure. Use a fresh result directory for each run. Do not rerun a failed capacity point with weaker guards.

`prepare.py` writes all strategies from one accepted planner solution and identical routing. It preserves a structured failure when the logical payload guard rejects, and raises unrelated errors. `run.py` executes preflight, native simulator and postflight under the same resource protections, records actual failure resources, and retains only lightweight summary output. It does not replace network events with analytical times.

Normal GitHub deliverables contain source, configuration, compact test/measurement evidence and report/plots, not raw native logs.

Additional verification and reporting:

```sh
# Reuse the accepted tiered-logging fixture preparation to run all same-input modes.
python3 experiments/tiered-logging/run.py \
  --binary /absolute/fresh/build/pair-layer \
  --old-binary /absolute/original/pre-logging/pair-layer \
  --lib /absolute/path/to/fixed-native/build/lib \
  --graph-tool /absolute/path/to/graph-tool \
  --fixtures-root /absolute/path/to/multi-npu-relay/evidence \
  --ep64-package /absolute/path/to/accepted/tokens-256/prepared-evidence \
  --out /absolute/fresh/regression \
  --cases nb-small direct-small chunk-small multichunk-multita --skip-faults
python3 experiments/qwen3-model-size/test-capacity.py \
  --binary /absolute/fresh/build/pair-layer \
  --input /absolute/fresh/regression/inputs/nb-small/input.txt \
  --relay-input /absolute/fresh/regression/inputs/multichunk-multita/input.txt \
  --out /absolute/fresh/boundaries
python3 experiments/qwen3-model-size/test-faults.py \
  --binary /absolute/fresh/build/pair-layer \
  --inputs /absolute/fresh/regression/inputs --out /absolute/fresh/faults
python3 experiments/qwen3-model-size/analyze.py --raw /absolute/fresh/qwen-results --out /absolute/fresh/analysis
python3 experiments/qwen3-model-size/collect.py --raw /absolute/fresh/qwen-results --out /absolute/fresh/small-evidence
```

The old-model comparison imports the already accepted measured 21-run dataset from `experiments/ep64-token-scaling/data/runs.json`. `analyze.py` asserts exact routing hashes and executed plan loads/replica counts for comparable completed points. It does not extrapolate missing Qwen measurements. Stage spans overlap and must not be summed to reconstruct layer latency. Simulator wall time, preparation/verification wall time and assumed planning latency are separate quantities.
