# Qwen256 Chunk Streaming Relay CPU diagnosis

## Main finding

Chunk is CPU-expensive in several distinct places: repeated dependency reconstruction dominates both Python stages and native initialization; online group-ready auditing adds repeated whole-weight-task scans; native per-Jetty retry/eligible-operation processing grows substantially in the sampled Chunk window. Direct avoids the graph-scan costs but still spends substantial CPU generating and validating every payload byte. The leading shared map lookup samples mostly belong to application metadata lookups, not native WQE processing. The 300-second Chunk timeout remains an incomplete simulation, so no completed Chunk latency or full-run speedup is claimed.

## Scope and evidence rules

This milestone diagnoses the accepted Qwen256 timeout. No optimization, native fix, planner/model/network/compute/relay/submission/TA change, or validation weakening is included. All large simulator measurements use summary logs, pair Jettys and the exact accepted input: EP64, E128/top-k8, H2048/I768, Zipf1.1/seed20261016, TA1024, chunk4096, 100Gbps/20ns. The native Release build stays `-O3 -DNDEBUG -g`; standalone application stays `-O3 -g`. Sampling uses the exact accepted executable, not the diagnostic copy.

The original application tree is `0efaad701fc10655f045d15785949b0d198722a7`, local commit `6f837d47d8f96508ed53f3602d887f95397c4fae`, equal to accepted remote `2a83d257ba13268937e605395ec6f70566dd8ef8`. Native commit/tree remain `2fde39d02920e639f5b200d0c5262a517326deb8` / `c27d1faef570e6da9900a71aa0a37180a58dfba8`. See `evidence/build-provenance.json` for exact source/ELF hashes.

Stages are distinct:

1. Python Preparation: planner and execution/config/graph generation.
2. Python independent Preflight: reconstruct and verify accepted plan/input/graph.
3. Simulator process: Read/init, Topology, Simulator::Run including online Audit/Validate, then terminal FinalAudit and cleanup.
4. Independent Postflight: input/plan/graph verification with the completed simulator fingerprint.
5. CPU-profile decode/reporting: excluded from all above run timings.

A guarded Chunk run is partial, not a valid layer-latency point. Its partial CPU distribution cannot be treated as a whole completed run, and it has no successful terminal FinalAudit/Postflight unless explicitly recorded.

## Fresh controls and observer perturbation

All rows below are fresh serialized simulator runs on the same host and exact prepared inputs. Guard wall includes process collection granularity; sampled process-tree CPU includes recorder overhead. These are single observations, not confidence intervals.

| Case / observer | Guard wall (s) | Process CPU (s) | Peak RSS (KiB) | Completion |
|---|---:|---:|---:|---|
| chunk-streaming-control | 300.341 | 300.099 | 1532592 | Partial, wall guard |
| chunk-streaming-sampled | 300.442 | 300.482 | 1531844 | Partial, wall guard |
| chunk-streaming-timed | 300.339 | 300.071 | 1536244 | Partial, wall guard |
| direct-control | 113.059 | 112.909 | 1656320 | PASS |
| direct-sampled | 114.094 | 114.067 | 1656320 | PASS |
| direct-timed | 105.790 | 105.658 | 1656296 | PASS |
| no-balancing-control | 2.258 | 2.211 | 144196 | PASS |
| no-balancing-timed | 2.258 | 2.213 | 144188 | PASS |

Direct sampling/control wall ratio is1.0092× (+0.92% observed); timer/control ratio is0.9357× (-6.43% observed). The timer build running faster is instrumentation/code-layout/host perturbation, not an implemented optimization. A single ordered pair cannot isolate profiler overhead from run variance. No Balancing's rounded2.258s wall is guard-poll quantized; its process CPU is2.211s control versus2.213s timed. Chunk's three wall times all hit the fixed cap, so their ratio cannot estimate overhead or equal progress.

Completed Direct control/sample/timed results and No Balancing control/timed results all have identical stable full summaries versus accepted output. Direct retains12.690087432ms/23,536,027 events; No Balancing retains7.957270688ms/819,877 events. Whole-process event rates are208,452 events/CPU-second for Direct control and370,868 for No Balancing control; these include initialization and terminal audit, unlike the separately labeled partial Chunk Run-only rate.

