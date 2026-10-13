# OpenURMA RR/DRR prototype: Phase 1

## Outcome and scope

The official CPU/SystemC build runs. A selectable DRR implementation now lives in the actual `UB_Jetty_Sched.clnp`, compiled by the official OpenClickNP compiler. The default remains RR. The experiment instantiates the generated `SC_doorbell` and `SC_jsched` and measures SystemC events; it is a **scheduler component experiment**, not an end-to-end reliable transport benchmark. No Nano-UB implementation, workload generator, or existing result was changed.

All 20 corrected RR/DRR component checks pass. Native RR has a reproducible full-ring admission loss: six pressure cases fail, preserved as regression evidence. Twelve raw files from four non-overflow scenarios are byte-identical between native RR and corrected RR. Two complete measured runs repeat byte-identically. DRR is slower in this configuration. The mixed-size common-backlog window is too short for a defensible fairness comparison; no DRR fairness improvement is claimed.

## Fixed source and build

- OpenURMA: https://github.com/bojieli/OpenURMA/tree/0ae5dce300154d761f97095864bda0cf2546b265
- OpenClickNP: https://github.com/bojieli/OpenClickNP/tree/c1c6acc58032a1894507d88659b3cca668b0e1a5
- SystemC 2.3.4, official source commit `5fc1469339775b54b1fcc2020ac744a58be5b50e`; GCC 14.2, C++17. CMake 3.22 or newer is needed for OpenClickNP.
- Source provenance and license: `third_party/openurma/UPSTREAM.json`, `third_party/openurma/LICENSE`; both upstream projects use Apache-2.0 for the relevant files. No kernel driver or paper is vendored.
- The overlay is `openurma/elements/protocols/ub/UB_Jetty_Sched.clnp`; the corresponding applicable patch is `patches/openurma/0001-jetty-rr-drr.patch`. Compiler, runtime, protocol headers and other elements are unchanged.

No FPGA SDK, sudo, or gem5 was needed. The official compiler builds with its stub runtime. The official `build_systemc.sh` does not consume its documented `SYSTEMC_HOME` to set g++ include/library paths; the wrapper supplies standard `CPATH`, `LIBRARY_PATH`, and `LD_LIBRARY_PATH` instead of changing upstream build code.

Reproduce from this repository with network access to the two public official repositories:

```sh
# Optional: export SYSTEMC_PREFIX=/absolute/path/to/existing/systemc
# Otherwise bootstrap uses this repository's existing user-directory installer.
# Optional: export CMAKE_BIN=/absolute/path/to/cmake
./scripts/openurma/bootstrap.sh
source .deps/openurma/env.sh
./scripts/openurma/run.sh
```

Default clones are isolated under `.deps/openurma/`. Existing overrides must point to the fixed commits. `OPENURMA_RESULTS` can select another relative output directory. `run.sh` rebuilds both variants, runs official checks, executes all component cases, audits raw events, and regenerates metrics. Recompute only analysis with `python3 -m experiments.openurma.analyze experiments/openurma/results`. Native failure reproduction is an explicit exact scenario list; unexpected successes or failures fail the suite. Native failure results are not included in performance metrics.

## Native behavior and minimal changes

The native scheduler has 16 Initiator rings indexed by `ini_rc_id & 15`; each ring has 32 entries and 31 usable flit slots. It tests one RR cursor slot per handler invocation, including empty slots. It chooses at SOP, then drains the same packet through EOP without preemption. Continuation input flits inherit the most recent SOP's Initiator. Callers must supply contiguous, well-formed WRs. Logical IDs alias above 15; this prototype does not expand or repair that original capacity.

The first flit is `ub_meta`, the next is `ub_ext`; `ub_ext.length()` supplies WRITE payload length. The 64-byte internal `flit_t` carrier contains only 32 bytes of payload per data flit. DRR waits until the extension is queued, then charges the declared WRITE payload length once at SOP selection (zero length costs one credit). Metadata-only and other opcodes cost 64 service credits. Those credits are not a model of READ response bytes or Atomic fairness. Default quantum is 256 bytes; tests set generated `_state.use_drr` before simulation. This is a CPU prototype configuration, not an implemented FPGA host-control register.

