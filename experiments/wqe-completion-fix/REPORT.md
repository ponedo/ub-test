# Concurrent segmented WQE completion fix

## Scope and provenance

This delivery fixes premature native WQE success for interleaved TA admissions on one Jetty. It does not modify UltraEP application code, resource mapping, TA segmentation, transport parameters, or target execution semantics.

- A: original native `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`.
- B: accepted TP→Jetty index `eda2fd75bfd1a37b28917b3ebbe721bade5f91ae`.
- C: combined native `2fde39d02920e639f5b200d0c5262a517326deb8`, B plus the two independent correctness patches and tests.
- Existing application baseline: accepted GitHub `a1c5aa4750d4d20ec60750f7f2027f8f0ce3d036` (local equivalent tree).

All timing below is measured from real ns-3-ub events. No fixed-delay network substitute is used. The target-executor delay is an explicit test workload after real transaction arrival.

## Confirmed root cause

`UbJetty::IsWqeCompleted()` reconstructed an inclusive completion frontier as `GetTaSsnStart() + GetTaSsnSize() - 1`. This describes a hypothetical contiguous reservation, not the SSNs actually admitted by `CommitWqeSegmentAdmission()`. Concurrent segmented WQEs can interleave: the original WQE 1001 owns 0, 3, 6, 9, 12. The reconstructed frontier is 4.

The TA response path validates exact task, segment, correlation and TP-generation ownership in `RecordSegmentSuccess()` before updating Jetty completion. WRITE requires the transaction response following target execution; its transport ACK alone is not a success event. The defect is later: the erroneous frontier lets `CheckAndRemoveCompletedWqe()` announce WQE success while owned TAs are pending. Terminal cleanup then marks its remaining SSNs as reclaimed, explaining the subsequently advanced prefix.

### Original causal counterexample

| Event | A original | B index | C fixed |
|---|---:|---:|---:|
| WQE 1001 sender success (ns) | 70,309 | 70,309 | 70,441 |
| Last owned target execution, SSN 9 (ns) | 70,335 | 70,335 | 70,335 |
| Jetty UNA at target SSN 9 completion | 15 | 15 | 9 |

A/B original event and summary outputs are byte-identical. C reports success after every required target execution. The 106 ns target-to-success gap is the actual response/transport and existing prefix-ordering behavior, not an inserted notification delay.

