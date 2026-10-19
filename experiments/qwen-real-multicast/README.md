# Real Qwen3-235B multicast comparison

Fixed N2048, L37 → L0 → L52; No Balancing → Direct → Chunk Streaming → Multicast. This experiment uses the accepted a848419 adapter and unchanged native b8375b5 sources. See REPORT.md for actual execution status and CAPACITY.md for static checks.

## Inputs and privacy

Supply the previously validated private 8-request source manifest, the frozen aggregate count table, and the N2048 routing prefix directory from the real-batch-scaling campaign. No download or synthetic substitution occurs. Source files, request boundaries, token order and expert IDs are revalidated by the existing qwen-real-minimal preparation. Raw inputs stay private.

## Reproduction

Use the accepted concurrent-multicast README build prerequisites and compiler flags. The recorded accepted executables can be reused only after their source/native/binary hash verification. Set PROJECT, PRIVATE (fresh directory), REFERENCE (private tokens-2048 directory), BIN, GRAPH, MANIFEST and COUNTS.

```
python "$PROJECT/experiments/qwen-real-multicast/run.py" --phase prepare-multicast --private "$PRIVATE" --reference "$REFERENCE" --binary "$BIN" --graph-tool "$GRAPH" --manifest "$MANIFEST" --counts "$COUNTS"
```

Run capacity.py --private "$PRIVATE" --native "$NATIVE" to verify pinned native hashes and all three actual prepared inputs, then write capacity-approved.json. Review CAPACITY.md for the source-referenced bounds and remaining runtime checks. Do not create a PASS gate for an unsupported input. The delivered aggregate capacity evidence applies only to the exact recorded inputs/configuration.

```
python "$PROJECT/experiments/qwen-real-multicast/run.py" --phase run --private "$PRIVATE" --reference "$REFERENCE" --binary "$BIN" --graph-tool "$GRAPH" --manifest "$MANIFEST" --counts "$COUNTS"
python "$PROJECT/experiments/qwen-real-multicast/collect.py" --private "$PRIVATE" --out "$PROJECT/experiments/qwen-real-multicast/results"
MPLCONFIGDIR=/tmp/qwen-multicast-mpl python "$PROJECT/experiments/qwen-real-multicast/analyze.py" --results "$PROJECT/experiments/qwen-real-multicast/results"
```

Each stage uses unchanged guard.py: 3600 seconds, 6 GiB RSS, 7 GiB address space, 8 GiB case disk, 2 GiB tmp disk and 1.5 GiB available memory. Existing output directories are not restart targets. A protected failure stops the campaign; do not skip a failed strategy or automatically widen resources.

## Metrics

Latency is layer_end minus layer_start in simulated picoseconds. Weight duration is weights_end minus planning_end. Dispatch/compute/combine overlap is retained in summary intervals. Group Ready is target execution/coverage; sender completion remains native feedback-driven.

Packet counts include measured physical data/envelope/control bytes. Entire-network bytes count every transmitting link, including switch egress, not unique application bytes. ACK/Response totals include token traffic. Egress queue residence is not total VOQ delay. Window query counts are proxies, not measured stall duration. Detailed multicast credit/window exports are unavailable for baseline modes without additional instrumentation; report that limitation rather than fabricate equivalent counters.

The independent child TP/Jetty allocation used by multicast differs from the Pair Jetty weight baseline. Results compare these complete accepted mechanisms, not packet copying alone. Ideal FP8 excludes scale metadata/padding; 500 GFLOP/s is assumed and the batch is an offline concatenation of real routing requests, not an observed serving scheduler batch.

One-command experiment reproduction with existing accepted executables:

```
bash experiments/qwen-real-multicast/reproduce.sh "$NATIVE" "$BIN" "$GRAPH" "$REFERENCE" "$MANIFEST" "$COUNTS" "$FRESH_PRIVATE"
```

For the separate original singleton, concurrent, network and native regressions, use the accepted `ub-concurrent-multicast/run-regressions.py` command documented in that directory, after the experiment process has exited. The original missing trace-parser native suite is reported separately, not relabeled a pass.
