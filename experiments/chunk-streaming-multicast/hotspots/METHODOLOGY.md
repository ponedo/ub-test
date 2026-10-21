# N256 arbitration and feedback hotspot export

This is read-only post-processing of the five completed formal N256 runs. No simulation, model change, dependency installation, publication, raw packet export, payload export, or per-token export is performed. `NEW` identifies the completed Phase C no-balancing/direct/CS+MC runs; `REUSED_ACCEPTED` identifies the original accepted CS/MC runs, not the empty prepared placeholders.

## Files

- `global-arbitration-feedback.csv`: five whole-run and five weight-phase rows. Includes requested, effective/committed, Rejected, and NoIngress grants; full-run physical TPACK/TAACK frames and bytes; logical remote TAs; accepted sender TAACKs; resource peaks. Weight-phase opcode-split feedback fields are intentionally blank.
- `critical-source-return-egress.csv`: critical weight-source host port and its shared return egress, separately for whole-run and weight-phase observations. It includes classed VOQ residence and exact weight-window port partitions. No-balancing has two explicit not-applicable rows.
- `return-egress-hotspots.csv`: top eight observed switch return egress ports per strategy/scope, ranked by class-1 VOQ residence sum, then class-1 TX count, then port. There are five whole-run sets and four weight-phase sets.
- `voq-stats.csv`: global VOQ sample count, sum, maximum, and sample-weighted mean, separately by scope and traffic class. Empty means indicate no samples, not measured zero latency.
- `source-feedback.csv`: all 64 sources per strategy, whole-run TPACK/TAACK reconciliation, and weight-attributable return feedback after graph-derived token subtraction. There are no task/token/payload identifiers.
- `diagnostic-coverage.csv`: applicability, measured timing boundaries, terminal sources, observed port coverage, bounded-ring status, and unavailable metrics.
- `source-input-hashes.csv`: SHA-256 and size of every input consumed. All source paths are relative to the task workspace root. This includes aggregate transfer metadata used only for source-level selection and reconciliation; those records are not copied to the output.
- `export-verification.json`: validation and conservation checks, source stability checks, and limitations.
- The historical diagnostic exporter is not bundled. These tables are bounded, hash-verified extracts from retained private run evidence; their metric definitions and conservation checks are documented below. The public simulator harness generates the corresponding diagnostic inputs for authorized fresh runs.

## Scopes and metric definitions

Native metric 2 is requested grant service; metric 10 is an effective/committed grant; metrics 8 and 9 are Rejected and NoIngress outcome counts and observed elapsed picoseconds. The requested service is 5,000 ps per start in these runs. Whole-run requested counts equal effective + Rejected + NoIngress, and effective grants equal physical TX frames at every port, including credits.

`whole_run` means the entire recorded simulator lifecycle, including feedback/drain after layer completion, not a clip at LayerLatency. `weight_phase_event_cohorts` means starts inside the weight window for requested service/TX, but ends inside that window for VOQ residence and grant outcomes. Full residence/service values are retained, not clipped to the window. Therefore phase starts minus phase outcomes can be nonzero without an instrumentation error.

Metric 0 is native VOQ packet residence. Counts and sums are summed across the requested ports/classes; maximum is the largest recorded sample; mean is sum/count. Classes are 0 = stage-2 weight; 1 = all TPACK plus weight TAACK; 2 = other traffic, including token TAACK and credits. Exact TPACK-only versus TAACK-only VOQ residence is not recorded. The hotspot ranking uses class 1, not all feedback opcodes, and therefore excludes token TAACK. The all/class-2 columns remain visible rather than silently relabeling class 1 as complete feedback.

Physical TPACK = packet-counts kind `transport_ack`; physical TAACK = `transaction_response`. Counts include both physical links. Each logical remote TA produces two TPACKs and one TAACK, each traversing two links: whole-run TPACK = 4 × logical remote TA count and TAACK = 2 × logical remote TA count. These are physical transmissions, not unique logical ACK messages. Accepted TAACKs at senders are separately counted once per TA.

