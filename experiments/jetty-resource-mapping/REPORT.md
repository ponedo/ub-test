# Jetty resource mapping: native index validated, shared-Jetty gate stopped

Status snapshot: 2026-10-16, after fresh 5K/10K/20K/50K A/B timing runs. The 50K sampled and scoped-timer runs and offline profile analysis are complete, with exact output parity for every diagnostic run. This report does not authorize further runs.

## Findings

1. **Task 1 passes its correctness gate.** The native reverse-index change passes all 44 available native unit suites after correcting the test working directory, the existing application regression chain, and fresh A/B comparisons at 5K, 10K, 20K and 50K accepted assignments. Each comparison preserves all 398 output files byte-for-byte, including payloads, timed events and summaries.
2. **Host simulator cost falls in these measured single trials.** At 50K, simulator wall time changes from 370.124 s to 105.556 s and user-plus-system CPU from 369.915 s to 105.362 s. Simulated layer latency remains exactly 1,353,604,768 ps. This is a host implementation improvement; it is not a model, network, or MoE speedup claim.
3. **Task 2 is stopped at its native capability gate.** Original A and indexed B both fail concurrent multi-segment WQEs on one Jetty: WQE 1001 receives its sender callback before all of its target execution completions. Both controls pass. All payload bytes ultimately validate, with no observed payload loss. Pair-Jetty application mapping and C measurements were not implemented or run. 100K was deferred at the capability blocker.

## Controlled comparison and provenance

The predeclared [experiment plan](experiment-plan.md), [matrix](matrix.yaml), and [command manifest](command-manifest.yaml) distinguish:

- A: preserved original native per-WQE mapping and lookup.
- B: the same application mapping, with native TP-to-Jetty reverse-index candidate selection.
- C: proposed application-level pair-Jetty reuse on indexed native libraries; blocked by the capability failure.

Native baseline: `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`.
Native implementation commit: `eda2fd75bfd1a37b28917b3ebbe721bade5f91ae`.
The standalone [native patch](tpn-jetty-index.patch) contains only `ub-transaction.cc`, `ub-transaction.h`, and focused assertions in `ub-test.cc`. It can be reviewed independently of this application experiment. The separately retained [native instrumentation patch](evidence/native-index-timing.patch) and [application timing patch](evidence/app-timing.patch) are diagnostic artifacts, not part of the native optimization commit or uninstrumented timing controls.

Raw artifacts are under `/workspace/scratch/c6ba02920254/jetty-mapping-raw`. Each attempt retains invocation, environment, input and source hashes, frozen executable/library hashes, guarded resource records, strict-verifier results and output hashes. A and B binaries/libraries were frozen separately before instrumentation. The shared-Jetty applications were compiled separately against ABI-matched A and B headers/libraries; their recorded `ldd` outputs identify the actual libraries.

Inputs preserve EP64/E128/top-k8, exact accepted assignments, no-balancing synthetic prefill inputs, seed, graph, routing, topology, WQE/TA semantics, explicit payloads, computation, logging and verification. Fresh A controls were run at each completed size; historical timings are not substituted. The unchanged guard and verifier code remain authoritative. Runs and builds are serialized. See the raw append-only `run-ledger.jsonl` and each `attempt.json` for actual execution status.

## Task 1 architecture and semantic coverage

`GetJettiesUsingTpn` keeps its API and its final live-transport/Jetty filtering. Instead of scanning every Jetty binding, it builds an ascending unique candidate set from:

- Direct TPN → ordered Jetty IDs.
- TPG local ID → ordered Jetty IDs, composed with the Controller's existing canonical TP → TPG membership index.

The second level deliberately reuses the existing membership authority rather than introducing new add/remove/rollback hooks. Canonical references and the unchanged `GetJettyLiveTps` path still check exact live generations. No cached owning TP/Jetty pointers are added. The index is maintained after successful bind/rebind, removed on unbind/destruction, and cleared on disposal. Failed binding attempts preserve the previous association.

The focused differential test compares results with the old full ordered scan over every fixture Jetty after each transition. Coverage includes direct and shared-group users of the same TP, ascending order and uniqueness, unrelated/missing TP queries, dynamic member addition/removal, RETIRING and frozen-but-live members, direct/group rebind transitions, failed rebind, idempotent unbind, Jetty destruction and same-number recreation, group destruction, draining endpoints, and endpoint generation reuse without resurrecting an erased binding. Existing lifecycle tests additionally check that pending last-member removal retains its live reverse binding and that replacement immediately removes the old member and exposes the new one.

Scope is candidate selection only. Packet/protocol algorithms, ACK handling, event scheduling, model/planner behavior and lifecycle lookup algorithms were not changed. Per-candidate live TPG materialization remains; this is not a general elimination of all lookup or lifecycle costs.

