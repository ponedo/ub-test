#!/usr/bin/env python3
"""Generate a formal report exclusively from PASS collected evidence."""
import argparse
import csv
from collections import defaultdict
import json
import os
if not __debug__ or os.environ.get("PYTHONOPTIMIZE"):
    raise RuntimeError("Assertions must remain enabled")
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();r=a.results
read=lambda name:list(csv.DictReader((r/name).open()))
summary=json.loads((r/'summary.json').read_text());assert summary['status']=='PASS'
perf=read('performance.csv'); comparisons=read('comparison.csv');resources=read('resources.csv');compute=read('compute-aggregate.csv')
names={'no-balancing':'No Balancing','direct':'Direct','chunk-streaming':'Chunk Streaming','multicast-v2':'Multicast v2'}
f=lambda x,key:float(x[key]); ms=lambda x,key:f(x,key)/1e6
pick=lambda rate,mode:next(x for x in perf if int(x['link_gbps'])==rate and x['strategy']==mode)
mc=pick(3136,'multicast-v2'); old=pick(100,'multicast-v2');nb=pick(3136,'no-balancing')
chunk=pick(3136,'chunk-streaming'); direct=pick(3136,'direct')
for row in perf:
    assert abs(f(row,'layer_ns')-(f(row,'planner_ns')+max(f(row,'weight_ns'),f(row,'reroute_ns'))+f(row,'post_gate_ns')))<1e-6
balanced=[pick(3136,mode) for mode in ['direct','chunk-streaming','multicast-v2']]
winners=[names[x['strategy']] for x in balanced if f(x,'layer_ns')<f(nb,'layer_ns')]
replication_answer=('None of the three replication/balancing strategies beats No Balancing at 3136 Gbps in this measured workload.' if not winners else 'Strategies beating No Balancing at 3136 Gbps: '+', '.join(winners)+'.')
mc_chunk=next(x for x in comparisons if int(x['link_gbps'])==3136 and x['reference_strategy']=='chunk-streaming')
old_mc_chunk=next(x for x in comparisons if int(x['link_gbps'])==100 and x['reference_strategy']=='chunk-streaming')
lines=['# CloudMatrix-inspired logical aggregate bandwidth: controlled Roofline comparison','',
'## Result and scope','',
replication_answer,
f"No Balancing is {ms(nb,'layer_ns'):.9f} ms; Direct {ms(direct,'layer_ns'):.9f} ms; Chunk Streaming {ms(chunk,'layer_ns'):.9f} ms; Multicast v2 {ms(mc,'layer_ns'):.9f} ms.",
f"Multicast versus Chunk changes from {f(old_mc_chunk,'multicast_layer_speedup'):.4f}× layer speedup at 100 Gbps to **{f(mc_chunk,'multicast_layer_speedup'):.4f}× at 3136 Gbps**. The high-rate result is a reversal: Multicast is {(f(mc,'layer_ns')/f(chunk,'layer_ns')-1)*100:.2f}% longer than Chunk, not faster. It remains only {f(direct,'layer_ns')/f(mc,'layer_ns'):.4f}× faster than Direct.",
'The requested questions whether reduced replication cost makes balancing worthwhile and whether Multicast retains its advantage over Chunk are both answered negatively for this fixed workload. The pre-registered prediction of reduced communication durations is matched; a fully compute-dominated balanced layer is not observed. The completed matrix and strategy-order reversal are retained without tuning protocol, allocator or rate assumptions afterward.', '',
f"For real Qwen3 L37 / 2048 tokens / EP64, the new 3136-Gbps simulation gives Multicast v2 **{ms(mc,'layer_ns'):.6f} ms** layer latency and **{f(mc,'speedup_vs_nobal'):.4f}×** speedup against No Balancing. A ratio below one means slower, not an improvement.",
f"The accepted 100-Gbps Multicast baseline is {ms(old,'layer_ns'):.6f} ms. Changing only the network rate gives {f(old,'layer_ns')/f(mc,'layer_ns'):.4f}× layer speedup for this strategy, not a universal bandwidth scaling law.",'',
'| Rate (Gbps) | Multicast compared with | Weight speedup | Layer speedup | Weight saved (ms) | Layer saved (ms) |',
'|---:|---|---:|---:|---:|---:|']
for x in comparisons:lines.append(f"| {x['link_gbps']} | {names[x['reference_strategy']]} | {f(x,'multicast_weight_speedup'):.4f}× | {f(x,'multicast_layer_speedup'):.4f}× | {ms(x,'weight_saved_ns'):.6f} | {ms(x,'layer_saved_ns'):.6f} |")
lines += ['', '## How much does the bandwidth change reduce latency?', '',
'Each row compares the same strategy’s accepted 100-Gbps baseline with its new 3136-Gbps result. Speedup is old/new time; reduction is (old-new)/old. No Balancing has no replicated-weight interval at either rate, so its weight ratios are N/A rather than zero or infinity.',
'| Strategy | Weight: 100 → 3136 Gbps (ms) | Weight speedup | Weight reduction | Layer: 100 → 3136 Gbps (ms) | Layer speedup | Layer reduction |',
'|---|---:|---:|---:|---:|---:|---:|']
for x in read('bandwidth-effect.csv'):
    ws=f"{f(x,'weight_speedup'):.4f}×" if x['weight_speedup'] else 'N/A'
    wr=f"{100*f(x,'weight_reduction_fraction'):.2f}%" if x['weight_reduction_fraction'] else 'N/A'
    lines.append(f"| {names[x['strategy']]} | {ms(x,'baseline_weight_ns'):.6f} → {ms(x,'new_weight_ns'):.6f} | {ws} | {wr} | {ms(x,'baseline_layer_ns'):.6f} → {ms(x,'new_layer_ns'):.6f} | {f(x,'layer_speedup'):.4f}× | {100*f(x,'layer_reduction_fraction'):.2f}% |")
