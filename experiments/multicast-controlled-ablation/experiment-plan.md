# Controlled multicast reversal ablation

## Claim, boundary, and separate arms
The accepted 3136 Gbps simulated weight-phase reversal is the starting point.
Test whether raising only the native pair-Jetty TA in-flight window changes the
Chunk/MC weight-time difference. Separately assess whether A can remove null
allocation callbacks without changing allocator semantics. A and B must each
start from the original allocator and original 512-window baseline. No A+B case
is authorized. This is ns-3 simulation evidence, not real hardware measurement.

A is STOPPED: the smallest null-callback suppression shifts the sampling time
and reverses the original round-robin winner order under the audited fixed
5 ns allocation model. The two A rows remain visible, without performance values.
A's standalone audit and counterexample supply evidence, not a fabricated run.

## Control and treatment
Control: fresh runs of the new application at the default/or explicit 512 window,
original allocator, diagnostic ON, for Chunk and MC. They must reproduce the
accepted diagnosis summary exactly except verification_wall_ns and match all
private per-expert compute/readiness files byte for byte. Accepted binary
`diagnosis-private/build/layer` and its linked diagnosis-native libraries remain
immutable; it is also rerun in the small accepted/OFF/ON gate.

B treatments: 1024 and 2048, independently from the original allocator. Window
changes can legitimately change packet scheduling, events and timing; no exact
cross-window event parity is claimed. At each changed window, passive observer
OFF vs ON must retain exact events, full summary (except verification wall time),
and private per-expert evidence parity.

## Fixed controls
- Accepted Planner, graph, trace/workload inputs, routing, topology, physical
  placement, traffic and compute model are copied byte for byte, never regenerated.
- Both strategies remain at 3136 Gbps, roofline compute 100 TFLOPS and 2692 decimal
  GB/s HBM, native pair Jetty, the accepted segment size and original allocator.
- Out-of-order TAACK capacity stays 2048. B changes only the TA send window.
- Summary logging only for real runs. All raw inputs, full per-expert results,
  diagnostic output, and temporary logs remain private. No publish/push/deploy.
- Same payload budget 8 GiB and weight-task limit 1,000,000 for all real cases.
- Same bounded recorder selectors across windows: nodes 3,5,13,17,27,36,50,52,59,64;
  MC source 3 and group 8; Chunk source/target/group filters unspecified.
- New window metadata is separate in ablation-config.json. No normalization of
  changed physics or new fields is allowed to weaken baseline summary parity.

## Pre-registered prediction and falsification
B prediction: if finite TA in-flight occupancy and accepted-TAACK turnover are
material on MC's tail, raising the window will reduce explicit full-window
eligibility intervals and may shorten MC weight readiness relative to Chunk.
The result is not assumed monotone: allocator, CBFC, shared-pair scheduling, and
collective eligibility can dominate or relocate the critical path.
Falsification: no reduction in the relevant measured window-full interval or no
improvement in the MC-minus-Chunk weight delta despite the capacity increase.
Negative, flat and reversed effects remain results, not reasons to alter inputs.
A is inconclusive as a performance ablation because semantic preservation failed.

## Evidence and correctness
Small gate: four accepted fixtures × 100/3136 Gbps × four strategies. At 512 run
accepted/OFF/ON; at 1024/2048 run OFF/ON independently. Keep legacy-parent regression,
compute-unit checks, observer FIFO checks, retransmission/data-once/ack-once and
invalidated-grant smokes at every window, negative payload/premature-completion
checks, strict window/rate CLI bounds, and capacity bounds/maxima. Every successful
run retains online byte/WQE validation, independent CBFC conservation, ingress/
egress bounds, pair-Jetty drain, multicast association drain, compute/readiness
checks, and capacity counters. Required measurements include bounded occupancy,
full-window duration, accepted-TAACK feedback latency, association peaks, native
queue/CBFC evidence, weight timing and unchanged task/payload totals.

Frozen pre/post manifests cover workload and accepted baseline evidence, all
experiment/Planner source, native source, application binaries and native libraries.
Baseline comparison is full private output parity, not only a selected aggregate.

## Checkpoint and resources
Checkpoint policy: continue_full_matrix for a valid negative performance result;
stop admission immediately for correctness, parity, identity, observer or guard
failure. Both fresh 512 baselines must pass before treatments are admitted.
No automatic repair that changes controls, no extra matrix cases, and no hidden
rerun. Full output sets are separate and directories refuse reuse.

Retain 6 GiB process-tree RSS, 7 GiB address space, 1 GiB host memory reserve,
8 GiB free output disk, 2 GiB free /tmp, and 4800 seconds for the whole case.
One interruption-owning coordinator permits at most two cases using peak-aware
admission. Baseline reserves accepted observed peak ×1.05 plus 128 MiB. Unknown
larger-window cases reserve the full 6 GiB cap, not an optimistic baseline peak;
this normally serializes them on the current 10 GiB host. Keep 128 MiB additional
admission margin and CPU/load/disk checks. Never blindly launch four processes.
Unavailable admission stops after 600 seconds without lowering a limit.

## Artifact contract and stopping condition
Each of six real cases yields independent input copies, exact command, resource
records, validation, online summary, expert/replica readiness, capacity counters,
network/pair/multicast lifecycle evidence, bounded diagnostics and run-result.json.
The formal ledger includes the two stopped A rows and their exact audit reason.
After the six authorized runs and analysis finish, stop and await user acceptance.
