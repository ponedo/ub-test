# N256 chunk-streaming multicast: formal results

## Result and scope

All five strategies passed at the single fixed 256-token point. NoBal, Direct and CS+MC were newly executed sequentially; the previously accepted CS and MC results were reused after exact input/native-library checks, twelve paired original-mode regressions and independent review. This is not a token sweep, stability study or crossover estimate.

| Strategy | Evidence | Full layer (µs) | Weight stage (µs) | Source weight payload (bytes) | Source weight wire (bytes) |
|---|---|---:|---:|---:|---:|
| NoBal | NEW | 102.942153 | 0 | 0 | 0 |
| Direct | NEW | 957.622688 | 921.500622 | 830,472,192 | 893,730,816 |
| CS | REUSED | 727.245670 | 691.082182 | 830,472,192 | 893,730,816 |
| MC | REUSED | 932.419197 | 896.326667 | 396,361,728 | 466,071,552 |
| CS+MC | NEW | 635.815360 | 599.722514 | 677,476,352 | 743,609,524 |

CS+MC reduces the weight-stage duration by **13.22%** and full-layer latency by **12.57%** relative to CS. Full-layer speedup over CS is 1.143800×. It is 33.60% below Direct and 31.81% below MC on layer latency. Its source payload and wire bytes fall 18.42% and 16.80% relative to CS, respectively. Downstream native weight wire bytes remain 893,730,816 across the balanced strategies.

**NoBal is still fastest overall at N256.** It intentionally has a main-only plan with zero replicas and no weight transfers; its zero weight duration is not a speedup denominator. The four balanced strategies share the exact plan and assignments (maximum NPU assignment load 34); NoBal has a different main-only assignment (maximum load 186). CS+MC is the fastest balanced strategy in this one case, not the overall winner.

The measurements are correlated outcomes, not a causal decomposition. In particular, source-byte reduction alone does not explain the latency ordering: MC sends fewer source bytes than CS+MC yet finishes later. No additional ablation was run to assign latency gains to one hop, expert, feedback mechanism or arbitration category.

## Actual merge coverage, not ideal grouping

The unchanged CS graph has 23,079 weight tasks, grouped into 13,844 fixed operations: 4,608 Stage I chunks, 9,216 Stage II chunks and 20 whole-expert graph fallback groups. There are 9,233 multi-target operations and 4,611 singleton operations. The theoretical all-group perfect-merge payload bound is 23 × 18 MiB = 434,110,464 bytes. Actual source payload is 677,476,352 bytes; the bound is not an achieved result.

| Graph role | Groups with any envelope / groups | Actual envelopes | Logical member payload carried in envelopes | Native-unicast fallback payload (bytes) |
|---|---:|---:|---:|---:|
| Stage I chunks | 512 / 4,608 | 1,050 | 5.6966% | 35,598,336 |
| Stage II chunks | 165 / 9,216 | 544 | 1.9676% | 55,508,992 |
| Whole-expert graph fallback | 17 / 20 | 142,650 | 40.4072% | 438,663,168 |

Stage I and Stage II multicast coverage is low, although both hops genuinely emitted envelopes. Stage II includes 4,608 singleton operations; considering only its 4,608 multi-target operations, 165 (3.5807%) merged at least once. Whole-expert groups account for most observed envelopes. These whole-expert operations were already in the original CS graph and remain whole-expert transfers, not chunked replacements.

Two different meanings of “fallback” must not be conflated:

1. **Whole-expert graph fallback** (`graph_role=direct-fallback`) is a fixed original graph shape. Such a group can still use an envelope opportunistically.
2. **Native-unicast fallback** is the runtime decision to immediately emit the originally selected native packet when all fixed member heads cannot merge now. It occurs in every graph role, including whole-expert groups.

There were 144,244 envelopes, carrying 147,705,856 source payload bytes and reconstructing 300,701,696 logical member payload bytes. Another 517,354 native-unicast packets carried 529,770,496 bytes. The actual original native first-send total remains 811,008 packets and 830,472,192 bytes. Envelope + fallback accounting conserves the original logical member payload. Fallback reason counters count actual selected packet pulls, not hypothetical merge opportunities; detailed reason and fanout tables are included.

## Readiness, completion and safe drain

Expert 45 is the last replica-ready expert in every balanced strategy. Direct, CS and MC finish receiver readiness at target 59; CS+MC finishes at target 49. In CS+MC, the last original CS chunk is task 22541, source relay 23, target 49, offset 18,870,272, length 4,096 bytes.

For CS+MC:

- Planning ends at 201,000 ps.
- The final replica receiver is ready at 599,923,514 ps; the measured weight duration is therefore 599,722,514 ps.
- The final weight sender WQE completes later, at 610,655,845 ps.
- Full-layer completion is 635,816,360 ps, measured from layer start 1,000 ps.