lines+=['','![Layer comparison](results/layer-comparison.png)','',
'![Multicast pairwise speedups](results/multicast-speedup.png)','',
'## Is replication worthwhile? Exact observed accounting','',
replication_answer,
'The non-overlapping timestamp identity is layer = planner + max(weight, reroute) + post-gate. Unlike the stage-span chart, these three adjacent intervals can be added. Relative to No Balancing, the added pre-gate interval must be smaller than the post-gate saving to obtain a net win. The saving is an observed composite interval, not an isolated compute improvement.',
'| 3136-Gbps strategy | Added pre-gate interval vs NoBal (ms) | Post-gate saving vs NoBal (ms) | Net extra layer time (ms) | Worthwhile here? |',
'|---|---:|---:|---:|---|']
for x in balanced:
    added=f(x,'planner_ns')+max(f(x,'weight_ns'),f(x,'reroute_ns'))-f(nb,'planner_ns')-max(f(nb,'weight_ns'),f(nb,'reroute_ns'))
    saving=f(nb,'post_gate_ns')-f(x,'post_gate_ns')
    extra=f(x,'layer_ns')-f(nb,'layer_ns')
    assert abs(extra-(added-saving))<1e-6
    lines.append(f"| {names[x['strategy']]} | {added/1e6:.9f} | {saving/1e6:.9f} | {extra/1e6:.9f} | {'yes' if extra<0 else 'no'} |")
