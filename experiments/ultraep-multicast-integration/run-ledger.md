# Execution ledger
- Authorized scope and immutable real inputs audited; source/manifest/counts/hash identity verified read-only.
- Candidate integration source added; native first-unsent observer build running.
- Opt-in RR commit revalidation patch prepared but not yet applied while native build runs.
- Stage A not run; Stage B not authorized by gate yet; no performance findings.

## 2026-10-20 16:19 UTC
- Initial EP4 multi-target canary: 4/4 modes passed.
- Initial 1 MiB attempted overlap fixture: simulator/validators passed, but structural coverage assertion failed (actual receiver sets disjoint). Not counted as overlap evidence; retained privately.
- Final Stage A: 8 cases x 4 modes = 32 positive runs passed. Four negative correctness injections rejected with expected diagnostics. Native data-loss and ACK-loss plus stale-grant smoke passed. Paired stress: 5 groups / 10 children / 9 pair Jetties; 1 MiB asymmetric case reached exactly 512 native in-flight TAs and drained.
- Old application parity: 24 fresh NoBal/Direct/Chunk executions matched the candidate semantic outputs field-for-field.
- Old v1/v2 matrix: 14 positive cases matched accepted wire/timing/queue metrics exactly; expected association/feedback negatives also checked.
- Native retransmission smoke: normal, one data loss, one ACK loss, one transaction-response loss passed existing verifier.
- Stage B fixed real preparation launched. No real performance result claimed yet.

## 2026-10-20 17:05 UTC: final cached native library
- Stage A32 positive cases,4 expected negatives,3 network/scheduler smoke and2 paired stress passed again.
- Old24 application parity,14 v1/v2 cases and4 native retransmission cases passed again. Additional Two-Stage candidate/legacy full summary matched except host verification time.
- Full native build completed successfully after resuming with4 parallel compiler jobs; wall776.13s for the resumed build, peakRSS3118752KiB, no resource guard. This is a build result, not a claim that every compiled native test suite was executed.
- Final real four-strategy preparation/preflight passed. Uniform source/native hashes checked. Fresh NoBal simulation started; first diagnostic NoBal is excluded.

## 2026-10-20 17:12 UTC: exact resource projection, unchanged hard limit
Final-library NoBal passed:380.460457s wall,369.069784s CPU,816172KiB RSS; simulated layer89.129315416ms exactly matches the earlier diagnostic and historical semantic result. The additional rounded380s projection gate stopped admission, although the exact historical relative-work projection is3584.603s, below3600s. Corrected the projection to use its exact formula, without raising any hard guard or weakening correctness checks. Explicit continuation validates binary/native/input/config/plan hashes and all existing NoBal verification receipts before running only the still-unrun three treatments. Preserve the original stopped ledger. This is not reuse of the earlier816s diagnostic result or a protocol/host guard failure.

## 2026-10-20 17:47 UTC: user-requested two-case concurrency
- Final Direct passed: layer 27.073308104 ms, receiver Weight Ready duration 6.867179560 ms, wall 1645.009791471 s, peak RSS 3827564 KiB.
- User clarified that 6 GiB is a per-case guard, not a combined host budget, and requested concurrent independent runs. Chunk was already running; admitted only Multicast alongside it after checking host available memory against its historical peak plus the unchanged 1.5 GiB host floor and 128 MiB margin. No third case or build was launched.
- The same executable bytes were copied and verified for the parallel case. The sequential launch path was temporarily renamed to prevent a duplicate Multicast launch after Chunk; the existing Chunk process retains the same mapped executable. Restore only after both drivers exit and all receipts verify.
- Chunk and Multicast retain identical per-case guards and configurations. Their host timing is not a strict serial-performance comparison. No simulated timing or event dependency was modified.

## 2026-10-20 18:19 UTC: Multicast verified, Chunk pending
- Multicast simulator, postflight and independent checks passed: layer 23.635078624 ms, receiver Weight Ready duration 3.429284200 ms, wall 1755.791955660 s, peak RSS 3832716 KiB.
- Chunk still running. No four-way completion or Chunk-relative performance claim yet.

## 2026-10-20 18:31 UTC: four-way verification complete
- Chunk passed all three checks: layer 25.357403064 ms, Weight Ready duration 5.150959120 ms, wall 2772.841126355 s, peak RSS 3710516 KiB.
- Parallel v2 driver exited 0. Sequential driver exited 1 only at the deliberately missing executable identity gate after Chunk PASS, preventing a duplicate v2 launch. Both exits were confirmed before the merge; all four cases' frozen identities and 12 simulator/postflight/independent receipts verified, then the unchanged original executable was restored. Merged ledger PASS.
- Actual simulator intervals: Chunk 17:40:10–18:26:23 UTC; v2 17:47:03–18:16:19 UTC. The v2 interval lies wholly inside Chunk's interval.
- Compact result allowlist collected, figures generated and latency figure visually checked. Independent read-only final numerical/privacy review passed. Multicast vs Chunk: weight speedup 1.502050813x, layer speedup 1.072871534x. No additional experiment scale admitted.
