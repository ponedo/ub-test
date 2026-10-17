# Pair Jetty application experiment

This directory adds a directed-pair Jetty manager and a new standalone `pair-layer` executable. It compares two Jetty ownership policies on the same accepted native implementation and the same application input:

- `--jettyMode=per-wqe`: one Jetty per remote transfer/WQE; Jetty ID equals task ID.
- `--jettyMode=pair` (default): one cached Jetty per directed `(source rank, target rank)` pair, shared across the communication stages that use that pair.

`pair-layer` supports the existing No Balancing, Direct Weight Forward, Two-Stage Relay, and Chunk-Streaming Relay input contracts. Strategy selection remains in the accepted input; `--jettyMode` changes Jetty ownership only. Local transfers remain local and allocate no Jetty.

The original applications and their source directories are preserved: `no-balancing-layer`, `direct-weight-forward`, and `multi-npu-relay`. The original accepted generator, planner, adapter, tracker, and strict relay verifier are reused. Do not replace those executables or copy this application into the native checkout to run this experiment.

## Fixed baseline and dependencies

- Native commit: `2fde39d02920e639f5b200d0c5262a517326deb8`, containing the accepted Jetty index and both concurrent-completion fixes.
- Native tools submodule: `scratch/ns-3-ub-tools` at `29009175f1778f76a22d929063c3a0821cb91e56` when provisioning the accepted build.
- The matching existing ns-3.44 native build must provide `build/include` and `build/lib`, including the `unified-bus`, `network`, and `core` libraries.
- C++20 compiler; Python 3 with `psutil` for the guarded runners; the retained Python planner/adapter modules in this delivery.
- Fresh input preparation additionally requires the original `multi-npu-relay/graph-tool.cc` helper, compiled below. No helper is needed merely to rerun already accepted, materialized inputs.

No native source changes are part of this experiment. `build.sh` checks the exact native source tree and a clean `src/unified-bus`, then compiles only the standalone application/probe sources. It records executable and native-library hashes. Headers and libraries must come from the same accepted native build.

### Reconstructing the accepted native source

The measured native commit is `2fde39d02920e639f5b200d0c5262a517326deb8`; its full Git tree is `c27d1faef570e6da9900a71aa0a37180a58dfba8`. Build preflight pins the tree, so applying the exact already-published patches with different commit metadata is supported. In a dedicated checkout at original baseline `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`, apply `experiments/jetty-resource-mapping/tpn-jetty-index.patch`, then `experiments/wqe-completion-fix/combined-native.patch`, and commit only those reviewed changes. Confirm `git rev-parse HEAD^{tree}` equals the tree above. This reconstruction was checked with an isolated Git index and produced that exact tree. Keep the native tools submodule at the version listed above.

Configure the resulting native source with the already accepted Release settings: `--enable-modules=unified-bus --disable-examples --enable-tests --disable-mpi --disable-mtp --disable-werror -d release -G Ninja -- -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_CXX_FLAGS_RELEASE="-O3 -DNDEBUG -g"`, then build the unified-bus module and test library. Existing accepted native build scripts document the same settings. No new native modifications are required by Pair Jetty.

## Manager, identities, and sequence numbers

`PairJettyManager::Get(source, target, tpn)` creates a Jetty on the source controller on first use and returns that same entry thereafter. It binds to the existing TP, applies the original TA segment size and completion callback, and rejects local/invalid ranks, an occupied ID, or a changed TP for an existing key. Reverse directions are separate entries. The manager neither schedules nor serializes WQEs.

The stable pair ID is:

```text
pair ID = source * number_of_ranks + target + 1
```

### ID-width audit

- The native transaction request `iniRcId` and acknowledgment `iniRcId` carry **20-bit** Jetty IDs. See `src/unified-bus/model/protocol/ub-header.h` and the `0xFFFFF` masks in `ub-header.cc`; the request and acknowledgment paths both use that width.
- The application bounds the rank count at `n <= 72`, so the pair-ID formula is bounded by `n*n <= 5,184`, safely inside the 20-bit field. Local keys are excluded. Task IDs are not used to allocate pair IDs.
- Task/WQE identity is separately carried in the simulator's `UbFlowTag` as `uint32_t`; its tag serializer uses `WriteU32`/`ReadU32`. `ub-transport.cc` creates that tag from the task ID and restores it for target delivery. This is simulator metadata, not an additional 32-bit field being added to the native transaction wire header.
- In legacy `per-wqe` mode, task IDs also become Jetty IDs, so that path still needs to fit the native 20-bit field. The retained application/input bounds keep the supported transfer count within that field; a wider simulation tag does not remove the Jetty-field restriction.

