# Qwen prefill token scaling

See `analysis-output/report.md`, `analysis-output/results.csv` and four SVG figures for completed measurements, failed/unreached coverage and limits. See `experiment-plan.md` and `fixed-config.json` for controls. Accepted 256 results are reused; only 512/1024/2048/4096 are newly executed.

The workload is synthetic Zipf routing with assumed effective 500 GFLOP/s and a simulated network, not real Qwen routing or hardware measurements. Planner/Relay/native/core files are unchanged. All four measured execution stages independently use 3600 s, all other accepted resource guards unchanged. No formal profiling was added.

From the experiment checkout, pass absolute paths to the accepted production binary, unchanged native libraries, and graph tool:

```
python3 experiments/qwen-prefill-token-scaling/run.py --raw /fresh/output/attempt --binary /accepted/pair-layer --lib /accepted/native/build/lib --graph-tool /accepted/graph-tool
python3 experiments/qwen-prefill-token-scaling/test-harness.py
python3 experiments/qwen-prefill-token-scaling/collect.py --raw /fresh/output/attempt --out experiments/qwen-prefill-token-scaling/proofs
```

The source filenames and exact commands/hashes are retained in proofs. An existing attempt ledger is never overwritten. Stop on failed stage/resource guard, preserve partial results and inspect state before any retry. Do not run expensive benchmarks concurrently.

`regression-reuse-proof.json` identifies the 64 previously accepted subsystem regression commands and exact unchanged sources/binary, explicitly not rerun here. `test-harness.py` is the new isolated orchestration/capacity test, with fake execution stages rather than native runs. `harness-provenance.json` describes a helper-only wording/assertion change after 512 preparation; the initial helper source is preserved.

Capacity predictions are estimates, not guarantees. Forecasts record observed free space and retain the hard 8 GiB free-disk guard.512/1024 had exact input-size/free-space checks and continuous guards but no separately recorded output-growth forecast before execution; later levels have timestamped forecasts. Large inputs, Packet/TA data and payloads stay local and are not in this delivery.