## Validation and retained failed attempts

See [gate evidence](evidence/gate1/README.md), [RTP resolution log](evidence/gate1/rtp-resolution.log), and the [correct-cwd native suite logs](evidence/gate1/native-unit-correct-cwd/).

- Final native result: **44/44 suites pass** from the native checkout working directory, including `unified-bus-rtp-resolution`, `unified-bus-lifecycle`, and `unified-bus-jetty-inflight`.
- The first aggregate invocation was rejected by the ns-3 runner because suites must be invoked separately. The initial separate-suite run from the workspace passed 43/44; `unified-bus-link-fault-input` failed its existing relative `scratch` path fixture. All 44 were rerun from the native checkout and passed. Initial logs/results are preserved; the report does not silently relabel them as successes. No test oracle was altered to resolve these invocation errors.
- The existing application regression chain passed. [Relay test results](evidence/gate1/relay-tests.json) retain 120 public oracle cases, order/load-sensitive checks, and expected live-fault rejection results. [Regression console](evidence/gate1/regressions-console.txt) and [relay ledger](evidence/gate1/relay-run-ledger.json) retain the chain's commands and outcomes.
- The isolated regression snapshot changed only bootstrap revision pins and support for a worktree `.git` file; its [bootstrap-only diff](evidence/gate1/bootstrap-only.patch) is retained. Existing regression logic/oracles were reused.
- Fresh A/B strict verification and complete 398-file parity pass at 5K, 10K, 20K and 50K. Separate 5K instrumented A and B runs each also preserve all 398 files against their own uninstrumented reference.

## Measurements available now

Authoritative final measurement tables and source hashes (14 successful attempts and 10 complete 398-file parity checks; C and 100K remain unrun): [measurement snapshot](evidence/measurements-final/README.md), [resources](evidence/measurements-final/resources.csv), [counters/timers](evidence/measurements-final/counters-and-timers.csv), [parity](evidence/measurements-final/parity.csv), and [measured curves](evidence/measurements-final/curves-partial.svg).

| Accepted assignments | A wall s | B wall s | A CPU s | B CPU s | A/B output parity |
|---:|---:|---:|---:|---:|---|
| 5,000 | 6.020 | 3.513 | 5.810 | 3.292 | All 398 files identical |
| 10,000 | 18.308 | 9.029 | 18.192 | 8.778 | All 398 files identical |
| 20,000 | 64.954 | 23.567 | 64.868 | 23.514 | All 398 files identical |
| 50,000 | 370.124 | 105.556 | 369.915 | 105.362 | All 398 files identical |

These are simulator-stage wall and user-plus-system CPU measurements, not total experiment-driver time. RSS and invariant counts are in the CSV. Exact 50K metadata is retained in `50000-A-timing/attempt.json` and `50000-B-timing/attempt.json` under the raw root:

| 50K measurement | A | B |
|---|---:|---:|
| Simulator wall seconds | 370.12387856200803 | 105.55579833098454 |
| User CPU seconds | 367.571366 | 103.916184 |
| System CPU seconds | 2.343662 | 1.445485 |
| Peak RSS KiB | 1,997,008 | 2,002,052 |
| Strict-verifier wall seconds | 53.17486280796584 | 49.899311490007676 |
| Strict-verifier status | PASS | PASS |

Both 50K outputs retain 98,386 remote WQEs, 98,386 target TAs, 4,487,239 simulator events and 6,250 completed tokens. Simulator events are the native event count from `simulator-metrics.json`, not the separately counted application event-trace rows. The recorded host has `MemTotal: 10206508 kB` (approximately 9.73 GiB, a roughly 10-GiB host), nine allowed CPUs and no swap. These fresh measurements must not be described using an older 16-GiB environment. Single trials do not establish statistical significance. The small RSS increase in B is visible in the records and must not be described as a memory reduction.

At 5K, diagnostic instrumentation records 36,736 lookup calls on both sides; binding records examined fall from 9,952,287 to 269,080. Measured Jetty creation calls remain 9,850 on both sides, as expected for unchanged per-WQE mapping. Scoped lookup thread CPU changes from 2.009 s to 0.340 s. These separately instrumented timers support attribution but are not unbiased end-to-end timings or sampling percentages; inclusive scopes must not be added together.

### Completed 50K diagnostic runs

Both sampled runs and both scoped-timer runs passed strict verification and preserved all 398 files exactly against their own uninstrumented timing controls. Raw `50000-{A,B}-{sampled,instrumented}/attempt.json` records and instrumented `timing.tsv` files retain the exact measurements. The [final measurement snapshot](evidence/measurements-final/README.md) consolidates these with the completed timing matrix.

