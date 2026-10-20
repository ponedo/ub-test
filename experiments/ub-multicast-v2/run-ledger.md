# Final execution ledger

All final runs executed sequentially on the original dot cloud host after checksum-verified transfer.

- Configure/native library build: PASS.
- Codec/association/current fixtures build: PASS.
- 14 positive network cases, including DWRR: PASS.
- All planned malformed codec, association, feedback and payload negatives: EXPECTED_REJECTION.
- Legacy single/full multicast/network replication/concurrent/four-strategy small regressions: PASS.
- Native test build: PASS. Native suites: 48 PASS, 1 known FAIL (missing parser, hasTaskTimes assertion). Full 49-suite inventory verified, no guard stops.
- Strict native gate: 2 valid inputs, 10 rejected invalid states; optimized Python rejected.
- Eight native changed files: exact patch replay PASS; accepted baseline 108 source hashes matched.
- Read-only source review: no supported-scope protocol defect found. Verifier fail-open issue fixed and tested.
- No optional 18MiB run, large Qwen experiment, planner change or new retransmission protocol.

Transferred earlier results remain private and are not used as final performance measurements.
