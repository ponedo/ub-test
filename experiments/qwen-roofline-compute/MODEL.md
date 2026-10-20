# Compute contract and evidence boundaries

## Formula and scheduler audit

Parent `../ultraep-multicast-integration/layer.cc:357` already computes `2 * matrices * m * H * I`; three matrices therefore mean `6mHI`, not an additional multiplier. Legacy preserves its exact integer-picosecond ceiling and `setup_ns` addition. `Compute` (parent lines358–365) waits for the NPU's dispatch/weight dependencies, visits physical experts in their existing order, sums their durations serially, and starts Combine only after the NPU's total finishes. `Ready`, `Gate`, `Start`, native transport and network code are unchanged. The source-region equality gate in stage-a.py checks the scheduler and dependency sections.

Roofline defaults: 100 TFLOP/s, 2692 decimal GB/s, zero launch overhead. Rates are effective assumptions and are NOT multiplied by the legacy utilization factor. Integer positive CLI parameters are configurable, strictly parsed and range checked. The official experiment uses exactly these defaults for all four strategies.

For m>0, FLOPs = 6mHI. Weights = the configured full Expert object size once per invocation; for official FP8 three-matrix SwiGLU this is 3HI = 18,874,368 B (18 MiB). Synthetic tests may override the object size and record that separately. Weights are resident in HBM when computation starts, but still require a compute-side HBM read. The UB transfer writes a remote copy into HBM; it does not eliminate this later local read. Main and replica experts use the same local read rule. No retained on-chip weight cache across calls is modeled.

Activation policy `separate-three-gemm-fused-silu-mul-no-cache-v1`:
- gate/up each read X: 2mH BF16 elements;
- G/U each written by GEMM, then each read by fused SiLU/multiply: 4mI elements;
- gated Z written, then read by down GEMM: 2mI elements;
- Y output written: mH elements.

Thus activation bytes = 2m(3H+6I) = 43,008m B at H4096/I1536. This is an explicit unfused-GEMM/intermediate-materialization assumption, not measured hardware traffic. Do not add UB packet bytes, network weight fanout, or Dispatch/Combine DMA to this compute-side HBM term. A more fused implementation could have lower traffic; no undocumented fusion adjustment is applied.

Tcompute_ps = ceil(F / compute_tflops); Tmemory_ps = ceil((weights+activations)*1000 / hbm_bandwidth_gbps); Texpert_ps = max(Tcompute_ps,Tmemory_ps). All products use 128-bit intermediates with checked64-bit outputs and the existing compute-time bound. m=0 produces zero FLOPs/bytes/time and no scheduled Expert invocation. Same-NPU experts cannot each monopolize compute and bandwidth concurrently: existing serialization remains unchanged.

`expert-compute.csv` reports per-physical-Expert token totals, arithmetic, actual event timestamps and selected duration; it contains no per-token routing. Independent Python oracle checks those tokens against frozen assignments, formulas, model/rates, zero work, physical ordering and exact NPU interval sums. Legacy rows include hypothetical roofline arithmetic for inspection, but only legacy duration drives scheduling.

## Hardware source, fixed version

CloudMatrix384 paper v2 (2025-06-18), §5.5.2 Table9, PDF p48 reports 1346 GB/s **achieved MLA bandwidth on a single Ascend910C die**, with1600 GB/s peak and84.1% utilization:
https://arxiv.org/pdf/2506.12708v2#page=48

v2 §3.3.1, p11 describes a dual-die NPU package and1.6 TB/s/die,3.2 TB/s/package:
https://arxiv.org/pdf/2506.12708v2#page=11

We use2692=2*1346 GB/s as the user-specified dual-die reference extrapolation. It assumes both dies effectively participate with balanced local traffic, without extra cross-die contention. This is neither measured whole-NPU Expert GEMM bandwidth nor guaranteed for these matrix shapes.100 TFLOPS is a modeling assumption, not a910C small-batch Expert measurement.

Version caveat: v3 removes the absolute1346/1600 values and retains84.1% utilization (Table8,p48). The numerical citation intentionally fixes v2, not latest. No hardware measurement is performed in this experiment.

## Retained boundaries

Real Routing Trace/model dimensions; deterministic validation payload bytes, not loaded checkpoint or numerical GEMM. Only compute duration changes. Native payload/WQE/TA, TP/Jetty drain, credits, Tag-free multicast and all network parameters stay unchanged. Phase spans may overlap; never sum Dispatch, Compute and Combine spans as a layer decomposition. Host wall time with concurrent processes is not a simulator performance metric.