Independent Postflight passed for all five completed large runs (each about0.252s guarded wall; user CPU0.081–0.198s), including exact executed-graph fingerprints. This is separate from simulator online Audit and terminal FinalAudit. Chunk has no completed Postflight. All13 accepted fault injections also retained expected rejection with diagnostic observers disabled and enabled. See `evidence/postflight.json`, `completed-large-parity.json`, and the two fault evidence files.

## Actual sampling method and calibration

User-only `perf_event_open` CPU-clock permission succeeded with existing settings. No security setting was changed. The recorder captures user IP, registers and 8KiB user stack at19Hz. DWARF decoding uses the same retained ELF files. The sample tables count one per SAMPLE record, never inferred counts or period-weighted percentages. Inclusive membership deduplicates recursive symbols but overlaps across ancestors; do not add it.

The known-hot-loop calibration passed:65 samples,100% leaf attribution to the known hot loop, five-frame callstacks, no unknown leaves, sample period/user CPU ratio0.9965, and one PID/TID. No lost/throttle records were observed. That observation does not prove zero sampling loss; stack truncation/unresolved frames remain possible.

The first unchanged-binary Chunk sample ended at the unchanged300s wall guard:300.44s observed wall,5,690 samples,1,531,844KiB max RSS. The perf header was finalized after SIGTERM, so partial samples and recorded loss counters remain decodable. Unknown leaf frames were154/5,690 (2.71%). At least one unresolved frame appeared in5,126/5,690 stacks (90.09%), often a libc ancestor; this is not90% unassigned leaf CPU. Inclusive attribution is limited to observed frames, and missing ancestors can undercount subtrees. `evidence/samples-chunk/` contains Top20 self/inclusive CSV/SVG, representative callstacks, loss/unknown/depth scope and caller attribution.

Observed inclusive stack membership over this **partial300s window**:

| Stack | Samples | Share |
|---|---:|---:|
| Layer::Read |2,201|38.68%|
| DefaultSimulatorImpl subtree |3,485|61.25%|
| Layer::Audit |335|5.89%|
| Layer::Validate |338|5.94%|
| Layer::Send |788|13.85%|
| Layer::Ready |428|7.52%|
| Layer::FinalAudit |0|Not observed; no terminal-completion evidence|

Read and Simulator scopes approximately partition the captured lifetime; the other rows overlap inside runtime callbacks. This evidence rejects a simplistic “all300s was online Audit” interpretation.

The two leading leaf symbols are const/non-const `map<uint32_t,uint32_t>::lower_bound`:1,932/5,690 samples (33.95%). Shared STL leaves are not assigned to native WQE handling by their names. Their observed enclosing app contexts are Read1,335, Send217, Validate176, Audit190 and Other14. The nearest application/UB caller is Layer::P for1,847 of those samples; Layer::Validate accounts for66. Thus these leading map leaves predominantly reflect application physical-metadata lookup.

Native `UbTransaction::TryContinueJettyTransmission` has361 self samples (6.34%) and1,550 inclusive samples (27.24%); the inclusive subtree includes native work and callbacks. `EnqueueRtpWqe` has134 self samples (2.36%) and712 inclusive samples (12.51%). These are observed costs worth comparing with Direct, not proof that all their descendant CPU is queue maintenance.

## Python stages: complete actual measurements

Preparation completed in203.594s wall,202.781s user CPU/0.838s system CPU,196,644KiB RSS. Its dependency-construction statement took196.070s wall/196.030s process CPU:96.3% of guarded stage wall. Chunk JSON writing took2.883s, graph-tool CSV parsing0.191s and weight transfer construction0.087s.

Independent Preflight completed in196.794s wall,106,304KiB RSS. Its duplicate dependency-reconstruction statement took195.328s wall/195.296s process CPU:99.3% of guarded wall. Native graph-tool wait was0.024s, independent planner verification0.090s, CSV parse0.234s, canonical graph serialization0.235s and fingerprint return0.245s.

These are full-size profiles, not small-case extrapolation. cProfile’s CPython3.12 inline-comprehension self attribution alone points at adapter emit/check functions; unchanged-statement timers locate the actual loop. cProfile uses wall time, subprocess internals are excluded, and parent waits are explicitly separated from Python compute. Fresh preparation bytes match accepted inputs except planning timing telemetry; fresh preflight PASS result/fingerprints are exactly equal. See `python-stages/` for Top20 self/cumulative/calls, callpaths, stage evidence and parity.

Historical unprofiled202.066s Preparation and214.112s Preflight controls are labeled historical, not fresh pairs. Ratios1.008× and0.919× cannot isolate profiler overhead or establish a speedup.