Source locations in the supplied final snapshot: [admission](native-snapshot/src/unified-bus/model/protocol/ub-function.cc#L1201), [completion predicate](native-snapshot/src/unified-bus/model/protocol/ub-function.cc#L1629), [terminal cleanup and wakeup](native-snapshot/src/unified-bus/model/protocol/ub-transaction.cc#L2647). The old predicate is preserved in the independent patch.

## Minimal correction

`UbWqe` stores an optional actual last-admitted TA SSN. Push resets it; successful admission updates it from the segment itself. Completion requires all WQE bytes admitted, a recorded admission frontier, and that frontier strictly below the existing global `sndUna`.

This does not require the WQE's owned SSNs to be contiguous. In the existing monotonic logical SSN domain, all owned admitted SSNs are at or below the last actual admission; the completed prefix therefore covers all of them. The all-bytes-admitted gate prevents partial submissions from finishing. Existing prefix head-of-line completion ordering is deliberately retained. The patch does not independently complete later WQEs around a prefix hole.

The admission-frontier fix adds one bounded optional scalar per WQE, no per-TA allocation, no new map or scan, and O(1) predicate/admission work. Native existing logical 32-bit exhaustion remains outside the supported claim; the existing 16-bit wire-wrap tests are retained.

## Separately authorized cancellation/failure notification repair

The original real-link cancellation characterization reproduces identically in A, B and frontier-only C (before the second fix). Two interleaved segmented WQEs share a Jetty. A's target execution is withheld, B's transactions finish. Canceling A at 100,000 ns advances UNA from 0 to 4, but B remains active at the quiet 150,000 ns checkpoint. A new C request at 200,000 ns causes a later response to recheck completion, releasing B at 201,214 ns.

`AdvanceTaSsnForWqeCleanup()` advances the prefix without rechecking other WQEs. This is distinct from premature success and is not repaired by the frontier patch alone. The original characterization exits zero when its observations are valid; that does not mean the liveness issue passes correctness. Its original A/B/frontier-only C evidence is preserved.

The separately authorized repair calls the existing completion checker inside `CompleteWqeOperationForDrain()`, after `FinishWqe()` returns. At that point the terminal WQE has been removed and its outcome callback delivered. It is gated on `CONTINUE_ACCEPTED`, a still-live function facade and the exact same Jetty pointer. Bulk stop/simulation drain is excluded. Retaining the Jetty pointer prevents destruction during the check, and generation/pointer revalidation avoids touching a replacement Jetty created by a reentrant callback. ACK/response processing and retained segment retirement are unchanged.

The native test covers 14 CANCELED/FAILED variants: no callback mutation, submission of a new WQE, nested cancellation of B, destruction, destruction/recreation of the same Jetty ID, and an awakened B-success callback canceling C or destroying the Jetty during the completion scan. Standalone failure/cancellation oracles require B notification during the quiet interval without new traffic and late-response resource reclamation. All 14 variants pass. In the final standalone cancellation and failure cases, B is notified at 100,000 ns immediately after A's terminal callback, instead of waiting for new traffic. Both report `hole_observed=0, errors=0`; late A target completions at 200,118/200,127 ns do not duplicate its outcome.

The wake repair invokes the existing scan of this Jetty's active WQE vector only on normal failure/cancellation, not all historical WQEs or other Jetties. An unsuccessful scan is O(K) in that active vector; its existing erase/restart behavior can be quadratic when many completions are released together. No new per-TA storage or global scan is introduced.

## Validation status

The original probe and nine expanded real-network cases pass on C. Expanded cases cover single/multiple WQEs, single/multiple TAs, interleaving, delayed/out-of-order target execution, a later overlapping submission, repeated target executor completion calls, 561 total TA admissions reaching the default 512 in-flight segment limit (observed peak `sndNxt - sndUna = 512`), payload identity and byte coverage, exactly-once callbacks and operation/TA/TP cleanup.

The independent event analyzer verifies 52 C WQE observations and every owned target completion precedes its sender success. Duplicate target-executor callbacks are tested; these are not claims of injected duplicate/stale inbound network responses. A new real-link interleaved 16-bit wire-wrap scenario was not run; existing native wire-wrap tests are retained. Logical 32-bit exhaustion is a separate pre-existing unsupported boundary.

The frontier-only native revision `26abe117f2903a4d6fc27c8d015a0f6ec25b6ffa` passed all 44 native unit suites. Its first old-application regression attempt completed the 48-case matrix and normal oracle checks, then its host monitor encountered a short-lived-process `psutil.NoSuchProcess` race while reading thread count. That attempt and traceback are retained. A local test-side observer catches only this observation race; original application and verification code remain unchanged. The final combined revision passes all 44 native suites, all 13 C standalone probe runs, the complete 48-run relay matrix, 26-run Direct matrix, and the prior Planner, No-Balancing and Chunk Relay regression chain. The No-Balancing chain includes 8 workload runs and 16 ordinary/optimized correctness tests. No native/application test oracle was relaxed.

## Coverage boundaries

The new real-link stress probes use RTP WRITE, whose success requires target execution/response. Existing native CTP and other transaction-type suites are rerun, but this delivery does not claim a new concurrent multisegment CTP workload study. Duplicate target completion and late post-terminal responses are tested; arbitrary injected wire duplicate/stale responses and 32-bit logical SSN exhaustion are not newly tested. No full 50K/100K capacity scan is performed.

## Exact existing-application parity

The accepted index-only baseline and final combined fix have identical deterministic artifacts:

| Regression set | Files compared | Changed files |
|---|---:|---:|
| Relay / No-Balancing matrix | 3,635 | 0 |
| Direct and legacy parity | 1,531 | 0 |
| Prior No-Balancing / Chunk Relay | 626 | 0 |

The comparator includes every CSV, payload binary and simulation summary in each set. Thus WQE/TA counts, target/sender timestamps, chunk readiness, relay forwarding, payloads and Layer Latency are unchanged for the existing one-WQE-per-Jetty application. The JSON hash manifests identify every compared file. The final successful regression chain took 162.74 host seconds including builds and tests; its peak RSS was 952,596 KiB.

## Host time and memory check

Three alternating index/fixed runs each at 5K and 10K assignments use identical accepted EP64 inputs and parameters. All 12 executions and independent verifications pass. Every fixed run matches its paired reference across all 398 output files byte-for-byte.

| Assignments | Index median wall (range), s | Fixed median wall (range), s | Index / fixed median peak RSS, KiB | Layer latency, both (µs) |
|---|---|---|---|---:|
| 5,000 | 3.512 (3.511–4.014) | 3.762 (3.261–4.013) | 295,708 / 295,820 | 136.649168 |
| 10,000 | 8.274 (8.025–8.525) | 7.522 (7.273–8.776) | 500,624 / 500,580 | 271.031968 |

Measured median wall ratios are +7.1% at 5K and −9.1% at 10K. Ranges overlap; three host trials do not establish zero overhead or a speedup. No consistent large runtime or RSS regression is observed in these bounded checks. Host wall time includes the existing 250 ms guard polling granularity. Raw CPU times, verifier times and all trials are in `evidence/overhead-summary/runs.csv`.

The actual compiled `sizeof(UbWqe)` increases from 448 to 456 bytes (+8 bytes). The admission frontier needs constant work per admission/check. Normal success-path ACK/response bookkeeping is unchanged. The additional active-Jetty completion scan is triggered only by failure/cancellation. This is a correctness delivery, not an UltraEP performance improvement claim.

## Delivery and reproduction

- `concurrent-wqe-completion.patch`: independent premature-success fix plus native test, against accepted index baseline.
- `terminal-wakeup.patch`: independent cancellation/failure repair plus 14-variant native test, on top of the first fix.
- `combined-native.patch`: both changes, against accepted index baseline.
- `native-snapshot/`: exact changed source files and native commit/file hashes.
- `evidence/probes/`: preserved frontier-only A/B/C evidence, including the then-unfixed cancellation hole.
- `evidence/probes-final/`: final A/B/C failures/controls/successes, actual events, outcomes, library/source provenance and causal analysis.
- `evidence/native-unit-suites-final/`, `evidence/regression-final/`, parity manifests and overhead records: final executed acceptance evidence.

Applying the two independent patches or the combined patch to the pinned baseline produces the same native Git tree (`c27d1faef570e6da9900a71aa0a37180a58dfba8`); `evidence/patch-parity.json` records the check. Full bulky native binaries and duplicate application payload archives remain on the host; GitHub includes the actual small probe events, logs, measured metadata and full output hash manifests. See README.md for explicit build, regression, probe and resource-check commands.

Both identified correctness issues are repaired within the scoped native completion/lifecycle hooks. No further Pair Jetty work is included; stop for acceptance.
