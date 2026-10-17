# EP64 Prefill Token Scaling preexperiment

**Scope: H64/I128 scaled synthetic model, not real Qwen3-235B hardware performance.**

## Configuration and provenance

Accepted application: `ddbab33c1bd5c74ae3946c7ce671e4d710fec402`; native `2fde39d02920e639f5b200d0c5262a517326deb8`. All strategies use Pair Jetty, EP64, 128 experts, Top-k8, single switch, 100 Gbit/s links, 20 ns link delay, 1024-byte TA segmentation. No accepted simulator/planner/network/compute source was changed. `data/provenance.json` contains source and library hashes; `fixed-config.json` pins all defaults.

Routing uses the retained generator: seed20261016, probability proportional to (expert+1)^-1.1, Top-k rejection sampling without duplicates, round-robin token source. Every strategy receives the same routing per Token count. Direct and Chunk use the exact same single computed UltraEP plan. Stored routing CSVs are prefix-consistent across scales. Main placement is two consecutive experts per NPU; two redundant slots per NPU.

Compute is 3-matrix SwiGLU GEMM FLOPs at1000GFLOPS×0.5 utilization plus100ns per active physical expert. Explicit synthetic payloads validate every byte, but no numerical MLP runs. Each token payload is128B (one TA); each expert weight is49,152B. UltraEP planning200ns and reroute100ns are fixed simulated parameters; separately measured planner CPU wall time is not injected as NPU time. NB uses zero planning/reroute time.

## Actual measurements

| Global tokens | Assignments | Strategy | Layer us | Speedup | Max NPU load | Replicas | Weight span us | Host wall s | RSS MiB |
|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 256 | 2048 | no-balancing | 56.199264 | 1.0000 | 406 | 0 | 0.000000 | 1.51 | 119.2 |
| 256 | 2048 | direct | 68.490416 | 0.8205 | 34 | 51 | 62.661680 | 2.01 | 160.1 |
| 256 | 2048 | chunk-streaming | 33.176256 | 1.6940 | 34 | 51 | 27.358240 | 2.26 | 159.4 |
| 1024 | 8192 | no-balancing | 221.854808 | 1.0000 | 1607 | 0 | 0.000000 | 5.02 | 209.7 |
| 1024 | 8192 | direct | 88.328880 | 2.5117 | 132 | 56 | 67.128360 | 6.52 | 248.3 |
| 1024 | 8192 | chunk-streaming | 47.733568 | 4.6478 | 132 | 56 | 26.528760 | 7.28 | 247.2 |
| 2048 | 16384 | no-balancing | 443.035384 | 1.0000 | 3226 | 0 | 0.000000 | 10.03 | 260.3 |
| 2048 | 16384 | direct | 108.306688 | 4.0906 | 262 | 59 | 67.128360 | 12.03 | 292.4 |
| 2048 | 16384 | chunk-streaming | 67.892048 | 6.5256 | 262 | 59 | 26.518320 | 13.79 | 291.0 |
| 4096 | 32768 | no-balancing | 890.134368 | 1.0000 | 6477 | 0 | 0.000000 | 21.56 | 327.2 |
| 4096 | 32768 | direct | 149.195096 | 5.9662 | 524 | 57 | 67.128360 | 23.57 | 380.4 |
| 4096 | 32768 | chunk-streaming | 108.519896 | 8.2025 | 524 | 57 | 26.528880 | 25.07 | 379.3 |
| 6250 | 50000 | no-balancing | 1353.604768 | 1.0000 | 9847 | 0 | 0.000000 | 37.10 | 391.3 |
| 6250 | 50000 | direct | 191.494208 | 7.0686 | 798 | 60 | 67.128360 | 37.86 | 471.3 |
| 6250 | 50000 | chunk-streaming | 151.659632 | 8.9253 | 798 | 60 | 26.529040 | 37.61 | 468.2 |
| 8192 | 65536 | no-balancing | 1768.082568 | 1.0000 | 12882 | 0 | 0.000000 | 53.67 | 447.8 |
| 8192 | 65536 | direct | 229.481144 | 7.7047 | 1046 | 58 | 67.128360 | 50.14 | 551.9 |
| 8192 | 65536 | chunk-streaming | 189.539064 | 9.3283 | 1046 | 58 | 26.524040 | 53.16 | 549.8 |
| 12500 | 100000 | no-balancing | 2709.921648 | 1.0000 | 19757 | 0 | 0.000000 | 93.51 | 573.5 |
| 12500 | 100000 | direct | 315.206120 | 8.5973 | 1595 | 59 | 67.128360 | 83.74 | 734.8 |
| 12500 | 100000 | chunk-streaming | 274.995520 | 9.8544 | 1595 | 59 | 26.518320 | 86.25 | 732.8 |