## Structural counts, not CPU percentages

The accepted graph has51 replicas,62,232 weight WQEs,470,016 weight TAs and481,296,384 bytes (459MiB) of transferred weights. Of those tasks39,168 require relay dependencies; only78,336 dependency links are emitted. A complete all-pairs reconstruction visits2,437,502,976 candidates. Python adapter and independent checker each perform that pass separately; C++ Read contains an analogous scan.

The graph contains11,520 distinct group-ready keys. A complete current Audit group scan would visit716,912,640 weight-task candidates;51 final weight scans would visit3,173,832. These are **potential full-execution counts derived from the graph**. Only explicit diagnostic counters establish how many were actually visited before a cutoff. Do not substitute these totals for partial-run actual counts.

Direct carries the same weight bytes and weight TA count with51 weight WQEs and no relay-group dependency scans. Therefore “more WQEs” is incomplete: Chunk introduces repeated graph searches and per-group audit scans, many more per-task state/payload objects and native queue/lifecycle transitions, while retained byte validation and most TA/packet work remain substantial in both. Neither incomplete Chunk latency nor a host CPU improvement can be inferred from task counts.

## Instrumentation validity

The generated diagnostic copy adds nested process-CPU timers, counters and safe checkpoints only. Pinned-source reverse-erasure returns the exact baseline bytes; all11 Simulator control expressions remain byte-exact and ordered. The SIGTERM handler only sets a flag. The next safe normal boundary writes active inclusive/self scopes and partial progress, then exits without adding or rescheduling simulated events.

Four existing fixtures each passed summary and full-debug parity (eight paired checks). Full event timestamps/order, TA identity, executed graph, payload bytes and indices are byte-identical. All stable JSON fields including log level, simulated layer time, event/TA/WQE/packet/byte totals and payload/graph fingerprints match; only `verification_wall_ns` is excluded. Source proof is not a substitute for these execution checks. Small parity does not prove that two large wall-cutoff runs reached identical progress.

Timers include counter/clock/callback instrumentation costs, except explicitly subtracted snapshot serialization CPU. Instrumentation can alter optimization layout and measured speed in either direction even with identical optimization flags; its CPU percentages are separate from unchanged-binary samples. No claim of optimized performance is made.


## Diagnostic Chunk partial phase/counter cross-check

The separate timer build stopped at300.34s guarded wall (terminal snapshot300.071s),1,536,244KiB RSS. The snapshot includes an active Audit call inside the still-running Simulator::Run. It is not a completed layer.

- Read88.689s CPU, including dependency reconstruction88.386s, transfer allocation0.174s and replica-buffer allocation0.126s; InitAudit0.009s; Topology0.077s.
- Simulator::Run211.154s inclusive CPU. Its self151.116s excludes explicitly instrumented app children but still contains native work and other app callbacks; it is **not pure native CPU**.
- Audit19.956s inclusive, including group scans18.051s and weight scans0.012s. Send42.644s inclusive/24.441s self; Validate15.438s; Ready27.884s inclusive/0.202s self. These nested inclusive values overlap.
- FinalAudit, summary writing and cleanup had zero calls at this cutoff. Snapshot serialization CPU before the terminal snapshot was0.086s. Other instrumentation costs remain included.

Actual counters at the cutoff, distinct from planned totals:

| Counter | Actual executed/observed |
|---|---:|
| Initialization dependency candidates |2,437,502,976|
| Accepted dependency links |78,336|
| Group audit events/candidate visits |9,990 /621,697,680|
| Final-weight audit events/candidate visits |33 /2,053,656|
| Simulator events |18,847,458|
| Simulated time |3,580,406,040ps =3.58040604ms|
| Remote WQEs submitted/planned |57,642 /66,122|
| TA admissions |391,636|
| Sender completions |35,852|
| Completed tokens |0|
| Pending replica weights |18|
| All-port transmitted/received packets |3,132,615 /3,132,587|
| Payload bytes generated/validated |462,495,744 /400,977,920|

The event rate is89,259 events per measured Simulator::Run CPU second, or62,822 per process CPU second including initialization; these are **partial-window** rates. The JSONL history and `runtime-progress.csv` preserve intermediate phase/event counters. All-port packet/byte counts include switch ports and protocol traffic; they are not unique end-to-end payload counts.