| Diagnostic run | Wall seconds | Same-arm control seconds | Observed wall difference | Output parity |
|---|---:|---:|---:|---|
| A sampled | 358.966777025 | 370.123878562 | -3.014% | All 398 files identical |
| A instrumented | 367.812166832 | 370.123878562 | -0.625% | All 398 files identical |
| B sampled | 106.095898863 | 105.555798331 | +0.512% | All 398 files identical |
| B instrumented | 116.350238549 | 105.555798331 | +10.226% | All 398 files identical |

The negative A differences are single-trial run-to-run noise, not evidence that profiling makes the simulator faster. B's scoped instrumentation changes wall time by approximately +10.2%, so its instrumented end-to-end time must not replace the clean B control. Sampling and scoped instrumentation use separate runs; observed differences are not calibrated overhead estimates or statistically established effects.

| 50K instrumented metric | A | B |
|---|---:|---:|
| `GetJettiesUsingTpn` calls | 327,148 | 327,148 |
| TPN lookup binding records examined | 893,007,851 | 22,726,174 |
| TPN lookup transport entries compared | 893,007,851 | 22,726,174 |
| Matched Jetty results | 22,726,174 | 22,726,174 |
| Lookup scoped thread CPU ns | 275,586,784,853 | 39,318,569,389 |
| `ResolveWqeLifecycleLocalId` calls | 98,386 | 98,386 |
| Lifecycle lookup scoped thread CPU ns | 17,134,813,362 | 17,882,262,737 |
| Jetty creation calls | 98,386 | 98,386 |

The binding-record work decreases by **97.46%** while query count and matched results are unchanged. Lifecycle lookup and Jetty creation remain outside the optimization scope; unchanged call counts and the roughly 17–18 s lifecycle scope are explicit residual costs. These are measured scoped thread-CPU durations and exact counters, not sampled CPU percentages. Scope overlap and instrumentation perturbation prevent adding inclusive timers into a total or treating their change as a separately calibrated causal speedup.

### Completed 50K sampled profiles

The main simulator thread was sampled at 99 Hz using user CPU-clock events and 8-KiB DWARF user-stack capture, decoded with the existing official `perf` decoder and previously calibrated collector. Percentages count each SAMPLE record once, never its sampling period. A has **35,283 samples** and B has **10,160 samples**. The runs are separate from the scoped-timer runs above.

| Observed stack-membership path | A samples / share | B samples / share |
|---|---:|---:|
| `GetJettiesUsingTpn` | 27,097 / 76.79903% | 3,605 / 35.48228% |
| `ResolveWqeLifecycleLocalId` | 1,602 / 4.54043% | 1,455 / 14.32087% |
| `CreateJetty` | 25 / 0.07086% | 21 / 0.20669% |
| `SubmitWqe` | 1,685 / 4.77567% | 1,541 / 15.16732% |

The indexed lookup remains material: it still merges candidates and executes the preserved live-transport/generation checks, including candidate `GetJettyLiveTps` work. Lifecycle and submission occupy larger fractions of the shorter B run; that fraction change does not establish an increase in absolute lifecycle cost. The independent scoped durations above are approximately 17–18 s for lifecycle resolution and were not optimized.

Coverage limits are explicit. Unknown leaf/self samples are **603/35,283** for A and **616/10,160** for B. Samples containing any unknown frame are **35,246/35,283** and **10,120/10,160**, predominantly involving outer frames. No LOST, LOST_SAMPLES or THROTTLE records were reported, and no samples lack frames; this does not guarantee complete stacks or complete capture. The table measures observed stack membership, not exhaustive attribution. Inclusive categories overlap and must not be added. Unknown frames remain in denominators and retained artifacts.

The only missing mapped pseudo-file is `//anon`; real mapped ELFs are retained in the symbol snapshots with hashes. System ELF copies were taken after capture, so their retention alone does not prove that every system mapping was unchanged during capture.

Profile evidence:
- A: [summary](evidence/profiles/A/summary.json), [self Top 20](evidence/profiles/A/self-top20.svg), [inclusive Top 20](evidence/profiles/A/inclusive-top20.svg), [self CSV](evidence/profiles/A/self-top20.csv), [inclusive CSV](evidence/profiles/A/inclusive-top20.csv), [folded stacks](evidence/profiles/A/stacks-count.folded.gz), [symbol manifest](evidence/profiles/A/symbol-manifest.json).
- B: [summary](evidence/profiles/B/summary.json), [self Top 20](evidence/profiles/B/self-top20.svg), [inclusive Top 20](evidence/profiles/B/inclusive-top20.svg), [self CSV](evidence/profiles/B/self-top20.csv), [inclusive CSV](evidence/profiles/B/inclusive-top20.csv), [folded stacks](evidence/profiles/B/stacks-count.folded.gz), [symbol manifest](evidence/profiles/B/symbol-manifest.json).

