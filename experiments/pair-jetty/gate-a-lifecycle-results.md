# Gate A: PairJetty lifecycle and wrap tests

All six independent extra cases passed on 2026-10-17 against unchanged native commit `2fde39d02920e639f5b200d0c5262a517326deb8`.

## Reproduce

Run `experiments/pair-jetty/run-pair-lifecycle.sh` from any directory. It compiles only the standalone application probe against the existing native build. Defaults assume `pair-jetty-delivery` and `wqe-completion-native` are sibling directories. Override `NATIVE` and `OUT` when needed.

The runner checks the native commit and clean `src/unified-bus`, records source/binary/library hashes, runs sequentially, and stops on the first failure. Guards: 90 seconds per case, 8 GiB address-space limit, at least 2 GiB free disk. It does not modify or rebuild native code.

## Results

| Case | Directed pairs | WQEs | Request TA segments | Peak outstanding per pair | Result |
|---|---:|---:|---:|---:|---|
| 2-node full directional | 2 | 8 | 24 | 3 | PASS |
| 3-node full directional | 6 | 24 | 72 | 3 | PASS |
| 4-node full directional | 12 | 48 | 144 | 3 | PASS |
| Cancel with late responses | 1 | 5 | 15 | 3 | PASS |
| Fail with late responses | 1 | 5 | 15 | 3 | PASS |
| Long cached-pair reuse | 1 | 22,000 | 66,000 | 63 | PASS |

The final long-reuse run took 3.024 seconds wall time, 2.977 seconds user CPU, and 36,892 KiB peak RSS. It verified 3,520,000 payload bytes, 22,000 exact-once terminal callbacks, 22,000 success callbacks, 66,000 responses, and one 16-bit SSN wrap. The final logical send/ack windows were both 66,000.

## Oracle and coverage

- Every fragment contains independently decoded magic, WQE ID, source, destination, byte offset, and fragment length, followed by deterministic bytes. Neither target identity nor payload offsets are inferred from SSNs.
- Target metadata checks include source, destination, WRITE opcode, resolved transaction, and the expected PairJetty ID. Separate sender trace accounting maps each logical SSN to its WQE and offset, verifies its 16-bit wire value, and checks the target's unwrapped logical SSN against the independently decoded payload offset.
- All directional pairs are exercised concurrently on real direct links. Three multi-TA WQEs per pair overlap, then the cached entry is reused. Reverse directions have separate IDs, storage, callbacks, and sequence spaces.
- Local-copy sanity checks consume no Jetty storage. The manager rejects self-pairs, out-of-range ranks, and TP changes for cached pairs. This is manager-level coverage; application local-transfer integration belongs to later gates.
- Cancellation and failure leave the first WQE's target responses delayed while later WQEs are target-complete but blocked behind the first WQE. Explicit terminalization wakes those later WQEs. A newer WQE remains active when the old responses arrive. Failed/canceled work receives exactly one outcome callback and no success-only client callback.
- Every target completion is invoked twice, including after cancellation/failure. No duplicate sender callbacks result.
- The wrap workload admits WQEs every 100 ns independently of completion or idle state. It does not serialize work or gate admission on ACKs. It crosses 65,536 actual TA admissions without seeding counters and retains 63 overlapping WQEs at peak.
- Busy `CheckIdle()` rejects active work. Final checks require every sender Jetty idle, zero active WQEs, drained logical windows, zero resident/active transaction operations and segments on every node, and zero outstanding unacked segments on every TP.
- Manager destruction occurs after successful idle checking and before `Simulator::Destroy()`. Simulator destruction emits no additional callbacks.

## Evidence

Raw outputs are under `pair-jetty-raw/gate-a-extra/`: per-case event CSVs, summary files, resource JSON, stdout/stderr logs, exit-status CSV, native commit, and SHA-256 hashes. `independent-event-audit.json` additionally records a read-only audit of the CSVs: matching request/verified-target counts, no failure records, wire/logical agreement, a continuous 0..65,999 logical request sequence, and delayed old responses arriving while newer work is active.

All six cases exited zero in both initial and final guarded verification. No new native failure or MRE was found. These results pass the extra lifecycle portion of Gate A; they do not claim later application or resource-comparison gates have passed.