Values are actual ns-3 event measurements. Host resource observations are single runs, not repeated statistical estimates. `data/analysis/scaling.csv` includes planning/reroute, dispatch/compute/combine spans, maximum rank compute duration, byte/TA/WQE/event/callback counts, logical expert and physical NPU Jain, and separate verifier resources.

## Execution bounds and failures

Scan status: **PASS**. Complete three-strategy Token points: [256, 1024, 2048, 4096, 6250, 8192, 12500].
- Initial6250-token NB attempt stopped at the8GiB free-disk guard after27.83s (peakRSS391.2MiB), without a final simulated latency. Its complete partial evidence is under data/attempts/initial. The user explicitly approved cleanup of two sets of verified old expanded copies and resuming6250→8192→12500. A fresh output root preserved all initial results;6250 routing and full simulator input hashes matched exactly before execution. The8GiB/300s guards remained unchanged. Cleanup raised free disk to12.94GiB; its receipt is retained under data/attempts/resumed.
- Requested21arms: 21 PASS, 0 FAIL, 0 NOT_RUN.
- Unattempted Token points: [].
- Guards remain300s per measured stage,6GiB process-tree RSS,7GiB address space,8GiB free output disk,1.5GiB host-available memory,2GiB free /tmp. No capacity limit or guard was loosened.
- Initial host preflight found only5.1GiB free. With explicit user approval, one previously verified duplicate restored evidence tree (16,643 files) was removed; originals and published evidence bundles remain. The cleanup and fresh recoverability check are recorded.

## Answers to the experiment questions

- direct: speedup increases monotonically across successful sampled points: 256→0.8205×, 1024→2.5117×, 2048→4.0906×, 4096→5.9662×, 6250→7.0686×, 8192→7.7047×, 12500→8.5973×.
  First measured winning point: 1024. This is a sampled bound, not an exact crossover.
- chunk-streaming: speedup increases monotonically across successful sampled points: 256→1.6940×, 1024→4.6478×, 2048→6.5256×, 4096→8.2025×, 6250→8.9253×, 8192→9.3283×, 12500→9.8544×.
  First measured winning point: 256. This is a sampled bound, not an exact crossover.
- Direct minus Chunk layer-latency gaps at the measured points: 256: 35.314160us, 1024: 40.595312us, 2048: 40.414640us, 4096: 40.675200us, 6250: 39.834576us, 8192: 39.942080us, 12500: 40.210600us.
- Direct weight span changes 62.661680→67.128360us from 256→12500tokens; its ratio to layer latency falls 91.49%→21.30%. Maximum rank modeled compute grows 3.742336→157.194880us.
- Chunk weight span changes 27.358240→26.518320us from 256→12500tokens; its ratio to layer latency falls 82.46%→9.64%. Maximum rank modeled compute grows 3.742336→157.194880us.
- No measured reverse decline occurs in either speedup curve. The reported physical NPU loads are substantially more balanced under UltraEP; increasing Token count amortizes fixed-scale weight cost. Physical Token destinations and traffic distribution also change under the accepted planner, so the layer benefit cannot be assigned entirely to compute from this experiment alone. The measured range does not establish an eventual saturation point.
- Direct is slower at256 and faster at1024 in this fixed model; the crossover is bounded between those sampled points. Chunk already wins at the smallest256-token point, so its lower crossover is not located.
- Direct and Chunk share planned compute loads and quotas. Their difference comes from the accepted weight-transfer graph and its native event dependencies. Consult weight-duration curves together with layer latency; do not assume a universal fixed relay advantage.
- Additional tokens increase modeled expert work while expert weight bytes depend on replica placement, not on token bytes. The successful measurements can therefore amortize weight distribution; replica counts and weight spans are reported explicitly rather than assumed constant.
- Do not infer saturation or high-Token behavior beyond the completed guarded range. A host storage guard is not a simulated network failure or an UltraEP performance result.
- H64/I128 gives only48KiB per expert and128B token payload; real dimensions alter weight volume, TA counts, network cost, GEMM efficiency and memory pressure. Constant utilization and linear per-assignment FLOPs omit real NPU calibration. Fixed200ns planning and100ns reroute do not model their growth with Token count; measured CPU planner wall is separate and cannot be substituted for GPU/NPU planning latency. Results establish this scaled experiment, not real Qwen speedups.

