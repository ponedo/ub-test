# EP64 Prefill Token Scaling preexperiment

This is the fixed H64/I128 synthetic model, not Qwen3-235B hardware performance.
All strategies use Pair Jetty. No simulator, planner, network, compute, payload or
protocol implementation is changed. The accepted application baseline is
`ddbab33c1bd5c74ae3946c7ce671e4d710fec402` (tree
`73c1747dcf0506191f234e1da82dee739ead0658`).

## Reproduce

Use the native checkout/build reconstructed exactly as documented in
`../pair-jetty/README.md`. Native tree is pinned by the unchanged build wrapper.
Python requires psutil and matplotlib; C++20 and the matching native libraries
are required. Run only one benchmark at a time. Reserve enough free storage:
8 GiB is a remaining-space floor, not a budget available for new logs.

```sh
export NS3_ROOT=/absolute/wqe-completion-native
export RAW=/absolute/fresh-ep64-scaling-output
bash experiments/ep64-token-scaling/run.sh
```

This compiles the real accepted application and graph tool, sequentially runs
all seven scale points, and uses the unchanged strict Pair Jetty verifier on
each strategy before proceeding. Existing output point directories are never
overwritten. A failure stops enlargement. Do not retry by weakening guards.
For a smaller *fresh* reproduction, append `--tokens 256 1024`.

`fixed-config.json` records every reused application/relay/planner parameter.
The capacity generator is reused unchanged (seed20261016, normalized Zipf1.1,
rejection of duplicate Top-k experts, source=token modulo64). Its generated
normalized input is checked against the fixed configuration. Planning is solved
once per scale and reused byte-for-byte by Direct/Chunk Streaming. NB has the
same logical routing. Prefix consistency is independently checked across scales.

Planning200ns and reroute100ns are configured simulated durations for UltraEP;
NB uses zero for both. Measured CPU planning wall time is reported separately.
The compute model is 3-matrix SwiGLU GEMM FLOPs with1000GFLOPS×0.5utilization,
plus100ns per active physical expert. Weights are3×64×128×2=49,152bytes.
Token payload is128bytes, therefore each remote token WQE has one1024B-maxTA;
weights still have multiple TAs. No Token Packing is performed.

## Time definitions

Layer latency is `layer_end - layer_start`, in the actual ns-3 event clock.
Planning and reroute are their own event intervals. Weight duration starts at
planning_end; weight completion is also reported relative to layer_start.
Dispatch/Combine spans run from earliest send through latest target data-ready,
including local assignments. Compute span runs from earliest rank compute_start
to latest compute_end. Ranks and stages can overlap: do not add these spans.
Dispatch gate obeys planning plus max(reroute, weight), then rank-local arrivals,
compute and combine dependencies determine layer completion.

Expert-load Jain measures the logical sampled routing histogram; NPU-load Jain
measures the physical planned assignment counts. Neither is network fairness.
Speedup always compares the same Token count/routing and Pair model.

## Raw evidence

Every completed run is losslessly packed only after successful strict checking.
Each package has independently hashed <=9 MB parts and a complete original-file
manifest. The full tar archive is read back and every part rehashed before its
owned generated directory is replaced. No old project evidence is deleted.
Failed or guarded outputs retain every original byte in separately labeled evidence packages after the process has terminated.

```sh
python3 experiments/ep64-token-scaling/restore.py \
 --package /path/to/tokens-256/direct-evidence \
 --out /absolute/fresh-restored-direct
python3 experiments/pair-jetty/verify.py /absolute/fresh-restored-direct/run pair
```

All CSV Routing Traces and small result records are also retained directly.
`runs.json` is the authoritative measurement ledger; `status.json` records
completed scale gates and any failure. The generator uses real dataset profiling
only to motivate orders of magnitude: these are synthetic routes and selected
preexperiment points, not measured Qwen gate decisions or exact dataset quantiles.

## Regression reproduction

Use a full Git checkout with the accepted historical objects (including
`a9ba52f6fdd2b7b5ef26913032aad2d11ab852ac`) available. Restore accepted
`experiments/multi-npu-relay/evidence` from its published evidence bundle if
using a sparse checkout. The old tests also consume tracked Direct config and
summary fixtures, restored by the driver from Git objects. Bootstrap-only
native revision/worktree and tighter nested resource-limit adaptations are
recorded; assertions and simulated inputs remain unchanged.

```sh
python3 experiments/ep64-token-scaling/regressions.py \
 --raw /absolute/fresh-regressions \
 --native "$NS3_ROOT" --build "$RAW/build" \
 --fixtures experiments/multi-npu-relay/evidence \
 --tools /absolute/pinned-prefill-build-tools
python3 experiments/ep64-token-scaling/audit.py --raw "$RAW"
python3 experiments/ep64-token-scaling/test-tools.py
```

The actual run retained three harness failures before recovery: nested address
limit, missing old config fixture, then missing old summary fixtures. Final
normal/optimized old tests and prior regression chain passed; inspect
`regressions-old-retry-evidence` recovery/results.json after restoration.
`resume-old-tests.py` documents that recovery without rerunning completed48
network cases. A fresh run uses the corrected main regression driver instead.

## Delivered results

See REPORT.md and data/analysis/scaling.csv. All seven requested scales and21 strategy arms passed after the explicitly
authorized storage cleanup and resumed scan. The initial6250-token NB disk-guard
failure remains under data/attempts/initial, separate from its successful retry.
The retry input hashes match exactly, and the original protection limits remain. All raw run bytes and unsuccessful harness
logs are preserved, including received payloads. Rebuildable executables and
copied source trees are excluded with hashes in data/packaging-exclusions.json.
Nested regression evidence packages can be restored with the same restore.py.
The original source/raw working directories were not deleted when packaging.


### Authorized resumed scan (actual run)

The initial scan stopped safely at the disk guard. After approved cleanup, the
same compiled binaries were reused with a fresh output root:

```sh
python3 experiments/ep64-token-scaling/run.py \
 --raw "$RESUMED" --binary "$RAW/build/pair-layer" \
 --lib "$NS3_ROOT/build/lib" --graph-tool "$RAW/build/graph-tool" \
 --reference-raw "$RAW" --tokens 6250 8192 12500
python3 experiments/ep64-token-scaling/merge-attempts.py \
 --initial "$RAW" --resumed "$RESUMED" --out "$COMBINED"
python3 experiments/ep64-token-scaling/collect.py \
 --raw "$COMBINED" --out "$COMBINED/analysis"
python3 experiments/ep64-token-scaling/audit.py --raw "$COMBINED"
```

A sufficiently provisioned fresh reproduction should run all seven points using
run.sh directly. A stopped run must not be silently retried with weaker guards.
Merged files retain both attempt ledgers and the original failed6250 evidence;
final speedups use only successful same-input arms.

Final independent review checked35 evidence packages,16,096 original members
and9,591,506,303 uncompressed bytes; all member and transport hashes passed.
It independently recomputed all21 metrics and restored/reverified the256-token
Chunk case with the unchanged Pair oracle. `data/final-independent-review.json`
records that pre-freeze audit (291 files before adding the audit artifacts).
`DELIVERY-MANIFEST.json` covers the final deliverable file set. The executed
independent review script is retained verbatim with its original local paths;
portable experiment checks are provided by audit.py and restore.py above.