For source s, switch node 64/port s is the return egress to host s. Its whole-run TPACK count equals outgoing + incoming logical TAs, and its TAACK count equals outgoing TAs. Weight-attributable counts subtract token contributions over the whole lifecycle; they are not phase-filtered counts. Relay sources can receive weights as well as send them.

`peak_voq_out_bytes_whole_run` and global maximum peak columns come directly from per-port network-resource statistics. The exported global peak is the maximum of per-port peaks, never the sum of nonsimultaneous peaks. These are separate from VOQ residence samples and from diagnostic observer-record peaks. No queue-depth histogram or VOQ p95/p99 can be derived from count/sum/max alone.

## Critical source and exact interval accounting

Every transfer tied at the actual maximum receiver-ready timestamp is selected; that time must match the recorded WeightReady. No historical source is presumed critical. The selected source/terminal target pairs are Direct 22→59, CS 23→59, MC 22→59, and CS+MC 23→49. These are terminal weight paths, not a complete causal layer-latency attribution.

For each selected host source, its own last native dequeue boundary is verified against all of that source's aggregate weight-transfer observations. The recorded prefix partition is retained separately from the gap to WeightReady; that gap is not labeled network latency or sender-completion latency. Exact partition fields are TX-busy union, allocator-pending excluding TX, and uncovered idle; they conserve the measured per-port window. Uncovered idle is not attributed to any particular eligibility cause.

No-balancing has no stage-2 weight transfers, no weight window, and no critical weight source. Its whole-run feedback and arbitration are measured normally. The zero-duration placeholder partition is not exported as a meaningful measured weight phase. Missing phase/critical values are blank with explicit status, not fabricated zero waits.

The four weight strategies have 122 recorded weight-window port partitions out of 128 physical ports. Unobserved switch ports have no measured phase partition. The export ranks only recorded phase ports and does not invent an idle partition for the other ports.

## Interpretation limits and checks

Global counts × 5 ns are allocator resource workload, not LayerLatency, not a new elapsed-time bound, and not causal speedup attribution. VOQ residence sums overlap among packets; per-port partitions overlap across ports. Do not add global service, queue residence, or multi-port partitions into a layer latency decomposition. LayerLatency and WeightDuration are provided only as independently measured reference values in coverage.

Selected TA RTT capture was disabled by impossible source/group selectors in every run. Its empty/zero counters do not mean zero RTT and cannot establish ACK-path latency or global duplicate coverage. The bounded native event rings were overwritten in weight strategies; the exporter does not consume or export raw rings, and no complete packet-chain explanation is claimed.

Validation checks cover healthy existing diagnostic status; zero open/unmatched FIFO/grant observations; unique aggregate keys; phase cohort schema/subset consistency; whole-run allocator outcomes; every physical port's commit/TX/dequeue equality; source-level feedback/TA reconciliation; Jetty admissions/accepted-TAACK/SSN progress and terminal drain; terminal-weight/source-prefix boundaries; exact partition conservation; equality with original accepted CS/MC aggregate totals; and unchanged SHA-256 for all consumed inputs. These are export-consistency checks, not a new simulator or model validation run.

## Compact observations

The four weight strategies have identical whole-run physical feedback totals: 3,369,024 TPACK frames and 1,684,512 TAACK frames. No-balancing has 128,768 and 64,384 respectively.

Whole-run Rejected grants are zero for NoBal, Direct, CS, and CS+MC; MC records 34,969. Whole-run NoIngress counts are 106,497 / 1,682,192 / 1,547,848 / 1,460,522 / 1,306,614 in NoBal / Direct / CS / MC / CS+MC order. These are observed outcomes, not direct explanations for relative layer latency.

The highest class-1 weight-window VOQ-sum return port is 22 for Direct, 57 for CS, 22 for MC, and 36 for CS+MC. A highest aggregate hotspot need not be the terminal weight source's return egress. In particular, CS+MC's terminal weight source is 23 while its highest aggregate class-1 return hotspot is port 36.
