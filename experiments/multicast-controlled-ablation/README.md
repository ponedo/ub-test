# Controlled multicast reversal ablation

This package contains fresh 3136 Gbps baseline runs and separate Jetty-window B
runs. A is **UNSUPPORTED** because the minimal null-grant callback suppression
changes the original allocator's round-robin winner order. No A performance result,
A+B combination, or default-window promotion is included.

Read `experiment-plan.md`, `preregistered-analysis.md`, `matrix.yaml`,
`run-ledger.md`, `audit-a/SOURCE-AUDIT.md`, and `native/SOURCE-AUDIT.md` before
interpreting the counters. Window metadata is separate from the unchanged
online-summary schema.

## Reproduction prerequisites and accepted controls

The public package is not a standalone substitute for the authorized private
experiment workspace. It intentionally does not download, regenerate, or publish
restricted routing/workload traces. Reproduction needs the same authorized
L37/2048 real inputs and accepted private control outputs, plus the accepted small
fixtures. The harness freezes their identities and refuses an output-directory
collision.

Keep these existing controls immutable:

- `bandwidth-work`, `bandwidth-native`, and `bandwidth-private`, including the
  accepted fixture inputs/results, real-3136 outputs, and `build/layer`,
  `build/graph-tool`, `build/parent-layer`, and `build/model-probe`.
- `diagnosis-work`, `diagnosis-native`, and `diagnosis-private`, including
  `build/layer`, `build/graph-tool`, `build/observer-fifo-test`, and the accepted
  `real-3136/chunk-streaming` and `real-3136/multicast-v2` inputs and full evidence.
- The native libraries linked by those accepted executables. Do not rebuild or
  relocate a control binary independently of its recorded library/RPATH identity.

Use this delivery checkout as `ablation-work`, its separate native tree as
`ablation-native`, and fresh explicit outputs under `ablation-private`. The
application baseline checkout for this study is
`b149fdd4d40d72791a84b788443b0450c41f6180`.

Each case input bundle contains `config.json`, `input.txt`, `plan.json`,
`assignments.csv`, `transfers.csv`, `weight-edges.csv`, and `graph-input.txt`.
The harness additionally needs accepted summary, expert-compute/expert-ready,
replica-ready, validation, and resource/lifecycle evidence for exact comparison.
If these authorized prerequisites are unavailable, stop rather than replacing
this study with synthetic or regenerated real inputs.

## Native patch chain: preserve the accepted diagnostic tree

The native repository base is
`b8375b51a094d3b1217b697989e1ab979f609e64`. The `7041b595...` base named in the
older diagnostic manifest belongs to the separate application repository, not
the native repository. These are different provenance scopes.

The accepted diagnostic native tree must already contain, in order:

1. `experiments/ub-multicast-v2/patches/native-write-v2.patch`
2. `experiments/ub-multicast-retransmission/patches/transport-fault-seam.patch`
3. `experiments/ultraep-multicast-integration/patches/peek-original-head.patch`
4. `experiments/ultraep-multicast-integration/patches/allocator-revalidation.patch`
5. `experiments/multicast-reversal-diagnosis/patches/native-diagnostics.patch`

See the accepted `multicast-reversal-diagnosis/README.md` and its native manifest
for that bridge. Make a separate source-tree copy of the accepted
`diagnosis-native`, preserving its applied patches but excluding build/cache
artifacts. A plain `git clone` is insufficient if the accepted patches are still
working-tree modifications. Never apply this study's patch to the control tree.

Apply only `native/ub-jetty-controlled-ablation.patch` to the separate
`ablation-native`. Its SHA-256 is
`f04aa181e011c097d35bdc359ca4d294f147f5ae7dc4562204932e287e92d600`.
This incremental patch changes exactly three passive-observation source files;
the allocator remains byte-identical. `native/native-patch-manifest.json` records
the accepted/candidate hashes and the complete 3430-file native source inventory
comparison. Forward/reverse application was verified on throwaway copies.

After the separate copy and patch application, verify without changing either
native input tree:

```sh
H=ablation-work/experiments/multicast-controlled-ablation
python3 "$H/native/verify-native-patch.py" \
  --accepted diagnosis-native --candidate ablation-native --staging "$H/native"
```

## Guarded execution

Use `command-manifest.yaml` from the workspace root, with fresh output paths.
Run pure harness/analysis tests, the native build, application/unit build, complete
small gate, prepare, and formal coordinator in that order. The native builder
uses two compiler jobs, assertions ON, logging OFF, and only the unified-bus
library target. This is not a claim that every native repository test suite ran.
The optional `--tools real-batch-build-tools` supplies the accepted CMake/Ninja
installation; omit it only when equivalent tools are already available.

The matrix has exactly six executable cells: 512, 1024, and 2048 × Chunk and MC,
all with the original allocator, fixed TP packet window 1000, ACK bitmap 2048,
unchanged Planner/roofline/trace inputs, and diagnostic ON. Default remains 512.
Both fresh 512 results must match accepted summaries and ordered per-expert
outputs exactly before treatment admission. The small gate additionally requires
512 accepted/OFF/ON and separate 1024/2048 OFF/ON exact event and output parity.

Real runs use summary logging only. Each keeps a 6 GiB process-tree RSS cap,
7 GiB address-space cap, 1 GiB host-memory reserve, 8 GiB free output disk,
2 GiB free temporary disk, and 4800-second whole-case wall guard. The coordinator
permits at most two cases through peak-aware admission; this execution was serial.
The 6 GiB forecast for an unmeasured larger-window case is a conservative admission
budget, not its measured footprint. Successful runs actually peaked at
3.596–3.757 GiB kernel-reported RSS (wait4 ru_maxrss), with separate
0.25-second sampled process-tree maxima. Recorded simulator user/system CPU
seconds exclude the Python coordinator and separate validation stages. The
resource JSON defines these accounting scopes and sampling limitations. Do not
weaken guards to obtain a timing.

## Delivered execution and recovery lineage

All six cells passed. The initial application build attempt was retained after a
root-authorized analysis-only label correction caused its final source-identity
gate to reject that attempt. A fresh `build-r2` passed with consistent identities;
all simulations use that frozen binary.

The original formal coordinator's execution session disappeared during the final
2048 MC attempt. It produced no terminal simulator resource/validation/result
record. The exact infrastructure cause is unknown, and this partial attempt is
not a performance result or a seventh experimental cell. Five completed cases
were already PASS and were preserved without rerunning them.

After stale-output, session, global-memory, frozen-identity, and completed-evidence
checks, one explicitly authorized retry ran only that final case in a fresh
private directory using the unchanged binary, inputs, driver, and guards. The
original interrupted root remains untouched. The resolved six-cell ledger and
final identity postflight are in the private `real-3136-recovered` root. Its first
five evidence directories reference the original successful outputs; publication
contains only sanitized aggregate files, not those private links or raw inputs.

The ordinary command manifest describes an uninterrupted fresh reproduction.
The retained recovery is an audited infrastructure exception, not an additional
sweep or a relaxed validation path. See `validation-resource-summary.json` for
attempt counts, measured resources, immutable-identity digests, and stopped A rows.

The requested runs and postflight are complete. No additional simulations,
optimization combination, or default change is authorized by this package.