Read’s total timer88.689s (dependency scope88.386s) differs materially from the unchanged-binary sample’s Read membership (2,201/5,690 samples, approximately116s of a300s CPU window). The timer build changes generated code and adds observers; host/run variation and instrumentation/code-layout perturbation are not isolated by those two measurements. Do not treat the difference as an optimization, a portable speedup, or a calibrated subtraction from baseline. The exact baseline sample is primary CPU attribution; timer/counter data corroborate phase boundaries and actual loop work.


## Direct completed sampling comparison

The unchanged Direct executable completed in114.09s guarded wall, with2,158 samples and1,656,320KiB maximum RSS. It executed23,536,027 simulator events and485,576 total TAs (weight470,016 plus assignment traffic), used3,941 remote WQEs and retained the exact12,690,087,432ps layer latency. Every stable full-summary field matches the accepted result, including graph/payload fingerprints and per-node packet/byte totals. Sampling therefore did not change this completed deterministic model result.

Direct observed stack shares are FinalAudit23.96%, Validate20.11%, Send23.22%, online Audit0.60%, and Simulator subtree75.58%. Read had no captured sample; that means below sampling visibility, not zero initialization cost. The leading map<uint32_t,uint32_t> lower-bound leaves total783/2,158 (36.28%): Send297, Validate231, FinalAudit240, other15. This is a byte-generation/validation metadata path, unlike Chunk's large Read scan contribution. Direct's unknown leaf count is79/2,158 (3.66%); any-frame unresolved count2,123/2,158 (98.38%). The same inclusive-unwinding caveats apply.

Native TryContinueJettyTransmission membership is39/2,158 (1.81%) in completed Direct versus1,550/5,690 (27.24%) in the partial Chunk window. These different observation windows prevent a clean whole-run CPU ratio, but both the callstacks and source identify extra Chunk pressure. At native `src/unified-bus/model/protocol/ub-transaction.cc:823–861`, each retry walks the current Jetty's operation-map range, builds an eligible-WQE vector and calls EnqueueRtpWqe for each member. `:1400–1436` then performs operation/queue lookups and queue-state checks. This work scales with the sum of live operations visited across retry callbacks, not merely total bytes or WQEs once. The Chunk graph plans2,304 weight WQEs on each chunked weight pair, versus one Direct weight WQE; actual instantaneous live-set sizes and native loop visits were **not counted** in this milestone. This is a source-backed complexity mechanism supported by CPU sampling, not a fabricated native iteration measurement.

The existing accepted Jetty lookup/index fix is still in place. These profiles do not imply that its TP-to-Jetty lookup regressed: the separate within-Jetty operation/retry loop is a different path.


## Completed Direct diagnostic phases

The separate diagnostic Direct run completed in105.79s guarded wall and1,656,296KiB RSS. Read consumed0.243s process CPU (dependency reconstruction0.000037s), Simulator::Run77.382s inclusive, and terminal FinalAudit27.634s. Within Run, Send20.443s inclusive/20.441s self, Validate18.180s and online Audit1.382s are measured; Run self37.375s remains residual uninstrumented work. FinalAudit's substantial completed Direct cost shows why its absence from the partial Chunk window must not be interpreted as free validation.

Direct actually generated and validated498,073,600 transfer bytes, then FinalAudit checked498,073,600 task bytes plus481,296,384 replica-buffer bytes. Every stable completed-summary field matches the accepted result. The final diagnostic Simulator::Now is10 seconds because the unchanged application schedules a10-second stop; it is not the layer latency, which remains12.690087432ms. Event-rate tables use process CPU, and the partial Chunk rate separately uses its measured Run CPU.

## Packet, buffer, copy and allocation coverage

Observed Packet and Buffer stack memberships are69/5,690 (1.21%) and42/5,690 (0.74%) in partial Chunk, versus72/2,158 (3.34%) and43/2,158 (1.99%) in completed Direct. They overlap and include descendants. These are CPU-sample shares, not packet counts. Native transaction processing includes TA callbacks and cannot be read as exclusive TA cost.

Explicit Chunk memcpy PLT leaves account for19 samples (0.33%). Allocation/free leaves are visible (Chunk malloc228 and cfree278; Direct malloc143 and cfree193), but these shared leaves alone do not identify the owning data structure. Inlined byte loops, unrecognized libc leaves and unobserved frames prevent a complete copy-cost partition. No claim that all copies are negligible or that unknown libc CPU is memcpy is justified. Exact generated/validated byte counters and all-port packet counts complement these limited sample attributions; a future targeted allocation/copy study would need caller-qualified counters or symbols.

