# UB Multicast fanout / header sensitivity

Controlled **weight-distribution-only** microbenchmark. No Planner invocation, Token Routing, Dispatch, Combine, or active Expert Compute. It reuses the accepted production graph classes, Layer communication/readiness and full online verifier with zero assignments. Inherited zero-duration planning/reroute markers and compute_idle bookkeeping do not simulate compute work. Do not interpret the compatibility online-summary `layer_latency_ps` field as a MoE Layer benchmark; `fanout-summary.json::all_receivers_ready_duration_ps` is the authoritative metric.

## Configuration

EP64,128 resident expert metadata,only expert0 copied;mainrank0;replicatargets1..F. F=1,2,3,4,8.18MiB deterministic synthetic validation bytes,seed20261016.100Gbit/s,20ns,TA1024B,chunk4096B,VL7,original finite queues/windows/CBFC/native ACK/Response. Direct and Chunk use accepted PairJetty endpoints; multicast uses accepted dedicated native child endpoints/coalescer. Comparisons between multicast header modes isolate charging on the same path; comparing communication strategies also includes endpoint/scheduling differences.

Original Relay policy is unchanged. F1/2/3 fall back to whole-expert Direct; F4/F8 select ranks1,2 as relays, retaining all-relay GroupChunk dependencies. Source/target sets are identical across strategies. This fixture selects fanout directly and does not claim to reproduce an UltraEP Planner placement decision.

[Header field budgets and Oracle limitations](HEADER_MODELS.md). Full is the default. Compact and ideal use actual smaller Packet objects and a bounded prefix-only Oracle; ACK/Response and actual received Payload verification are unchanged. Native ns-3-ub source is not modified. Project header diff: [patches/header-cost-model.patch](patches/header-cost-model.patch).

## Build and reproduce

Requires a working accepted native tree b8375b51a094d3b1217b697989e1ab979f609e64 (all source hashes checked), built release libraries, C++20 compiler, OpenSSL development library, Python3 with psutil and matplotlib, cmake/ninja for old regressions. Baseline project commit b2b990d1fea69f7e1a1e7ed615494f821aa71913 must be in local Git history for legacy header extraction. The graph tool and baseline pair-layer binary are those from the accepted concurrent-multicast/real-multicast build; rebuild using their documented commands if absent.

```bash
bash experiments/ub-multicast-fanout-header/reproduce.sh \
  /path/to/multicast-native /path/to/fresh-private-output \
  /path/to/accepted/graph-tool /path/to/accepted/pair-layer
```

All builds/tests/simulations are sequential. Exact host guards remain3600s/stage,6GiB RSS,7GiB address space,min8GiB disk,min2GiB/tmp,min1.5GiB available memory. No silent resume or overwrite. A protected stop/nonzero/failed check halts the pipeline. The optional ideal block is after all20 main cases pass. Normal output is Summary, with one bounded legacy Debug parity group. Never publish raw large packet/payload data.

Individual commands:

```bash
python3 experiments/ub-multicast-fanout-header/build.py --native "$NATIVE" --out "$PRIVATE/build"
python3 experiments/ub-multicast-fanout-header/run.py --binary "$PRIVATE/build/fanout" --out "$PRIVATE/campaign" --phase small
python3 experiments/ub-multicast-fanout-header/run.py --binary "$PRIVATE/build/fanout" --out "$PRIVATE/campaign" --phase main
python3 experiments/ub-multicast-fanout-header/run.py --binary "$PRIVATE/build/fanout" --out "$PRIVATE/campaign" --phase ideal
python3 experiments/ub-multicast-fanout-header/verify.py "$PRIVATE/campaign/main-f8-compact-oracle"
python3 experiments/ub-multicast-fanout-header/collect.py "$PRIVATE/campaign" --out "$PRIVATE/aggregate"
python3 experiments/ub-multicast-fanout-header/analyze.py "$PRIVATE/aggregate"
```

Use the full script for all regression/legacy gates. `build_legacy.py --original-files` can use previously captured original adapter.h and group-manager.h instead of Git extraction; both bytes are checked against fixed SHA256.

## Evidence meanings

- Source payload and wire fields refer to mainrank0; Relay forwarding payload is separate.
- All-network wire sums physical TX over source/relay/receiver/switch ports, including native control traffic. It does not double-count RX observations.
- Per-target Weight Ready is actual full target execution/coverage. Sender Complete is separate and can be later.
- Egress residence sums queue waiting observations; it is not a complete VOQ/arbitration decomposition.
- Window/CBFC queries are counts, not stall duration.
- Per-target SHA256 is calculated on actual received weightData; independent Python regenerates the deterministic expected bytes. No payload is persisted in regular cases.
- Summary retains per-WQE timing/coverage reductions plus complete online per-TA checks. Debug additionally independently replays every TA and packet event. The independent checker explicitly labels that coverage distinction.
- All pressure/fault fixtures are correctness-only. Main performance runs never change fixed queues, windows, delays, or payload size.

The generic native examples-test parser submodule is absent in the supplied native checkout, a known regression limitation. Do not confuse an expected suite failure with passing tests, nor omit it from the report.
