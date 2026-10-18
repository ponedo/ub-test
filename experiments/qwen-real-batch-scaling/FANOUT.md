# Read-only Relay eligibility and graph statistics

Pinned authority: [production C++ weight-distribution.h](https://github.com/ponedo/ub-test/blob/93bdf7fef154743738910da9e561d796f5955507/experiments/direct-weight-forward/weight-distribution.h), `RelayWeightDistribution::Edges`. Adapter translation and dependencies: [adapter.py](https://github.com/ponedo/ub-test/blob/93bdf7fef154743738910da9e561d796f5955507/experiments/multi-npu-relay/adapter.py). This helper changes no planner, strategy, protocol, parameter, input or simulator code. It reads unchanged generated artifacts; its output is aggregate-only.

## Exact eligibility

For each expert, R is the number of replica physical instances **excluding the main**. If R <= 1, nr = 0. Otherwise nr = min(floor(sqrt(R)), relay_max_relays, R−1). With nr > 0, gain = R − max(nr, ceil((R−nr)/nr)). Eligibility is nr > 0 AND (force_relay OR (R >= relay_min_replicas AND gain >= relay_min_fanout_gain)). Defaults in the adapter are minimum 4 replicas, maximum 8 relays, minimum gain 2, force false. The helper reads actual parameters and does not replace them with defaults.

The production graph also rejects zero nodes/weight bytes/chunk bytes/max relays, shardCut >= weight bytes, invalid optional scale-up domains, duplicate physical IDs, out-of-range ranks and mismatched replica main ID/rank or a replica placed on its main's rank. Adapter validation additionally bounds parameters and weight-task count. Those are input/preflight guards, not alternative per-expert eligibility thresholds. A valid graph is required before statistics are emitted. The helper adds strict unique-main and orphan-replica checks rather than certifying malformed planner inputs.

Main processing order is (rank, physical ID). Replica order is the original ordinal_physical_order for relay strategies, never sorted replica IDs. Selected relay ties use already-used rank, persistent sender byte load, rank, then replica ordinal. Unselected leaves retain ordinal order, and their assignment updates persistent cross-expert loads. Main-to-selected edges and selected-to-leaf edges use the unchanged production iteration order. Therefore thresholds alone do not identify actual relay nodes.

## Definitions

- physical_instances_including_main: physical planner records, including the main. This counts instances, not distinct ranks.
- new_replicas_excluding_main: physical records marked replica. “New” means replica placements in this plan relative to its sole main; it is not an incremental change from another run.
- eligible_experts: exact predicate above, independent of whether the chosen strategy is Direct. Direct may have eligible experts and zero actual relays.
- actual_relay_experts: experts with at least one actual graph edge whose source is a replica.
- relay_physical_count: distinct replica physical IDs that actually forward, summed across experts.
- relay_node_count: distinct NPU ranks actually forwarding. At total level ranks are deduplicated across experts, so per-expert counts must not be summed to obtain this total.
- main_outgoing_copies: distinct target physical instances of main-origin edges. One whole expert image per target; chunk tasks are not additional copies.
- main_outgoing_tasks / forwarded_tasks: actual graph edge/task counts split by main versus replica origin. This exposes chunk expansion explicitly.
- direct_fallback_tasks: all tasks belonging to experts without forwarding, including the explicitly Direct strategy. relay_tree_tasks: all tasks belonging to experts with forwarding, including main-to-relay seeds. These categories partition weight_tasks. main_outgoing_tasks + forwarded_tasks independently partitions weight_tasks.
- weight_tasks: all graph tasks, including any same-rank tasks. weight_wqes: tasks with different source and destination ranks. local_weight_tasks: remaining tasks.
- weight_tas: sum ceil(task bytes / segment_bytes) over remote tasks, independently rounded per task; never ceil(total bytes / segment_bytes).
- weight_bytes: sum payload bytes over all graph edges. Includes both main seeds and forwarding, with no headers/acknowledgements. remote_weight_bytes excludes same-rank edges. These are graph-derived expected counters, not measured completion counters or link bytes. Compare against verified simulator counters before describing them as completed.
- reasons: per-expert threshold failure reasons; nr=0 prevents force enabling one/zero replicas. Enabled reason records adaptive versus force mode. Actual enablement comes separately from graph edges.

## Validation and usage

`python3 fanout_stats.py --case /private/prepared/case --out /aggregate/fanout.json`

Requires config.json with explicit runtime relay parameters, plan.json, and weight-edges.csv. Direct/TwoStage/Chunk artifacts are supported. A bare NoBalancing artifact lacking relay parameters or weight-edges.csv needs an explicit caller-side empty-graph wrapper with the same fixed parameter context; do not fabricate missing parameters or infer them from WQE count.

Before publishing a PASS, it independently reconstructs exact graph selection, shard ranges, scopes and submission order; compares the actual edge multiset and ordered sequence; checks config transfer endpoints/ranges/ranks/task identities; and reconstructs exact full-expert or group-chunk dependencies. Tampered, missing, duplicated or reordered edges and dependencies are rejected. The helper is diagnostic evidence, not a replacement for accepted preflight/postflight or source-routing provenance checks.

Tests: compile the pinned, unmodified `../multi-npu-relay/graph-tool.cc` (no simulator build), then `RELAY_GRAPH_TOOL=/path/to/graph-tool python3 -m unittest -v test_fanout_stats`. Six test methods pass, including 120 fixed-seed cross-check graphs across all three strategies with shuffled ordinal order, cross-expert sender loads, force mode, max relay caps, varied gains, FC1/FC2 boundaries, tails, same-rank forwarding and malformed graph mutations. Tests contain synthetic placements only.
