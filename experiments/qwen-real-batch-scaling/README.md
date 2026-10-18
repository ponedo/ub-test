# Real Qwen3-235B batch scaling (accepted scope through 2048)

Base application: `93bdf7fef154743738910da9e561d796f5955507`. This directory adds only orchestration, read-only graph statistics, tests and aggregate analysis. The planner, simulator, native protocol and existing model/configuration sources are unchanged.

## Run

Supply the previously validated private eight-request manifest, its matching aggregate frozen-count reference, an accepted Release pair-layer binary/library, and the accepted graph-tool. Do not upload the manifest, source JSON, routing JSON or prepared input archives.

```sh
python run.py --private "$NEW_PRIVATE_RUN_ROOT" --binary "$PAIR_LAYER" \
  --lib "$NATIVE_LIB" --graph-tool "$GRAPH_TOOL" \
  --source-manifest "$PRIVATE_MANIFEST" --frozen-counts ../qwen-real-length-survey/results/expert-counts.csv.gz
```

Use a fresh output directory. The driver runs N512, N1024 and N2048, each with L0/L37/L52 and No Balancing/Direct/Chunk. It requires nine unique fully verified cases before advancing. No 4096 execution is accepted. All protected stages retain 3600 seconds, 6 GiB process-tree RSS, 7 GiB per-process address space, 8 GiB minimum output-disk free space, 2 GiB temporary free space and 1.5 GiB available host memory. Resource failure stops advancement.

During this campaign the user reduced the scope while the original outer interpreter was running. The 2048 child therefore writes `scope-boundary.json` only after all nine cases and four stages pass, then exits 3. The original outer STOPPED record is retained. The separate aggregate scope completion requires all 27 new cases and the explicit USER_SCOPE_LIMIT_REACHED marker. The current source understands this exit code. Unit tests exercise both the original loaded outer behavior and the current behavior.

## Tests

```sh
python test_stage_gates.py
python test_live_scope_boundary.py
python test_collect.py
RELAY_GRAPH_TOOL="$GRAPH_TOOL" python test_fanout_stats.py
python regress_small.py --private "$NEW_REGRESSION_ROOT" --binary "$PAIR_LAYER" --lib "$NATIVE_LIB" --graph-tool "$GRAPH_TOOL"
```

`regress_small.py` runs the unchanged small 8-NPU synthetic hot-expert case through No Balancing, Direct, Two-Stage and Chunk with independent Preflight/Postflight and full online checks. It is a correctness regression, not a new scaling result. See REPRODUCE.md for aggregation/plots and FANOUT.md for exact source predicates and field definitions.

## Evidence and privacy

N256 simulated latencies are historical reuse. Its fanout graphs were independently reconstructed from the exact recovered raw source prefix, unchanged planner and graph generator; no historical simulated latency was regenerated for those graphs. A fresh N256/L0/No-Balancing execution matches the historical stable event/byte/completion outputs exactly, excluding only host verification timing. Recovered host performance is not compared with old-host wall time.

The source phase remains the dataset's first-record convention, not an explicit phase label. Eight independent requests form an offline batch; nested prefixes are correlated. Source NPU `batch_token_id % 64` is a simulation assumption. FP8 weights are ideal payload bytes without scale metadata/padding, BF16 activations and 500 GFLOP/s are model assumptions. See REPORT.md for measured results and limitations.

The explicit Zipf regression uses the unchanged original H64/I128 EP64 N256 generator/configuration. Run `python regress_zipf.py` with the same four arguments as `regress_small.py`, using a different fresh private directory. Its three strategies match the historical routing SHA256, layer latency, WQE/TA/event/completion/replica counts exactly; results/zipf-regression.json records the comparisons.

The historical nine rows leave `mapping_sha256` blank because that field was not persisted in their original performance ledger. Their published routing SHA and separately verified original-prefix identity remain available; the blank is not a failed mapping check. All 27 new rows persist both routing and canonical mapping hashes.
