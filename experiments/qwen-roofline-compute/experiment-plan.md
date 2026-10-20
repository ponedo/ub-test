# Preregistered plan
Claim: expert-batch-aware roofline reduces modeled compute and changes multicast layer benefit.
Control: accepted legacy model. Treatment: only duration formula. Strategy block: NoBal/Direct/Chunk/v2 with identical trace and accepted planner per mode.
Prediction: weight time unchanged, compute shorter, layer benefit of weight reduction proportionally larger; network competition may shift Dispatch/Combine timing. Falsification: unchanged or worse layer advantage is retained, not tuned away.
Evidence: exact independent integer oracle, expert timings/serialization, payload/WQE/TP/CBFC validators, phase spans, full host resource receipts and frozen hashes.
A: unit m=0,1,8,19,20,32,64,128,256 plus invalid/overflow; legacy parent-vs-new 4 small fixtures x4 modes; roofline same16; data/ACK/invalidation smoke2models.
B: fixed real L37/N2048/EP64 four roofline cases after A; compare published legacy under exact unchanged native sources and small legacy parity. If parity fails stop and diagnose, never mix inconsistent history.
Checkpoint: units -> build -> small parity/correctness -> fixed real preparation -> cases -> analysis -> publication. Stop on correctness or resource failure, diagnose without expanding scale.

2026-10-20 19:54 UTC user override (Sentinel_8dc6a1d3e3188191aa0ade2bec2aa137): host available-memory reserve is now 1 GiB, superseding both the original 4 GiB/20% floor. Per-case6GiB, address-space, disk, time, payload and WQE guards remain unchanged. Already running native-j2 build retains its earlier stricter4GiB floor; subsequent stages use1GiB.
