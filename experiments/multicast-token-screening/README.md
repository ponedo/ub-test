# Fixed 256-token screening

This is a new, minimal harness over the accepted full-Layer implementation at
`3521a64fd300938af3af4573a9793c4cde8d9649`. It does not alter the native protocol,
allocator, application executor, planner, graph compiler, or observers.

The only formal cases are Chunk Streaming and Multicast v2 at 3136 Gbps, using
the exact cached 256-token real source prefix and a shared natural layer-37
plan. There are no 512/1024-token cases and no 2048-token baseline rerun.
Each strategy runs once. A successful pair can show a deterministic reversal;
it does not establish repeated-run stability or the minimum token count.

## Frozen conditions

- 64 endpoints plus one switch; link propagation **20 ns**, not 5 ns.
- Original allocator allocation service **5 ns**; TP packet window 1000.
- Jetty TA window 512, out-of-order ACK window 2048.
- Roofline 100 decimal TFLOP/s and HBM 2692 decimal GB/s.
- Full Layer including planning, weights, dispatch, compute and combine.
- 44 natural replicas, 21 replicated experts, max fanout 5.
- Activation BF16, idealized FP8 weights, model dimension 4096, FF dimension
  1536, three matrices, weight bytes per expert 18,874,368, segment 1024 bytes.
- Natural plan semantic SHA256:
  `5df5e9b331e487985f0b53a8e0485e9acc477bd71d756430029f8b7427bed06d`.
  Normalization removes **only** `cpu_wall_ns`; both output plans and assignment
  files are additionally required to be byte-identical to the shared source.

## Preparation and review

The runner invokes the unchanged accepted resource guard for source validation,
preparation, graph preflight, each simulator, and every postflight stage. Source
validation reuses the accepted raw-source prefix audit, including source Git
blob identities and frozen counts. Preparation copies one cached direct input,
changes only its link bandwidth to 3136, and calls the accepted integration
adapter for both strategies. It never solves or manually changes the plan.

Run `run.py prepare` with explicit private paths for `--private`, `--source`,
`--routing`, `--manifest`, `--counts`, `--binary`, `--graph-tool` and `--identity`.
The identity file is a nonempty JSON mapping of absolute filenames to SHA256,
covering the verified accepted source/native runtime and loaded binaries. The
runner also binds its own Python files and binary identities.

Preparation writes `prepared-manifest.json` and stops. Before formal execution,
an independent read-only review must verify scope, provenance, graph identities,
resource limits, bounded-observer capacity and all intended command arguments.
Only after approval may a separate JSON file contain:

```json
{
  "status": "PASS",
  "approved_to_run": true,
  "independent_reviewer": "independent reviewer identity",
  "prepared_manifest_sha256": "SHA256 of the reviewed prepared-manifest.json",
  "minimal_gates": {"path": "private gate result JSON", "sha256": "its SHA256"},
  "independent_review": {"path": "private review result JSON", "sha256": "its SHA256"}
}
```

Both evidence JSON files must report `status: PASS`; the independent review also
binds the same `prepared_manifest_sha256`. Minimal gates cover unchanged
source/runtime hashes, default parameter assertions, the unchanged accepted
observer/native-window unit checks and model oracle, and packet-work/opcode
cohort semantics. Existing passive-observer validation is retained; no new
synthetic token simulation is added to this quick task. These checks are not
additional real-token screening cases.

Run `run.py run --private CAMPAIGN --approval APPROVAL.json` to admit exactly the
two sequential cases. Neither preparation nor tests create approval. Existing
stage outputs and stopped/completed campaigns cannot be silently resumed or
rerun. The first failure stops subsequent admission. A visible other simulator
or unavailable full RSS allowance plus host reserve prevents admission.

Each guarded stage atomically updates a small private host heartbeat every
second with its driver and observed owned descendant PIDs, process start times,
PID namespace IDs, session IDs, last sample time and current tree RSS. It does
not change native instrumentation. An old RUNNING heartbeat after a disconnected
session means an uncertain attempt, not permission to duplicate it. Interrupted
attempts are preserved, and the accepted guard retains ownership cleanup.

`test_harness.py` and `test_analyze.py` are unit tests, not simulator gates. Their
execution is recorded distinctly from the two formal runs.

## Lightweight observations, unchanged correctness

The existing bounded observer is enabled with all 65 nodes. Both observer-only
source and group selectors use the non-matching value 4294967294. This suppresses
selected TA/RTT correlation, not traffic, global Jetty occupancy, native port
statistics, phase partitions, transfer landmarks or packet counts. UINT32_MAX
would mean all and is deliberately **not** used. The unmodified observer may
still emit fixed-size rings privately; the aggregate analyzer neither reads nor
publishes them. Selected-detail zero counters are not global completeness proof.

Postflight keeps the accepted input/graph reconstruction, full online checks,
independent integration/network/pair-state checks, and Roofline computation
verifier. It then aggregates WeightDuration, all tied critical transfers, actual
critical-source and hot return ports, exclusive phase time partitions, allocator
callback outcomes, TPACK/TAACK packet counts, window saturation, envelopes/fanout,
and simulator CPU/wall/RSS. Overlapping residence sums are never added as wall
time. ACK and transaction response are combined in the native phase class, while
the separate opcode packet counts cover the whole Layer.

No universal Chunk drop/retry counter is invented: the no-loss claim states its
basis in exact expected work, full target byte checks, drained protocol state and
physical link packet/byte conservation, with retries disabled. MC additionally
requires its explicit injected-loss and native-retry counters to be zero.

Only sanitized aggregates and this harness may be published. Private raw source,
routing, mappings, complete transfer logs, token/payload data and observer rings
remain outside the repository.


## Completed campaign

Both authorized N256 formal cases and all correctness postflights passed. The
actual run retained all 65 native nodes, the shared natural plan, original
allocator, default windows and full Layer. No other real-token sizes or retries
were run. N256 reproduced a 29.699% Multicast WeightDuration reversal.

See REPORT.md for the result, run-ledger.md for exact attempts/host costs and
correctness-gates.json for sanitized validation evidence. This completion note
is post-run administrative documentation; executed source and harness code were
not modified. No global-minimum or repeated-run-stability claim is made.