Deficit is retained across insufficient-credit visits, reset when a queue empties, and not increased on a Fence-blocked or missing-extension visit. Eligible packets remain on the cursor while credit suffices. A selected packet streams without waiting for its entire body; the 4097-byte regression exceeds the ring capacity and completes. No flit metadata, wire layout, transaction numbering, or non-scheduler element changes.

Native admission used `read_input_port` before checking ring capacity, losing a flit when the ring was full. Both corrected RR and DRR now peek at the existing generated input slot and consume it only when admitted; packet-owner state advances only then. No new queue capacity is added. The overflow fixture completes only 32 of 41 WRs natively; both corrected policies complete all 41. Shared-source head-of-line blocking remains. Output FIFO writes retain the native blocking behavior.

Fence semantics remain the native outstanding Read/Atomic counter per Initiator. These operations increment at SOP dispatch; notifications on port 2 decrement the counter. A fenced WR cannot start while the count is positive. The test injects separate notifications at 200ns and 400ns and checks both prior operations must be released, while an independent Initiator progresses. Notifications are scripted **test stimuli**, not fabricated completion evidence. Native notification identity validation, malformed-input handling (including silently dropped stray continuations), PSN/ACK and retransmission coverage are not strengthened or established by this component experiment.

## Checks and raw evidence

`experiments/openurma/results/validation.txt`, `runs.json`, `native_rr_comparison.json`, and `determinism.json` record the checks. `provenance.json` binds source, patch, generated SystemC and binary hashes to the fixed upstream versions. Individual run directories contain stdout, `component.events.csv`, `component.queues.csv`, and (when the run reaches reporting) `component.wr.csv`.

- Official SW-emulation checks: Fence, multi-Initiator parallel, TX wire, multi-flit WRITE, ROI ordering, ROT ordering: six checks for each build, all 12 return success. These have different pipeline scopes: for example, multi-flit WRITE tests encode/decode/HBM and does not exercise this scheduler.
- Official native SystemC `test_sc_latency.cpp`: one WR posted at 10ns, first wire flit at 35ns, first decoded flit at 39ns, three wire and three decoded flits. Its printed “roundtrip” is first decoded arrival, not a remote CQ or ACK. We do not use its 322MHz conversion as measured hardware performance.
- Component scenarios per policy: smoke; two outstanding Read/Atomic plus Fence; full-ring overflow; two 4097-byte WRs with partial tails; delayed extension; 500ns sink stall; equal and mixed workloads in forward and reverse source order. All 20 corrected runs pass.
- Native component runs: four non-overflow cases pass; overflow, stall and four sustained workload cases fail. This is six preserved expected failures, not six passing native performance runs.
- Every output flit's 64 raw bytes are compared with input, with per-WR flit index, no duplicates/loss, per-Jetty WR sequence, contiguous SOP-to-EOP, completed WR count, drained rings and outstanding counters checked. Test correlation uses reserved carrier fields, unchanged through these two elements; it is not asserted to survive the complete transport pipeline.
- Native/corrected RR comparison covers all three raw CSVs for smoke, Fence, large and delayed-extension cases. Deterministic repeats cover mixed/forward for both policies, all three CSVs each. Event sequence and SystemC delta count disambiguate equal-time events.

## Measurement contract and results

A deterministic source makes all WRs ready at 10ns, then submits complete WR packets round-robin across three Jettys, using either 0/1/2 or 2/1/0 source order. Each Jetty has 96 WRs. Equal sizes are 256/256/256 bytes; mixed sizes are 64/256/1024 bytes. Doorbell/source FIFOs have depth 8, scheduler output depth 1. The sink consumes one flit then waits 4ns. Ring sizes, input ordering, sink, and workload are identical for corrected RR and DRR.

Latency starts at application ready (10ns) and ends when the sink consumes output EOP. It includes source admission pressure. Reported `submit_to_dispatch` separately starts at the first source FIFO write and ends at the scheduler's output SOP offer; this also includes ingress time and is not pure queue residence. Payload drain rate is total payload bits divided by time from 10ns to last EOP consumption. No protocol completion is inferred. Quantiles use linear interpolation at `(N-1)*q`.

The generated SystemC backend waits 1ns per handler invocation and does not implement the element's `.timing { ii = 2; }`. Blocking FIFO operations add actual waits. The following rates describe this explicit simulator/sink configuration, **not NIC or hardware Gbps**.