weight_delta=f(mc,'weight_ns')-f(chunk,'weight_ns')
post_delta=f(mc,'post_gate_ns')-f(chunk,'post_gate_ns')
layer_delta=f(mc,'layer_ns')-f(chunk,'layer_ns')
assert abs(layer_delta-weight_delta-post_delta)<1e-6
lines += ['',f"Multicast minus Chunk at 3136 Gbps is exactly {layer_delta:.3f} ns of extra layer latency: {weight_delta:.3f} ns later weight readiness plus {post_delta:.3f} ns longer post-gate interval (equal 200 ns planner intervals). Thus {100*weight_delta/layer_delta:.2f}% of the observed difference lies before the dispatch gate, in the weight interval. This is timestamp accounting, not proof that one source, allocator round or queue uniquely caused it.",
f"Weight/layer share declines from {100*f(pick(100,'direct'),'weight_layer_fraction'):.2f}% to {100*f(direct,'weight_layer_fraction'):.2f}% for Direct, from {100*f(pick(100,'chunk-streaming'),'weight_layer_fraction'):.2f}% to {100*f(chunk,'weight_layer_fraction'):.2f}% for Chunk, and from {100*f(old,'weight_layer_fraction'):.2f}% to {100*f(mc,'weight_layer_fraction'):.2f}% for Multicast. The remaining high-rate weight shares are still large, and all three dispatch gates are weight-ready constrained. The experiment has not become fully compute-dominated.",
f"At 3136 Gbps the latest-ready experts are Direct {direct['last_weight_ready_experts']}, Chunk {chunk['last_weight_ready_experts']}, and Multicast {mc['last_weight_ready_experts']}. These differ from accepted 100-Gbps Direct {pick(100,'direct')['last_weight_ready_experts']}, Chunk {pick(100,'chunk-streaming')['last_weight_ready_experts']}, and Multicast {old['last_weight_ready_experts']}; a change in the observed final readiness event is not a unique causal-path attribution.", '',

'## Hardware interpretation and fixed assumptions','',
'This is a logical endpoint aggregate model, not a physical seven-link/fabric reconstruction or a hardware measurement. 3136 Gbps = 392 decimal GB/s is the nominal one-direction aggregate of a dual-die package: 2 × 7 × 224 Gbps. It is not 392 GB/s one-way per die, not bandwidth assigned to every physical link, and not verified single-peer throughput.',
'The versioned [CloudMatrix384 v2 source](https://arxiv.org/pdf/2506.12708v2) reports 196 GB/s one-way per die and a 135 GB/s inter-node WRITE measurement per die. Its peer count/concurrency and bandwidth-test message size are not established. [Version 3](https://arxiv.org/pdf/2506.12708v3) removes those numerical specifications; removal alone does not establish a correction. Full references and directionality are in [HARDWARE-REFERENCE.md](HARDWARE-REFERENCE.md).',
'The unchanged 20 ns propagation setting is not the paper’s 2.1 µs end-to-end inter-node WRITE latency or a protocol RTT. The existing 5 ns allocator interval, CBFC settings, transport behavior, packet/TA sizes, topology and queue settings are unchanged. Fixed allocator cadence and protocol/queue costs may limit high-rate scaling; this experiment neither removes them nor measures their unique causal contribution.',
'Compute remains the accepted Roofline-inspired max(compute, HBM) model: 100 TFLOP/s, 2692 decimal GB/s, zero launch charge. The 2692 value is the historical dual-die extrapolation from a v2 single-die MLA measurement, not measured expert-GEMM bandwidth. The model excludes calibrated small-batch efficiency, dequantization/scales and physical cross-die contention. See the accepted [MODEL.md](https://github.com/ponedo/ub-test/blob/3c2275eafea79426a441c819c8b65268492ff08e/experiments/qwen-roofline-compute/MODEL.md).','',
'## Controlled comparison and baseline reuse','',
'Only emitted runtime/parameter link_gbps and the corresponding input rate token change from 100 to 3136. Accepted Planner, assignment, routing, expert dimensions, native code, per-NPU serial scheduling, Weight Ready and compute formulas remain unchanged.',
'100-Gbps rows are reused accepted Roofline evidence at commit 3c2275eafea79426a441c819c8b65268492ff08e, not new full real runs. [source-provenance.json](results/source-provenance.json) records the accepted source audit. baseline-reuse.json proves regenerated baseline config/input/assignment hashes and semantic Planner hashes match all four accepted records. Current source and binary hashes are checked before collection. New binary paths/hashes remain in the private validation record; only identity count/digest is exported, and historical/new binaries are not claimed byte-identical.',
'Current Stage A requires 32 small cases (four fixtures × four strategies × two rates), 16 accepted-100 comparisons, native rate/rounding/credit-cell checks, ordinary UbPort/UbLink serialization of 40-byte credit and 160-byte data frames with 20 ns propagation, and three bounded native fault smokes. The ordinary-link probe checks busy gating, completion/receive timestamps and final idle state; it does not exercise upper-layer protocol processing. Published-baseline comparisons use only available accepted evidence; they do not imply a full historical event replay. All four new real cases must pass online payload, postflight, independent network and independent compute checks with no guard termination.',
'The unchanged Roofline model regression was rerun: 16 positive cases and six expected-negative cases pass; see results/model-unit/status.json. The formal four real runs retain the accepted no-loss default --nativeRetrans=false. Only the data-once and ack-once small fault smokes explicitly enable --nativeRetrans=1; the grant-invalidation smoke adds no new protocol. Disabling native retransmission in the no-loss formal runs does not disable CBFC or remove native ACK, transaction-response and WQE-completion checks. No retries or injected losses are recorded in the real Multicast lifecycle.',
'Native full-build success is not a claim that every native unit-test suite was executed. The reported scope is the model regression, bounded Stage A tests and four independently verified real cases.',
'Actual per-physical-expert token counts, FLOPs, HBM-byte estimates, duration and bottleneck classification are exactly equal between the two rates for each strategy. The common 16,384 expert-token invocations conserve top-k=8 × 2048; aggregate FLOPs are 6 × 2048 × 8 × 4096 × 1536. Different strategies can have different active-expert counts and weight HBM reads due to replicas; equality is checked between rates for each strategy, not incorrectly across all strategies.','',
'## Simulated timings','',
'| Gbps | Strategy | Planner ms | Reroute ms | Weight ms | Dispatch span ms | Compute span ms | Max-node compute ms | Combine span ms | Layer ms | Weight / layer | NoBal speedup |',
'|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
for x in perf:lines.append('| '+str(x['link_gbps'])+' | '+names[x['strategy']]+' | '+' | '.join(f'{ms(x,k):.6f}' for k in ['planner_ns','reroute_ns','weight_ns','dispatch_span_ns','compute_span_ns','compute_max_node_ns','combine_span_ns','layer_ns'])+f" | {100*f(x,'weight_layer_fraction'):.2f}% | {f(x,'speedup_vs_nobal'):.4f}× |")
lines+=['','Stage spans are elapsed first-start to last-end windows and overlap. They are not additive stage costs; summing them double counts concurrent work. Weight/layer is a duration ratio, not a causal attribution of the whole layer.','',
'![Overlapping stage spans](results/stage-spans.png)','',
'## Observed gates and completion constraints','',
'The exact source constraint is dispatch_gate = max(weights_end, reroute_end). The collector verifies that identity, identifies all latest-ready experts from expert-ready.csv, and verifies combine end equals layer end. Timestamps below are absolute simulated picoseconds, not durations. Empty latest-ready entries mean no remote weight readiness event.',
'| Gbps | Strategy | Latest-ready experts | Latest weight-ready ps | Dispatch gate ps | Gate constraint | Latest compute end ps | Combine end / layer end ps |',
'|---:|---|---|---:|---:|---|---:|---:|']
for x in perf:lines.append(f"| {x['link_gbps']} | {names[x['strategy']]} | {x['last_weight_ready_experts'] or 'none'} | {x['last_weight_ready_ps'] or 'none'} | {x['dispatch_gate_ps']} | {x['dispatch_gate_constraint']} | {x['latest_compute_end_ps']} | {x['layer_end_ps']} |")
lines += ['',f"At 3136 Gbps, Multicast’s post-gate interval is {ms(mc,'post_gate_ns'):.6f} ms, versus No Balancing’s {ms(nb,'post_gate_ns'):.6f} ms. Multicast’s layer end is {ms(mc,'after_latest_compute_ns'):.6f} ms after the latest NPU compute end. These intervals contain overlapping dispatch, compute, combine, serialization, credit and queue effects; they are not pure compute or protocol costs.",
'The latest-ready expert explains which observed weight-readiness event reaches the global gate, not a uniquely traced causal path to the final token. The latest compute-end timestamp likewise does not establish the final token’s unique critical path. A bandwidth-only comparison can show timings and constraints but cannot isolate allocator, CBFC, source injection or switch contention without additional controlled interventions. No such interventions were run.','',
'## High-rate counterevidence and source-level hypotheses','',
'Full counter and source-line details are in [HIGH-BANDWIDTH-ANALYSIS.md](HIGH-BANDWIDTH-ANALYSIS.md). The following findings constrain explanations of the Multicast/Chunk reversal; they do not establish a unique cause.']
multicast_rows=read('multicast-aggregate.csv')
mc_stats=next(x for x in multicast_rows if int(x['link_gbps'])==3136)
old_mc_stats=next(x for x in multicast_rows if int(x['link_gbps'])==100)
coalescing={key:int(mc_stats[key]) for key in ['envelopes','native_singleton_packets','payload_bytes','wire_bytes']}
assert coalescing=={key:int(old_mc_stats[key]) for key in coalescing}
assert int(mc_stats['native_retry_packets'])==int(mc_stats['injected_losses'])==0
network={x['strategy']:x for x in read('correctness-aggregate.csv') if int(x['link_gbps'])==3136 and x['strategy'] in ['chunk-streaming','multicast-v2']}
assert all(int(x['total_credit_blocked'])==0 for x in network.values())
peak_voq={mode:int(x['max_port_voq_bytes']) for mode,x in network.items()}
port_counts={mode:int(x['max_switch_port_packets']) for mode,x in network.items()}
feedback_counts={mode:int(x['max_switch_port_feedback_packets']) for mode,x in network.items()}
ready_gap=float(mc_stats['final_ready_after_latest_first_send_ns'])
lines += ['',
f"Measured Multicast coalescing is unchanged across rates: {coalescing['envelopes']:,} envelopes, {coalescing['native_singleton_packets']:,} native singleton packets, {coalescing['payload_bytes']:,} source payload bytes and {coalescing['wire_bytes']:,} source wire bytes. Neither loss of coalescing nor additional payload explains this reversal.",
f"The recorded CBFC blocked counters are zero for both Chunk and Multicast; Multicast lifecycle reports zero native retries and zero injected losses. Maximum per-group association occupancy is {mc_stats['max_association_peak']} against per-group limit {mc_stats['min_group_association_limit']}. These counters do not support a credit-stall, retransmission/loss, or association-capacity-exhaustion explanation. Zero blocked counters are not a claim of zero queueing or zero feedback delay.",
f"The largest recorded per-port VOQ peak is {peak_voq['multicast-v2']:,} B for Multicast versus {peak_voq['chunk-streaming']:,} B for Chunk. The busiest switch output port records {port_counts['multicast-v2']:,} total packets for Multicast versus {port_counts['chunk-streaming']:,} for Chunk. These are full-run per-port maxima, not weight-stage-local statistics; different ports’ peaks must not be summed as simultaneous occupancy. Total port packet counts include all recorded packet types, not solely ACKs/responses. The corresponding maxima for transport-ACK plus transaction-response packets alone are {feedback_counts['multicast-v2']:,} and {feedback_counts['chunk-streaming']:,}.",
f"The final Multicast group has fanout {mc_stats['latest_first_send_fanout']}; its first-send completion is {mc_stats['latest_first_send_done_ps']} ps and the final expert Weight Ready is {mc['last_weight_ready_ps']} ps, a {ready_gap:.3f} ns gap. This small final gap locates the observed ending relative to source completion; it does not attribute the preceding full interval to a single mechanism.",
'The unchanged source uses 5 ns allocation rounds, per-pair round-robin selection and all-member readiness for a multicast grant. ACK and transaction-response traffic is not coalesced. Together with the packet/queue counters, these make packet-service and feedback/readiness gating plausible explanations for non-ideal high-rate scaling. Without controlled interventions or a complete time-resolved causal trace, neither the allocator alone nor feedback alone is established as the unique cause.',
'The model also retains InportProcessingDelay=0 and packet-rate-control=NONE. Switch parse/rebuild processing costs are not hardware-calibrated. These omissions limit physical-hardware conclusions even though the current native simulation passes its correctness checks.','',
'## Host resource evidence','',
'| Strategy | Start UTC | End UTC | Wall seconds | CPU seconds | Peak RSS GiB | Concurrent simulator overlap |',
'|---|---|---|---:|---:|---:|---|']
for x in resources:lines.append(f"| {names[x['strategy']]} | {x['start_utc']} | {x['end_utc']} | {f(x,'wall_seconds'):.3f} | {f(x,'cpu_seconds'):.3f} | {int(x['peak_rss_kib'])/1048576:.3f} | {x['concurrent_overlap'] or 'none'} |")
pressure=json.loads((r/'host-pressure-summary.json').read_text())
receipts=json.loads((r/'build-receipts.json').read_text())
lines+=['',f"Minimum sampled host available memory: {pressure['min_host_available_bytes']/1024**3:.3f} GiB across {pressure['samples']} coordinator samples. This is system-wide, includes unrelated activity and is not a proof about unobserved intervals. resources.csv records per-strategy start/end and simulator overlap; detailed admission events remain private; build-receipts.json retains {len(receipts)} bounded build receipts, including any failures and resumptions.",
'At most two independent case workers; admission uses measured availability, historical peak × 1.05, remaining peak growth, 128 MiB extra margin, 1 GiB available-memory reserve and CPU/load checks. Each case retains 6 GiB tree-RSS, 7 GiB address-space, 4800-second whole-case wall, 8 GiB work-disk/2 GiB tmp free-space limits, an 8 GiB logical payload budget and one-million weight-task limit. Sandboxed process visibility is incomplete. Concurrent host wall/CPU timings are resource evidence, not strict strategy-performance rankings.',
'','## Privacy, limitations and reproduction','',
'Publication is aggregate-only: strategy timings, work/communication/correctness totals, queue maxima without node identifiers, fanout histogram, compact synthetic-test summaries and required per-strategy resource scalars. The explicitly requested last Weight Ready Expert IDs and timestamps are the only retained real expert identifiers. correctness-aggregate.csv reports drained PSN/TA windows, zero outstanding state and total credit conservation, with explicit confirmation that the full private per-port credit and transport-window checks passed. All detailed per-node/per-expert/per-packet tables, online summaries, host receipts/admission events, absolute-path source/binary maps, real inputs and raw traces remain private. Pending batched-credit totals may be nonzero: the checked conservation includes these credits; this is not unacknowledged payload or a claim that every credit counter resets to its initial value.',
'One fixed real layer/token-count point is not a scaling survey. The verified payload is deterministic validation data, not real checkpoint numerical inference. Simulation speedups must not be presented as measured Ascend performance or physical CloudMatrix topology performance.',
'See [README.md](README.md) and reproduce.sh. The script reconstructs no new protocol, runs no old full real Roofline matrix, and refuses non-fresh output. PNG and SVG plots are generated only after strict collection passes.']
a.out.write_text('\n'.join(lines)+'\n')
