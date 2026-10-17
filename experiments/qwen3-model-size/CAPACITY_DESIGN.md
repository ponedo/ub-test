# Configurable capacity safety

User-approved extension after the original 256-token capacity gate failed:

- `pair-layer --payloadBudgetBytes=...`: uint64 logical payload bytes, default 268435456 (256 MiB), supported range 1..8589934592 (8 GiB).
- `pair-layer --weightTaskLimit=...`: uint64 weight-WQE count limit, default 20000, supported range 1..1000000.
- Adapter/config/runtime equivalents: `payload_budget_bytes` and `weight_task_limit`; absence retains old defaults. Qwen workflow explicitly chooses the supported maxima; these are ceilings, not allocations or promises that the host can execute that demand.
- Assignment cap remains 100000. Expert count, physical count, individual WQE byte limit (64 MiB), network and protocol parameters remain unchanged.

## Arithmetic / indices

The C++ payload expression uses checked uint64 multiplication and addition, including token-assignment count and total logical payload. Python integer calculations are additionally checked against uint64 capacity. Nonpositive or above-supported budget values are rejected in adapter, preflight and executor.

An allocation-free predictor computes the number of graph edges using the existing replica-group eligibility and shard chunk counts, before graph ranges/edges are materialized. It does not choose different relays or alter grouping. The actual graph count must equal the prediction. Independent seeded tests compare this count against the unchanged native graph tool for all three strategies.

Total transfer count (at most 2*100000 + 1000000 under the configured caps) must fit signed INT32 because application event/Audit task arguments use `int`, while WQE task identifiers and vector loops use uint32. Total logical segment count must fit UINT32 before payload allocation; this conservative bound also bounds any individual Jetty logical SSN progression in one layer. Native wire SSN wrap remains the existing implementation's responsibility; no wire format is changed. Packet/event aggregate counters remain uint64. Payload lengths/offsets remain uint32, safe under the unchanged 64 MiB per WQE maximum. Compute arithmetic remains existing uint128 and bounded duration.

Budget and graph/range checks occur before transfer payload allocation. Storage is allocated for actual transfers/experts only, never for the selected maximum budget. Retained source and target buffers, validation state, protocol objects and Python graph objects are additional memory not represented by logical payload. This is why the unchanged process limits remain mandatory.

## Resource gate

All real stages remain sequential with 300 s per-stage wall limit, 6 GiB process-tree RSS, 7 GiB address-space limit, 8 GiB free workspace disk, 2 GiB free `/tmp`, and 1.5 GiB available host memory. The first resource failure stops scaling; no automatic relaxation. Preparation and independent pre/postflight are guarded too. An experiment blocked or killed at any stage has no successful Layer Latency or speedup.

The weight graph's existing dependency-list construction can require quadratic scans at large edge counts. This task does not optimize or replace it. A preparation timeout must be reported separately from network simulation resources.