| Workload | Policy | Source order | Component payload Gbit/s | Makespan ns | P50 ns | P99 ns |
|---|---|---|---:|---:|---:|---:|
| Equal | RR | forward | 48.774 | 12093 | 6068 | 11972.98 |
| Equal | RR | reverse | 48.742 | 12101 | 6073 | 11980.20 |
| Equal | DRR | forward | 48.402 | 12186 | 6113.5 | 12065.11 |
| Equal | DRR | reverse | 48.366 | 12195 | 6120 | 12074.20 |
| Mixed | RR | forward | 54.312 | 19005 | 9512 | 18809.86 |
| Mixed | RR | reverse | 54.289 | 19013 | 9577 | 18832.68 |
| Mixed | DRR | forward | 44.808 | 23036 | 11527.5 | 22798.99 |
| Mixed | DRR | reverse | 44.779 | 23051 | 11620.5 | 22835.01 |

Fairness is Jain's index of actual received payload bytes across the three Jettys; a separate index counts internal 64-byte carriers, not Ethernet wire bytes. We use the longest common interval where all three rings have positive sampled occupancy across BOTH policies and BOTH source orders, earliest tie. Samples are 1ns apart; this is queued-flit occupancy, not a claim of permanently eligible complete WR backlog. Intervals shorter than one full one-WR-per-Jetty sink service round are diagnostic only. This rule is encoded before interpreting the results; no favorable policy-specific windows are used.

Equal workload common window is [258,12016)ns, longer than the 120ns minimum. Payload Jain values: RR forward 0.99998763, reverse 0.99999243; DRR forward 0.99998500, reverse 0.99998743. These finite windows do not establish an improvement. Mixed common window is [3266,3334)ns, only 68ns versus the 192ns minimum, so primary mixed fairness values are null. Per-Jetty latency, full-run byte shares, window shares and explicitly diagnostic short-window indices remain in `summary.json` and each `metrics.json`. Finite full-run shares reflect offered sizes and are not a saturation fairness claim.

DRR is slower here, especially with mixed sizes. One-slot-per-cycle selection, credit rounds, extension availability, and shared ingress pressure constrain this component. No ablation identifies their individual contribution. This prototype does not justify promoting DRR as an improvement, tuning the fixture to obtain Jain near 1, or using an independent analytical scheduler as transport evidence.

## Trace 1.0 adapter feasibility — inspection only

Potential future ingress is `NIC::submit_wr` in `runtime/openurma/include/openurma/openurma_sc_facade.hpp`, backed by `wr_in`; `runtime/openurma/src/openurma_sc_facade.cpp` connects doorbell → scheduler → Initiator ordering → the remaining TX modules. `pop_wire_tx`, `push_wire_rx`, and `pop_cqe` expose different wire/completion boundaries. No Trace adapter or MoE workload migration is implemented.

A later adapter would need explicit validation and mapping:

| Trace concept | Candidate mapping / unresolved requirement |
|---|---|
| Jetty identity | Explicit map into 0..15; reject alias/capacity overflow rather than masking arbitrary IDs. |
| Ready time | SystemC source thread waits until trace time; retain ready and successful submit times separately under backpressure. |
| WR bytes | `ub_meta` + `ub_ext.length/address/token` + 32-byte payload chunks, correct last-flit padding and SOP/EOP. Never interleave different WRs' continuation flits. |
| Sequence / WR identity | Bounded mapping to native transaction fields, including 16-bit TASSN wrap; preserve a separate correlation table instead of assuming reserved test bytes traverse the wire. |
| Dependencies | Release on validated matching CQ/protocol completion, not scheduler EOP or first decoded flit. |
| Read/Atomic Fence | Wire genuine completion notifications back to scheduler port 2. In the inspected SC facade `f_jsched_notify` is declared and bound but has no writer found; do not assume this loop is complete. |
| Destination | CNA routing, peer NICs, memory registration/address tokens, and target completion must be configured and validated. Single local sink has none of these semantics. |

The existing fairness/quantile definitions can be reused only after event boundaries and eligible backlog are made comparable. End-to-end completion, PSN/ACK/retry, multi-destination routing, more than 16 Initiators, and Trace dependency correctness remain unverified. This phase intentionally stops at a reproducible real-element component experiment.
