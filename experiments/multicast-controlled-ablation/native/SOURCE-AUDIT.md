# Controlled Jetty-window ablation: incremental source audit

This is a private staging artifact. The patch is relative to the accepted `diagnosis-native` tree, including its existing diagnostic sink and prior native patches. It is not a standalone patch against upstream OpenUSim. Native paths below refer to frozen `ablation-native`; experiment paths refer to frozen `ablation-work`. Exact audited-file hashes are in `source-audit-sha256.json`.

## Patch scope and reproducibility

`ub-jetty-controlled-ablation.patch` changes only:

- `src/unified-bus/model/protocol/ub-function.cc`
- `src/unified-bus/model/protocol/ub-function.h`
- `src/unified-bus/model/ub-reversal-diagnostic.h`

All 3,430 files under the two native `src/` trees were compared. Their inventories match and only those three files differ. Allocator, transport, switch, port, queue manager, codec and CMake sources are unchanged. `native-patch-manifest.json` contains the baseline/candidate hashes and representative unchanged-control hashes. `native-patch-validation.json` records successful forward and reverse checks, application and exact output hashes using throwaway copies; both input trees stayed unchanged. No builds or simulations were performed during packaging.

## Capacity, CLI and unchanged controls

- `src/unified-bus/model/protocol/ub-function.cc:1015–1030`, `UbJetty::GetTypeId`: ACK bitmap default remains 2048; native `UbJettyInflightMax` default remains 512. The member initializer remains 512 at `ub-function.h:432`.
- `ub-function.cc:1070–1077`, `UbJetty::IsLimited`: preserves the existing `sndNxt - sndUna >= inflightMax` calculation exactly once, then reports that result. It does not re-probe a predicate.
- `experiments/multicast-controlled-ablation/layer.cc:38–44`: default CLI text is `512`; `ParseJettyTaWindow` accepts only the exact strings `512`, `1024`, `2048`. `CheckJettyConfig` validates the actual per-instance limit, unchanged 2048 bitmap and limit ≤ bitmap. Metadata goes to separate `ablation-config.json`.
- `layer.cc:296–297`, `Topology`: the only experimental capacity write is `Config::SetDefault("ns3::UbJetty::UbJettyInflightMax", ...)`. Per-instance checks are at `layer.cc:319,486`; CLI registration and parsing are at `layer.cc:503`. No TA size, MTU, TP window, WQE, planner or topology treatment is introduced.
- `layer.cc:192–193`, `Read`: aggregate predicted logical TAs are bounded by `UINT32_MAX`, starting from zero, preventing 32-bit cursor wrap in the admitted workload. This is distinct from supported 16-bit wire-SSN wrapping.
- `src/unified-bus/model/protocol/ub-transport.cc:265–269`: unchanged TP packet-window default is 1000; `ub-transport.cc:2064` copies it into the actual packet limit. `layer.cc:265`, `TrackTp`, requires 1000 for every created TP.

## Passive observations and time boundaries

- `ub-reversal-diagnostic.h:12–15,56–64,78`: event kinds and optional task identity are appended; pre-existing kind values and meanings remain intact. Jetty events identify source/destination/Jetty and logical next/una/window/TA SSN. Jetty event `port` and `tp` fields are not physical port/TPN.
- `ub-reversal-diagnostic.cc:5–15`: the sink remains null by default. `diagnostic-recorder.h:24,131` keeps measurement disabled unless explicitly enabled.
- `ub-function.cc:1048–1067`, `ObserveJetty`: copies state into the sink only when enabled. Admission is observed after the committed cursor increment at `ub-function.cc:1268–1270`. Accepted TAACK progression is observed at `ub-function.cc:1535–1536`, before completion callbacks and nested transmission can admit more work. Existing rejected-ACK branches report rejection without changing their return values at `1486–1513`.
- `jetty-measurement.inc:34–65`, `AdvanceJetty`/`ObserveJettyEvent`: integrates global Jetty occupancy and full-window exposure from actual state changes, with independent real window-test counts. `diagnostic-recorder.h:56–57` clips weight-phase exposure at its exact boundaries. Observation begins at each Jetty's first observed event, not its creation. Full-window exposure is not automatically harmful blocked-wait time, and pair-times are not additive critical-path wall time.
- `diagnostic-recorder.h:66,72–82`: inherited actual `AllReady` evaluations and validated per-queue FIFO occurrence residence remain in use. No queue or readiness predicate is re-evaluated by the recorder.

## TAACK correlation, cleanup and evidence limits

- `jetty-measurement.inc:18–31,52–62`: selected pending TAs use source, Jetty and full logical SSN; the live 16-bit lookup rejects aliases. Out-of-order duplicate accepted ACK calls are counted separately and cannot create duplicate RTT samples.
- `jetty-measurement.inc:23–24,67–83`, `ObserveTaPacket`/`BindSourceFrame`: envelope associations use source plus retained packet-instance identity, with UID only as a consistency check. Concurrent copies/fragments sharing a UID remain distinct. `pair-multicast-v2.h:87–90` binds the already-popped member TAs to that exact emitted envelope; it does not change forwarding metadata, tags or payloads.
- `layer.cc:478–483` uses the existing decode-only packet seam on copies. Three boundaries are separate: admission → accepted TAACK; native packet pop → accepted TAACK; first successful physical source `TxStart` → accepted TAACK. Only the last is the measured physical-source transaction round trip; it still includes downstream network, receiver execution and return path, not propagation alone.
- `ub-function.cc:1274–1305`, `AdvanceTaSsnForWqeCleanup`: the existing native cleanup and continuation are unchanged; only a post-progress snapshot is added. `jetty-measurement.inc:64` marks selected cleanup evidence incomplete instead of treating cancellation as ACK success. `WriteJetties`, lines 84–94, fails closed on unresolved TA/frame/ACK state, nonzero terminal occupancy, or missing selected weight pop/TX samples. The existing application idle check remains at `layer.cc:495`.
- Bounds are explicit at `jetty-measurement.inc:31` and `diagnostic-recorder.h:25`: aggregate/state maps and 65,536-entry tails are capped. Weight-end Jetty tails and selected weight RTT tails are exported separately. No measurement code schedules events or mutates model state, payloads or tags.

## Existing validation evidence

`ablation-private/stage-a/status.json` reports PASS for 428 cases: 224 small, 42 fault, 28 negative, 21 invalid-rate, 30 invalid-window, 12 invalid-capacity, 7 max-capacity and 64 legacy. Its native boundary, FIFO and Jetty-observer unit flags are all true. Event order is exact for accepted/OFF/ON at 512 and independently for OFF/ON at 1024 and 2048; equal-window summaries match except `verification_wall_ns`.

`jetty-window-test.cc:21–49` exercises real native fill/block, bitmap-last-slot out-of-order ACK, duplicate/rejected ACKs, full release, failure cleanup and logical SSN crossing of the 16-bit boundary at all three windows with observation OFF/ON. `jetty-observer-test.cc:21–27` checks exact occupancy/phase clipping, RTT boundaries, concurrent same-UID packet instances and duplicate-instance rejection. Packaging verifies these existing sources and evidence; it does not rerun them.
