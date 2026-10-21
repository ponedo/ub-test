# Completed N256 screening ledger

This ledger was finalized after the unchanged frozen harness completed. The
original private execution ledger and all attempt artifacts remain intact.
Only two formal attempts ran, sequentially, with no retries or other token sizes.

| Strategy | Attempts | Final status | WeightDuration (µs) | Layer latency (µs) | Simulator wall (s) | Simulator CPU (s) | Peak RSS (KiB) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| chunk-streaming | 1 | PASS | 691.082182 | 727.245670 | 577.271775 | 576.966275 | 2,724,044 |
| multicast-v2 | 1 | PASS | 896.326667 | 932.419197 | 475.007116 | 474.750517 | 2,802,784 |

Every case passed input preflight, the simulator/online validation, executed
input/graph postflight, independent integration/network/lifecycle verification,
Roofline integer-oracle verification and aggregate-only postflight. All twelve
per-case guarded receipts report exit 0 with no guard trigger. The shared combine
fingerprint and 4,021 frozen source/runtime/harness identities remain unchanged.

The pair reproduced reversal: MC WeightDuration was 205.244485 µs longer,
29.69899823% slower. This is one tested N256 reproducer, not a global minimum or
repeated-run stability result. Primary details and mechanism discussion belong
in REPORT.md; exact case hashes and checks are in correctness-gates.json and
input-identities.json.

Formal simulator total wall was 1,052.278892 seconds (17.54 minutes), and total
CPU was 1,051.716792 seconds. These figures exclude one-time runtime restoration,
build and ancillary checks. Fresh binaries/host and all-node observation differ
from historical selected-node runs, so no strict historical speedup is claimed.

## Unchanged execution scope

- Real manifest-order N256 prefix, serialized layer 37, shared natural plan.
- 44 replicas, 21 replicated-expert groups, maximum fanout 5.
- Link 3136 Gbps, propagation 20 ns, original allocator service 5 ns.
- Jetty TA window 512, out-of-order ACK window 2048, TP window 1000.
- Roofline 100 decimal TFLOP/s and HBM 2692 decimal GB/s; full Layer.
- All 65 native nodes observed. Impossible source/group selectors suppress only
  selected TA/RTT details. No raw rings are used in the published analysis.
- Fixed per-stage guard: 4,800 s, RSS 6 GiB, address space 7 GiB, host reserve
  1 GiB, output-disk reserve 8 GiB, temporary-disk reserve 2 GiB.
- No failed, interrupted, uncertain or replacement formal attempt occurred.
- No N512/N1024/N2048 run, allocator intervention, window sweep, new execution
  framework, protocol change or new native instrumentation occurred.

## Correctness interpretation

All 128 directed native links conserve packet and byte counts. Transfer-derived
WRITE/TPACK/TAACK totals, all-pair admission/completion/SSN progress, target bytes
and compute results reconcile. MC explicit native retry and injected-test-loss
counters are zero. There is no exported universal drop counter: the report calls
this a no-loss/no-retry consistency contract, not direct measurement of every
possible drop event. Disabled selected RTT counters are not completeness proof.

## Post-run documentation boundary

README.md and this ledger receive administrative completion notes only after
formal execution and independent result review. Published Python harness/runtime
source remains byte-identical to the executed frozen version. The execution
hashes in source-provenance.json continue to identify that version; publication
metadata does not retroactively change approval or execution evidence.
