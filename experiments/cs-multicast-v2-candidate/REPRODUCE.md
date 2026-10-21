# Reproduction boundaries

Current result:39 executions at fixed3136Gbps (original37 plus the single paired S64 extension), with preserved coverage gaps and no measured LayerLatency win. The earlier52 executions at100Gbps are off-target diagnostics only. Total actual simulations91. This records the bounded workflow executed on2026-10-21; current target workflow is below the explicitly archived100Gbps section. Fresh reproduction still requires exact build/run approval; do not edit neighboring frozen v1 or native sources.

1. Prepare APP build with build.py prepare, explicit --out, --native token-screen-native, --accepted-identity cs-mc-private/app-build-v2/runtime-identity.json, --graph-tool token-screen-private/build/graph-tool. Use resolved absolute paths. The wrapper reuses frozen build planning and changes only source root and base identifier. Compiler input is candidate layer.cc; exactly one g++/c++ command, no native build.
2. Review source/include/native closure and resource limits, then supply approval JSON binding build-plan SHA256 with status PASS and approved_to_build true. build.py execute --out BUILD --approval FILE runs the frozen guarded build once. No automatic retry.
3. Assemble a read-only combined runtime identity containing accepted control binary/native closure, newly built candidate executable/include closure, graph tool, imported Python dependency closure and all build provenance. Any conflicting hashes stop. Candidate and v1 link the same accepted native libraries.
4. small.py prepare --out FRESH --identity IDENTITY --binary BUILD/layer --control cs-mc-private/app-build-v2/layer --graph-tool token-screen-private/build/graph-tool generates only the exact approved small fixtures and explicit37-run command-manifest.json. It normalizes V08 chunk to4096 for both arms. Review generated input hashes, exact ordered commands and row ledger before execution.
5. Supply approval JSON with approved_to_run true and manifest_sha256 matching command-manifest.json. small.py execute --out FRESH --approval FILE is a single sequential pass; no implicit resume/retry. The first failure preserves exact command/host artifacts and stops. Missing TA512 or other mandatory witness is INCOMPLETE.
6. Compare measured A/B WeightDuration, LayerLatency, source wire work, actual envelopes by hop/fanout, reason transitions, candidate inhibition costs, native NoIngress/Rejected and physical ACK/retry evidence. Keep missing safety/causal witnesses explicit. A completed execution ledger is not generalized admission or evidence of gain.

Metadata-only checks: python test_small.py. They do not generate fixtures, compile, run a simulator, or import historical PASS as new coverage. Live F03 proof remains fixture-specific. Guard limits and native verification are reused from accepted v1 rather than copied into a new execution framework.

## Archived100Gbps workflow only (not target evidence)

The off-target diagnostic result used52 simulator executions for a 37-execution logical matrix. The first 15 executions were intentionally reproduced after correcting an overly strict post-run rolling-tail oracle. The simulator executable and runtime controls did not change. Record both attempts; do not erase the initial INCOMPLETE result or present the duplicate executions as independent performance samples. Planner host cpu_wall_ns varies on fresh preparation: the recorded reproduction reused the original plan.json input bytes, preserving freshly generated plans and host timing separately. No simulator timing was copied.

With the corrected checker, the normal 37-run executor stops at V09/candidate-on because the inherited invalidation does not produce an actual stale-grant rejection under the candidate's changed eligibility. This is an expected limitation of the recorded reproduction, not authority to change the injector or mark its witness PASS.

To prepare exactly the remaining independent cases, use:

python prepare_remaining.py --prior PREFIX_RUN_ROOT --check-only
python prepare_remaining.py --prior PREFIX_RUN_ROOT --out FRESH_REMAINING_ROOT

The helper accepts only the preserved exact V09 INCOMPLETE prefix, verifies current pinned identities, requires the original declared rows, and refuses any remaining case already started. It creates only V10–V14 paired inputs, three candidate-off cases and six negative cases. Existing verified v1 V01/V04/V06 outputs are pinned read-only parity references, not new executions. It cannot approve or run anything, repair failures, resume arbitrary states, overwrite outputs or tune runtime policy. Review the new 19-execution manifest and authorize its exact hash separately; then the unchanged small.py execute command runs that package. Preserve overall NOT_GENERAL_ADMISSION and V09 NOT_EXERCISED after those remaining cases complete.

Post-run source additions are prepare_remaining.py and test_remaining.py, plus result documentation and sanitized exports. The helper codifies the metadata-only subset construction already used in the recorded run; it was not part of the compiled binary or the earlier execution identity. Its source hashes are recorded separately. No further simulations were run to validate this helper. Its check-only path and four refusal mutations were tested against preserved prefix metadata.

### Fixed 3136Gbps target run and bounded streaming extension
All earlier 52 executions at 100Gbps are off-target diagnostics only. Do not use
them as evidence for the requested high-bandwidth setting. The corrected input
contract checks serialized link rate 3136Gbps, delay20ns, chunk4096, actual TA512,
TP1000 and native allocation5ns. The initial corrected 37-command pass stops
at the original 12KiB V04 v1 strict streaming witness (seven executions total).
Preserve that directory and its incomplete ledger.

For the root-approved bounded extension, archive the exact executed small.py
before the explicit whitelist revision. Then run metadata preparation only:

    python prepare_target_remaining.py --prior <target-prefix> --out <fresh-target-remaining> --archived-small <exact-original-small.py>

This accepts only that exact seven-execution V04 stop, preserves original
inputs for the30 unexecuted commands, and adds one paired64KiB S64 fixture.
It checks unchanged Planner/assignment bytes and the tree edge/role set. It
pins prior V01/V04 control outputs as read-only references, not new executions.
After independent manifest review and a separately created exact root approval:

    python small.py execute --out <fresh-target-remaining> --approval <root-approval.json>

Only explicitly declared original V04/C-V04 streaming gaps and V09 candidate
stale-grant gaps may continue as INCOMPLETE_NOT_EXERCISED after every other
check. S64 may not use that exception. No further length search, runtime
change, native build, or implicit retry/resume is authorized by this helper.

### Candidate-only in-flight cumulative ACK oracle correction
At3136Gbps, the inherited F03 oracle incorrectly required the entire covering
ACK route to start after the lost ACK arrived. The observed PSN10/11 ACKs
started earlier, arrived later on the same TP, and had complete UID-matched
four-hop paths. candidate_ack_oracle.py retains the original fixture bounds,
original-task coverage, directed TP identity and terminal drain, but requires
only complete ordered paths whose final ingress equals the selected later RX.
It does not claim an observed instantaneous sndUna transition. Frozen v1 files
and the stopped ledger remain unchanged. Fresh preparation with current code
uses this oracle from the start.

For the already stopped target experiment only, a separately pinned posthoc
control receipt avoids repeating its simulator execution. The narrowly scoped
prepare_ack_remaining.py accepts only the exact V12 control stop after16 runs
in the32-run remainder, and emits the16 still-unexecuted commands. Inputs and
runtime binaries remain unchanged; execution again requires exact root approval.
No fixture, injection timing, length or treatment search is performed.