The raw root retains per-attempt input/output/ELF hashes, commands, resource metadata, raw `perf.data`, timing TSVs and decode symbol snapshots. [Evidence collection](collect-evidence.py) copies small source records and produces a size/SHA256 raw manifest; [small-evidence packaging](package-small-evidence.py) prepares portable records. Reproduction is specified by the [manifest](command-manifest.yaml), [harness instructions](README.md), and the native capability [reproduction script](run-shared-jetty.sh). Archive packaging is separate from the completed measured results. C and 100K entries are explicitly unrun, not missing zero-cost observations.

## Task 2 native capability failure and reproducer

The [probe description](shared-jetty-probe.md), [standalone source](shared-jetty-probe.cc), and [reproduction script](run-shared-jetty.sh) provide a bounded MRE using production APIs. The fixture uses two nodes, a direct link, paired RTPs and one sender Jetty. It submits WQEs 1001/1002/1003 concurrently without whole-WQE serialization, each with four 1,024-byte fragments and a 32-byte tail; WQE 9001 is submitted later on the same Jetty. The target executor deliberately delays completions. Independent payload records encode WQE ID, absolute byte offset and fragment length; verification does not derive offsets from contiguous SSNs.

| Probe mode | Original A | Indexed B |
|---|---|---|
| Single multi-segment WQE | PASS | PASS |
| Concurrent single-segment WQEs plus later reuse | PASS | PASS |
| Concurrent multi-segment WQEs plus later reuse | FAIL | FAIL |

Retained [A events](evidence/shared-jetty/A-concurrentmulti-events.csv), [B events](evidence/shared-jetty/B-concurrentmulti-events.csv), [A summary](evidence/shared-jetty/A-concurrentmulti-summary.txt) and [B summary](evidence/shared-jetty/B-concurrentmulti-summary.txt) show the same violation: WQE 1001 owns SSNs 0, 3, 6, 9 and 12; its sender callback is at **70,309 ns**, preceding its SSN 9 target completion at **70,335 ns**. Peak outstanding WQEs is 3. All four WQEs ultimately receive one callback and all five target fragment completions; all explicit payload bytes validate. The evidence supports early completion, not observed data loss.

The native WRITE rule in `src/unified-bus/model/protocol/ub-transaction-rules.cc` requires a response; `ShouldCompleteOnTpAck` does not allow transport-ACK-only success, and the transaction path produces the TA response after target execution completion. Source analysis points to interleaved SSN ownership conflicting with the contiguous-range assumption in `UbJetty::IsWqeCompleted`, followed by terminal cleanup of outstanding segments. Intermediate UNA advancement is an inference from the source, not an independently recorded observation. Final `sndUna == sndNxt == 20` cannot prove genuine ACK reclamation because terminal cleanup also marks outstanding sequence bits.

The failure occurs on both revisions and therefore is not evidence of an index regression. It invalidates the assumed shared-Jetty capability required for Task 2. No protocol completion repair, ACK workaround, or whole-WQE serialization was introduced. The reproducer script's successful overall exit means the expected failure reproduced, not that shared-Jetty capability passed.

## Decision boundary and limitations

Accept the independent native index patch on the completed correctness evidence. Keep the original application per-WQE Jetty mapping. The authorized 5K–50K A/B timing and 50K diagnostic comparison is complete. Shared-Jetty mapping needs a separately scoped native semantics investigation and approval before it can be reconsidered.

The completed results cover this fixed synthetic workload/topology and measured sizes, not every workload or a production MoE implementation. Simulated latency is unchanged in A/B by exact event/output parity. No task fusion, payload packing, load balancing, lifecycle redesign, or 100K capacity result is claimed.

## Delivery and reproduction checks

The [archive manifest](evidence/archives/archives.json) inventories exact fixed inputs, raw event CSVs and compressed original CPU profiles. [Run records](evidence/runs/) preserve measurement/verification/parity metadata and a full SHA-256 raw-file manifest. Full payload trees and exact mapped ELF copies remain retained on the host; they are not duplicated in Git. Raw profile decoding needs matching binaries; folded symbolized stacks and hotspot tables are provided independently.

The delivered native suite script was executed again: [44/44 passed](evidence/native-runner-repro/results.json). The [complete shared-Jetty reproduction script](evidence/shared-jetty-script-repro/reproduction-check.txt) passed its expected-failure oracle, reproducing all original event/summary/exit files exactly. Its initial library-location preflight failure is retained and explained in [reproduction notes](evidence/shared-jetty-script-repro/README.md); explicit frozen library search fixes the bootstrap check, not native protocol behavior. Synthetic harness self-tests also passed (parity, duplicate/payload rejection, binary identity checks).