## Three future optimization candidates, not implemented

1. **Index immutable dependency and audit membership.** Python adapter `experiments/multi-npu-relay/adapter.py:39–46`, independent preflight `experiments/tiered-logging/preflight.py:112–118`, C++ `experiments/pair-jetty/pair-layer.cc:158–173`, and `online-validation.inc:69–73` repeatedly scan all weight tasks. Ordered membership indexes could change dependency work from O(RW) toward expected O(W+R+D), and group checks from O(GW) toward O(W+matched memberships). Preserve task-list dependency ordering, every source-coverage/readiness/timing assertion, and independent checker derivation. Incorrect membership or order could silently weaken validation or change dispatch order.
2. **Cache immutable physical metadata outside byte loops.** `pair-layer.cc:70,91–92,275,284–287` and `online-validation.inc:88–92` repeatedly resolve checked physical IDs. Resolving immutable metadata once per relevant task could change repeated lookup work from O(B log P) to O(B), while retaining every byte/provenance check. Validate IDs before caching; preserve malformed-ID rejection, relay-buffer identity, buffer lifetime and corruption detection. This is supported by caller-qualified map samples, not just a generic STL hotspot.
3. **Investigate an ordered native retry/eligible-operation index.** `src/unified-bus/model/protocol/ub-transaction.cc:823–861,1400–1436` is sampled heavily in Chunk. First measure retry counts and actual live-operation visits; current evidence establishes neither a native O(W²) executed count nor a quantified speedup. An index could reduce repeated live-range scans, but is higher risk: preserve operation-ID order, dispatch readiness, CTP exclusions, sender/cleanup transitions and transport-capacity wakeups. Do not batch WQEs or change submission/TA semantics.

Any later optimization should be a separate milestone. Compare each candidate against this pinned baseline using the same Release flags and inputs. Require exact small full-debug event timestamp/order and TA identity parity, exact graph/payload bytes and fingerprints, identical stable summary fields and packet/byte totals, and unchanged fault rejection. For large completed cases require exact simulated latency, counts and full stable summaries. For Chunk, compare deterministic prefixes at an identical simulated event boundary, not equal host-wall cutoffs; a stop observer must itself be proved non-scheduling and preserve the prefix. Full completion remains necessary before claiming a completed-layer result. Repeat clean uninstrumented controls to estimate host variance; collect profiling runs separately, with all guards retained.


## Hypotheses and remaining uncertainty

| Original explanation | Outcome | Evidence boundary |
|---|---|---|
| Python preparation/preflight dominate their stage | Matched | Full-size measured dependency spans, independently checked inputs |
| Native initialization dependency handling is material | Matched | Original Read samples and actual complete diagnostic candidate pass |
| Online group Audit is material | Matched | Original Audit samples and partial executed scan counters; not the entire timeout |
| Native per-Jetty retry work adds Chunk cost | Partially matched | Caller stacks and source mechanism; no native retry/live-set iteration counter |
| Copies/packet handling alone explain the timeout | Inconclusive as a complete attribution | Small observed Packet/Buffer memberships; incomplete copy symbols and overlapping descendants |
| Chunk can complete within the fixed guard | Not demonstrated | All valid Chunk runs remain partial; no completed latency or final validation |

No optimization was attempted. The next decision is which separately validated candidate to investigate first; the evidence most directly supports ordered immutable graph/membership indexes.


## Resource guards and interrupted attempt

The original process-group guard retained300-second wall,6GiB sampled tree RSS,7GiB address space,1.5GiB minimum host available memory,8GiB minimum free disk and2GiB minimum free temporary disk. Large input preparation was not rerun to start simulations. A recoverable sparse checkout removed only newly materialized, unmodified historical-evidence copies; original evidence and Git objects remain intact. Raw sample output has a128MiB budget, with large profiles and decoded stacks retained locally under SHA256 manifests.

One fresh uninstrumented Chunk attempt lost its execution-tool session during an exec-server transport disconnect and produced no terminal resource ledger. Its directory/provenance are preserved and its status is **INTERRUPTED_UNKNOWN**, excluded from timing comparisons. The same bounded command was retried after host access recovered. Shell process views are namespace-scoped, so they cannot prove absence of a host-global orphan; the old directory received no subsequent completion write, and the successful retry used300.099s process CPU in300.341s wall without an apparent competing-CPU shortfall. No saved environment, security setting change, or relaxed guard was used.