Receiver readiness, sender WQE completion and native transport drain are distinct milestones. No claim is made that sender/native state is drained when the receiver becomes ready. All 2,750 native TP state rows are safe at final validation; pending native descriptors, active WQEs and timers are drained under the verifier's conditions. Native credit conservation holds with legitimate batching residuals; **not all credit counters are zero and “all credits returned” is not claimed**.

The hybrid observer reports 694 codec allocations and retirements, maximum 537 live codecs, and zero terminal active codecs, pending member associations and pending association entries. The finite graph descriptor count is 55,355, below 131,072. Runtime retry counters are scoped to installed hybrid source proxies, not all network channels; no loss was injected in formal runs. The original same-expert/same-chunk GroupChunk dependency barrier and immediate native submission are preserved.

## Validation and provenance

- All five cases produce combine hash `d3acc773b80e9925`.
- CS and CS+MC produce the same executed graph hash, `716b18790ac6b969`; the six graph-bearing files are byte-identical.
- Phase B passed all 38 declared rows, all 14 required coverage categories and all 12 exact paired original-mode regressions. The JSON additionally contains a parity aggregate witness, hence 39 result rows.
- The F03 cumulative-ACK oracle correction is explicitly post hoc. It imports preserved original evidence with the original STOPPED record retained; it did not rerun the simulator. Evidence demonstrates a covering same-TP ACK and safe terminal state, not the instantaneous `sndUna` advancement timestamp.
- Reused accepted CS/MC controls retain their original result hashes. Exactly two documented administrative publication-file hashes were reconciled against accepted Git blobs; execution inputs, native sources, libraries, binaries and result outputs were not edited.
- Complete gate identity checks cover 7,460 entries before and after the campaign and each of its 12 guarded stages. Formal result and output manifests are included by hash in `runtime-provenance.json`.

### Native patch status

**No new native patch and no native rebuild were performed for CS+MC.** The APP-only binary links the unchanged accepted native library closure. `inherited-native-patches.csv` lists the exact six pre-existing patches and their SHA-256 hashes in inherited order; `native-source-manifest.csv` and `app-include-source-manifest.csv` pin the actual source/build closure. The inherited allocator, native protocol/window machinery and wire codec are unchanged.

The candidate eligibility implementation currently merges accepted 78-byte native WRITE headers. Unsupported header layouts fall back to native unicast. The codec remains unchanged, but generic variable-header merging was not demonstrated. Other unsupported tests are documented in the validation evidence; no claim is made about native SSN wrap, true packet reordering, persistent loss/exhaustion, source-envelope loss, lost CBFC credits or multi-switch reliability.

## Host resources and guards

New simulation host times were 13.06 s (NoBal), 427.53 s (Direct) and 778.42 s (CS+MC). The hybrid sampled process-tree RSS peak was 2,797,223,936 bytes, while the Direct run peaked at 2,859,765,760 bytes. The recorded accepted CS and MC host times were 577.27 s and 475.01 s, respectively. Reused control costs are historical accepted measurements, not reruns; simulated speedups must not be described as host execution speedups. Hybrid execution used more host time than accepted CS in these observations.

All runs were sequential, with no concurrent native build or simulator. Limits remained 6 GiB process-tree RSS, 7 GiB address space and 4,800 seconds per guarded stage; admission required 7 GiB host available memory, 8 GiB disk and 2 GiB temporary disk reserves, with a 1 GiB host reserve monitored during execution. No resource guard fired. Exact stage host resources and NEW/REUSED provenance are in the CSV exports.

## Arbitration and feedback interpretation

The `hotspots/` export separates global observations from the terminal-weight source and return-egress ports, and retains their selected observation windows. Global NoIngress, Rejected, effective-grant, TPACK/TAACK and VOQ residence metrics are not interchangeable with a critical path. A global event count multiplied by the native 5 ns arbitration interval is **not** layer latency. No phase-specific TPACK/TAACK split or selected-TA RTT is fabricated where the original bounded observer did not record it.

## Files and reproducibility

- `five-strategy-results.csv`: exact measured performance and host provenance.
- `timeline.csv`, `per-npu-load.csv`: phase milestones and assignment loads.
- `hybrid-stage-summary.csv`, `hybrid-stage-fanout.csv`: measured graph-role/fanout accounting.
- `hybrid-unicast-fallback-reasons.csv`: actual native fallback conditions, packet counts and bytes.
- `expert-ready.csv`, `critical-expert-ready.csv`, `critical-weight-completion.csv`: per-expert readiness and separate last receiver/sender milestones.
- `host-resource-provenance.csv`, `resource-guard-summary.json`: guarded host measurements and limits.
- `input-graph-hashes.csv`, `runtime-provenance.json`, source/patch manifests: exact identities.
- `latency.svg`, `source-weight-traffic.svg`, `hybrid-envelope-coverage.svg`: deterministic aggregate plots, with CSV values as the authoritative numeric source.
- `plot_results.py`: standard-library plot generator that reads only delivered CSV files and regenerates all three SVGs byte-identically. No simulation, raw trace, per-token record or payload is required.

The report and aggregates were independently reviewed. No additional formal simulation was performed to create these tables or figures.
