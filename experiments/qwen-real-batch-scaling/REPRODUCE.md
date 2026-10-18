# Aggregate analysis reproduction

These commands do not run the simulator. Supply the private aggregate ledger root and audited prefix summary explicitly; do not place raw routing or payload artifacts in the public results directory.

```sh
python collect.py --private-root "$LEDGER_ROOT" --historical ../qwen-real-minimal/results --historical-fanout "$HISTORICAL_GRAPH_AGGREGATE" --skew "$AUDITED_PREFIX_SUMMARY" --out results
MPLCONFIGDIR=/tmp/qwen-mpl XDG_CACHE_HOME=/tmp/qwen-xdg OPENBLAS_NUM_THREADS=1 python analyze.py --results results
python test_collect.py
```

Python 3 and matplotlib are required. `--report-only` skips plotting while an execution campaign is active. The CSV is the plot source, alongside equivalent aggregate.json and input-skew.json. All plot values are derived from verified completed cases; host wall and CPU durations are never used to compare simulated strategy latency.

The execution scope is N256 (historical reuse), N512, N1024 and N2048; three serialized layers and three strategies give 36 accepted rows, 27 newly executed. Scope completion requires all 27 new case stage checks plus the explicit N2048 boundary marker. The original outer driver's STOPPED remains visible and is not rewritten to PASS. N4096 static input evidence is retained separately, not included in performance acceptance.