### Logical and wire SSNs

The application tracks the logical TA sequence separately for each source/Jetty in both modes. The sender trace exposes the 16-bit wire SSN; the application checks that it equals the low 16 bits of its logical sequence. Target requests carry the native unwrapped logical SSN. Per-transfer admission records map that logical sequence to the byte offset; response bookkeeping consumes the matching pending wire-sequence entry without scanning the complete transfer history.

`ta-identity.csv` records task, Jetty, logical SSN, byte offset, and length. Target identity checks include the expected Jetty, task, source, destination, and transaction metadata. Callback routing uses task plus Jetty identity, rather than assuming those IDs are interchangeable.

The independent lifecycle probe performs a real 66,000-TA run using 22,000 multi-TA WQEs on one cached pair. It starts from sequence zero and crosses the 16-bit boundary without seeding counters. WQEs are admitted on fixed times independently of callbacks, with actual overlap. Payload fragments independently encode their own identity and offset, so the payload oracle does not infer correctness from SSN arithmetic. See `gate-a-lifecycle-results.md` and its raw evidence for the completed lifecycle checks.

## Scope and lifecycle limits

The comparison preserves:

- Router assignments, logical experts, physical placement, and planner quotas
- Per-assignment dispatch/combine WQE granularity and each accepted weight-transfer edge
- Payload bytes, TA segment size, topology, routing, TP configuration, and congestion-control settings
- Target-completion readiness, relay dependencies/group barriers, and the accepted compute model

Sharing a native Jetty also shares its native queue/window. This can change simulated scheduling or latency; logical equivalence does not require equal timestamps. No timing change or speedup is assumed. Measure it and retain neutral or negative results.

Only **idle teardown** is supported and tested here. Call `CheckIdle()` after all work completes, and keep callback owners alive through native cleanup. The manager does not provide cancellation-on-destruction, eviction, live rebinding, or a safe active-work teardown API. Cancel/fail probes test terminal outcomes and late responses while the manager remains alive; they do not establish that destroying an active manager is safe.

## Paths and standalone build

The following commands assume sibling native and application directories. Choose a fresh raw-output root so failed or previous runs are preserved. Run one build or simulation job at a time.

```sh
set -euo pipefail
export WORKSPACE=/absolute/workspace
export DELIVERY="$WORKSPACE/pair-jetty-delivery"
export NS3_ROOT="$WORKSPACE/wqe-completion-native"
export EXP="$DELIVERY/experiments/pair-jetty"
export RAW="$WORKSPACE/pair-jetty-rerun"
export BUILD="$RAW/build"
export FIXTURES="$DELIVERY/experiments/multi-npu-relay/evidence"
export LIB="$NS3_ROOT/build/lib"
mkdir -p "$RAW"

NS3_ROOT="$NS3_ROOT" OUT="$BUILD" bash "$EXP/build.sh"
```

This creates `pair-layer` and `pair-probe`. The additional lifecycle script below compiles `pair-lifecycle-probe` separately against the same build.

For an individual application run, first copy the accepted input/config/plan artifacts into a fresh output directory, then use:

```sh
"$BUILD/pair-layer" \
  --input=/absolute/fresh-case/input.txt \
  --out=/absolute/fresh-case \
  --capacityMetrics=/absolute/fresh-case/simulator-metrics.json \
  --jettyMode=pair
python3 "$EXP/verify.py" /absolute/fresh-case pair
```

Use the guarded runners below for the actual gates. The verifier's final positional argument should match `pair` or `per-wqe` so mode-specific ID and Jetty-count checks are included.

## Gate A: capability, lifecycle, and wrap

Run the original adapted capability cases sequentially, preserving stdout/stderr and summary files:

```sh
mkdir -p "$RAW/gate-a"
run_probe() {
  local name=$1
  shift
  timeout 90s "$BUILD/pair-probe" --output="$RAW/gate-a/$name" "$@" \
    >"$RAW/gate-a/$name.stdout" 2>"$RAW/gate-a/$name.stderr"
  grep -qx 'status=PASS' "$RAW/gate-a/$name-summary.txt"
}
run_probe single-single --mode=singleonesegment
run_probe single-multi --mode=single
run_probe multi-single --mode=onesegment
run_probe multi-interleave
run_probe late-overlap --lateNs=25000
run_probe pressure --count=16 --segments=32 --lateNs=25000 --duplicateDone=1

NATIVE="$NS3_ROOT" OUT="$RAW/gate-a-extra" bash "$EXP/run-pair-lifecycle.sh"
```