## Event timing and correctness

Layer latency = layer_end − layer_start. Dispatch begins after planning and max(reroute, weight readiness). Each NPU computes only after its assigned token data arrive, and sends combine after its own compute. Different NPUs overlap: global Dispatch/Compute/Combine spans are not disjoint and must not be summed. Target transaction completion still drives chunk readiness and relay/group synchronization; sender completion is not substituted.

Every successful arm passed the retained strict Pair verifier: routing/quota conservation, target payload bytes and segment coverage, weight completeness, chunk dependencies, Top-k results, exact sender callbacks, no early completion and consistent task/Jetty identities. Input hashes and full raw events are preserved. Two-stage is retained and exercised in regressions, not added to the scan.

## Regression results

- build-native-test: PASS (0.50s), guard=None.
- native-tests: PASS (2.26s), guard=None.
- pair-basic: PASS (0.50s), guard=None.
- pair-lifecycle: PASS (13.29s), guard=None.
- pair-nb: PASS (12.54s), guard=None.
- pair-weights: PASS (44.89s), guard=None.
- pair-negative: PASS (3.51s), guard=None.
- old-ultraep: FAIL (14.82s), guard=None.
- Old-suite recovery results (unchanged test assertions):
  - normal: PASS (3.51s).
  - optimized: PASS (3.76s).
  - prior-chain: PASS (104.77s).
- Preserved harness failures: initial lifecycle wrapper requested an 8GiB address-space limit inside the stricter 7GiB outer guard; the isolated wrapper was tightened to 7GiB. The old-suite source snapshot omitted accepted evidence JSON fixtures; config and summary fixtures were restored exactly from accepted Git objects. The 48 completed old scenarios were reused for normal/optimized verification, and the earlier dependency chain was rerun. No simulator code, oracle assertion, or simulated input was changed to recover these harness failures. Full failed logs and fixture hashes remain available.

## Evidence and reproduction

Run `bash experiments/ep64-token-scaling/run.sh` with `NS3_ROOT` and fresh `RAW` as shown in README. Run `regressions.py` separately, after the scan has terminated, never concurrently. Read `data/status.json` and failure resources before choosing a larger reproduction host.

Every finalized generated run is preserved as hashed, split XZ evidence packages; original archive members were read back byte-for-byte before replacing the owned working copy. `restore.py` reconstructs an empty destination and checks every member and transport hash. Routing CSVs and analysis are also directly readable. Raw failure records are retained and explicitly labeled. Source hashes identify unchanged baseline code; new files only orchestrate, validate, package and analyze experiments.

Prior workload profiling motivates orders of magnitude: measured GPQA-main single-request P50≈185tokens (suggested256), Codeforces batch8 P90≈6112 (suggested6144), LongBench Qasper P90≈7646 (suggested7680). This scan uses chosen preliminary points, not exact quantiles; longer real batches exceed its100K-assignment ceiling. Real request lengths do not establish real expert routing. See the accepted `experiments/prefill-workload-profiling/evidence/recommended-token-points.csv`.

The task stops at this delivery for acceptance; no parameter retuning or new protocol optimization is included.

Final independent evidence audit:35 packages,16,096 members and9,591,506,303
uncompressed bytes verified exactly. All21 measurements and7 routing prefixes
were independently recomputed; a restored256-token Chunk case passed the
unchanged strict Pair verifier again. See data/final-independent-review.json.