The lifecycle runner adds real-link 2/3/4-node directional coverage, local-no-Jetty sanity checks, concurrent multi-TA cancellation/failure wakeup, late/duplicate completion handling, real wrap, and idle/resource cleanup. It records per-case exit codes, events, summaries, host resources, and hashes. Do not progress past a native abort, callback/byte mismatch, or unfinished work; preserve the failing case as an MRE instead of modifying native code in this experiment.

## Gate B: No Balancing

```sh
python3 "$EXP/run-cases.py" \
  --binary "$BUILD/pair-layer" --lib "$LIB" \
  --inputs "$FIXTURES" --group nb --out "$RAW/gate-b"
```

For every selected accepted input, the same executable runs `per-wqe` then `pair`, each followed by strict verification. The runner hashes inputs and compares logical transfer/result invariants across modes.

## Gate C: weight strategies

After Gate B passes:

```sh
python3 "$EXP/run-cases.py" \
  --binary "$BUILD/pair-layer" --lib "$LIB" \
  --inputs "$FIXTURES" --group weights --out "$RAW/gate-c"
```

This covers the accepted Direct, Two-Stage, and Chunk-Streaming cases, including relay/group dependencies, partial chunks/TAs, and reordered target completion. The strict verifier checks actual received payloads, exact coverage and multiplicity, target readiness, compute dependencies, and sender completion identities. A successful simulator exit alone is insufficient.

### Live negative and verifier-tamper checks

Run after Gate C has finished, with no concurrent jobs:

```sh
python3 "$EXP/run-negative-tests.py" \
  --binary "$BUILD/pair-layer" --lib "$LIB" \
  --gate-c "$RAW/gate-c" --out "$RAW/gate-c-negative"
```

Nine existing faults must fail with their expected application error: `weight-byte`, `premature-ready`, `duplicate-weight`, `early-compute`, `early-group`, `relay-byte`, `relay-buffer-byte`, `early-relay`, and `early-final-ready`. The accepted `multi4_force/chunk-streaming` fixture is used except for `early-group`, which uses `slow_relay8/chunk-streaming` and requires local relay coverage complete while another group dependency is incomplete. Resource kills and unrelated failures do not count as successful rejection.

`duplicate-notify` must succeed under the strict verifier and retain the baseline summary, payloads, and executed graph. Copies of the accepted artifacts are then tampered with to test rejection of a payload-byte change and premature final readiness; the original Gate C outputs are untouched. `negative-tests.json` records the outcomes and exact commands.

## Gate D: guarded fixed-input resource comparison

Use the same binary and native libraries for both modes. Accepted `common-5000/run`, `common-10000/run`, `common-20000/run`, and `common-50000/run` inputs can be reused directly. To prepare new copies, compile the unchanged helper and run the fixed-seed generator → planner → adapter wrapper:

```sh
export GRAPH_TOOL="$RAW/helpers/graph-tool"
mkdir -p "$(dirname "$GRAPH_TOOL")"
c++ -std=c++20 -Wall -Wextra -O2 \
  "$DELIVERY/experiments/multi-npu-relay/graph-tool.cc" -o "$GRAPH_TOOL"

for scale in 5000 10000 20000 50000; do
  python3 "$EXP/prepare-inputs.py" \
    --out "$RAW/common-$scale" --assignments "$scale" \
    --mode no-balancing --graph-tool "$GRAPH_TOOL"
  python3 "$EXP/run-cases.py" \
    --binary "$BUILD/pair-layer" --lib "$LIB" \
    --inputs "$RAW/common-$scale/run" --group one \
    --out "$RAW/gate-d-$scale"
done
```

`prepare-inputs.py` requires a fresh `--out` and calls the retained `prefill-capacity/stage.py` stages without changing their fixed seed, generator, planner, or adapter. It supports `--mode no-balancing` and `--mode ultraep`; the latter produces the accepted balanced chunk-streaming workload. Keep the chosen workload and input hashes identical across the two Jetty modes. The commands above are a reproduction procedure, not a statement that a newly prepared run has completed.

Only consider 100K after the 50K parity/resource checks pass and the unchanged guards leave adequate capacity:

```sh
python3 "$EXP/prepare-inputs.py" \
  --out "$RAW/common-100000" --assignments 100000 \
  --mode no-balancing --graph-tool "$GRAPH_TOOL"
python3 "$EXP/run-cases.py" \
  --binary "$BUILD/pair-layer" --lib "$LIB" \
  --inputs "$RAW/common-100000/run" --group one \
  --out "$RAW/gate-d-100000" --modes pair per-wqe
```

`run-cases.py` defaults to `--modes per-wqe pair`. If a larger legacy run hits a resource guard, retain that failure and review it before a fresh `--modes pair` run within the same safety limits. A pair-only success is not a completed A/B parity comparison and does not provide a measured legacy runtime or speedup.

Do not invoke the older `jetty-resource-mapping/harness.py` with this executable: its `--jettyMapping=pairJetty` switch belongs to an older interface. This executable accepts `--jettyMode`.

## Guards, evidence, and reporting

Application/input/negative runners use the retained guard: 300-second wall limit per stage, 6 GiB process-tree RSS, 7 GiB address space, at least 1.5 GiB host-available memory, 8 GiB free output storage, and 2 GiB free `/tmp`. The small lifecycle runner has its own 90-second/8-GiB-address-space/2-GiB-free-disk bounds. Guards are ceilings, not targets. Do not run benchmarks concurrently or silently relax a guard after a failure.

Keep:

- Native commit, clean-tree check, input/source/binary/library hashes, commands, and exit status
- `results.json`, `summary.json`, and mode-aware `pair-validation.json`
- `events.csv`, `ta-identity.csv`, native traces, received payload bytes, and the executed transfer graph
- `simulator-metrics.json` counters and separate host `resource.json`/resource samples
- Negative-test records and all failed/guarded attempt directories

Report wall time, CPU, RSS, Jetty counts, WQEs, TA counts, callback counts, strict-verifier outcome, logical parity, and simulated latency separately. Host overhead reductions do not establish numerical MoE throughput improvements; the retained workload uses synthetic verified payloads/results and the accepted modeled compute durations. Record the final actual results in the experiment report, including unchanged timing or any negative result, rather than treating this README's commands as evidence of execution.

## Delivered evidence and restoration

`evidence/bundles/manifest.json` lists every original evidence path, size and SHA256, plus deduplicated content objects and independent transport bundles capped at 10 MB. The bundles contain application events, original input graphs, received payload bytes, counters, complete raw native trace member files, resources, errors and test logs. ELF binaries and copied old source checkout snapshots are excluded; build/library hashes identify the fixed code used. The optional 100K legacy run is explicitly guarded and partial.

The transport deduplicates identical bytes and compresses chunks with XZ. Previously compacted `native.tar.gz` containers are expanded to their original `native/` member paths. Original gzip-container hashes are recorded for provenance, but their encoding bytes are not reconstructed; every original trace file byte is preserved. `anchor-verification.json` checks the new representation against the previously reviewed file manifests. The original full gzip archives remain on the host; their reviewed per-file manifests are published in `evidence/previous-manifests/`. The commands below also independently recheck the transformation against those old hash anchors.

After cloning this branch, restore all evidence into an empty directory and verify all files. No separate download service, credentials, or manual archive ordering is needed:

```sh
RESTORED="$PWD/pair-jetty-restored-evidence" # must be absent or empty
python3 "$EXP/restore-evidence.py" --bundle-dir "$EXP/evidence/bundles" --out "$RESTORED"
python3 "$EXP/restore-evidence.py" --bundle-dir "$EXP/evidence/bundles" --out "$RESTORED" --verify-only
python3 "$EXP/restore-fixtures.py" --raw "$RESTORED" --out "$RESTORED/input-fixtures"
python3 "$EXP/check-bundle-anchors.py" --raw "$RESTORED" --previous "$EXP/evidence/previous-manifests" --bundle-dir "$EXP/evidence/bundles" --result "$RESTORED/anchor-recheck.json"
export FIXTURES="$RESTORED/input-fixtures"
```

The extractor checks transport hashes, content hashes and full reconstructed file hashes, rejects path traversal and links, and refuses nonempty restore targets. Use a separate fresh output root for reruns. Fixture restoration was checked against all 336 accepted input files byte-for-byte. Native traces are directly readable after restoration; their retained `native.manifest.json` records the pre-compaction hashes.

`review-audit.json` labels the optional 100K A/B comparison incomplete; this does not assert a source correctness failure. The completed Pair100K and complete A/B through50K have their separate verification evidence.
