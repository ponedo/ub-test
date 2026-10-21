# CS + Multicast WRITE v2

Completed N256 experiment: [REPORT.md](REPORT.md). CS+MC reduced weight duration by 13.22% and layer latency by 12.57% versus CS; NoBal remains fastest overall. Most envelopes belong to original whole-expert graph-fallback groups, not the two relay stages.

Start with [REPRODUCE.md](REPRODUCE.md), [DESIGN.md](DESIGN.md), and [NATIVE-PATCH.md](NATIVE-PATCH.md). Fresh small tests use `phase_b_reproduce.py`; `phase_b.py` and `phase_b_extension.py` preserve the original staged experiment and reviewed historical correction. All 50 fresh small executions passed. Exact real N256 reproduction requires authorized private inputs, which are not uploaded.

[Five-strategy CSV](five-strategy-results.csv) | [Arbitration and feedback](hotspots/global-arbitration-feedback.csv) | [Streaming evidence](results/phase-b/streaming-witnesses.csv)

# Harness reference

Read [DESIGN.md](DESIGN.md), [preregistered-plan.md](preregistered-plan.md), and [matrix.json](matrix.json) before any execution. These are a declared design and gated harness, not proof that tests or formal experiments passed.

## Files

- `layer.cc`, `hybrid-multicast.h`, `hybrid-integration.inc`: isolated candidate APP implementation; old source files are not edited.
- `adapter.py`, `preflight.py`: exact accepted CS graph with transport-only metadata and independent graph/group checks.
- `verify.py`: unchanged generic full-layer checks plus actual hybrid byte/packet/member/lifecycle conservation.
- `fixtures.py`, `test_hybrid_contracts.py`, `phase_b.py`: frozen small correctness matrix, pure tests, runtime witnesses and 12 paired old-mode regressions.
- `build.py`: two-phase APP-only build plan and approval latch against immutable native libraries.
- `prepare.py`, `run.py`: five N256 inputs, exact manifest/review latch, strict CS/MC reuse decision and five-row results.

All generated evidence belongs in a fresh private output directory, outside accepted controls. Default Summary; bounded Events only for predeclared small witnesses. No native rebuild, wait-based multicast, changed native limits, implicit retry or formal run before Phase B/review approval.

## Gated build

1. `python build.py prepare --out NEW_BUILD --native ACCEPTED_NATIVE --accepted-identity ACCEPTED_BUILD_IDENTITY --graph-tool ACCEPTED_GRAPH_TOOL`
2. Review `NEW_BUILD/build-plan.json` and its source/native pins.
3. Parent approval JSON must contain `status: PASS`, `approved_to_build: true`, and exact `build_plan_sha256`.
4. `python build.py execute --out NEW_BUILD --approval BUILD_APPROVAL`

This compiles only the application. A rejected or stopped build requires explicit new review/re-pin and a fresh output directory; the script does not retry.

## Formal preparation and approval

After the complete Phase B gate, use:

`python run.py prepare --private NEW_CAMPAIGN --accepted-campaign ACCEPTED_CAMPAIGN --graph-tool ACCEPTED_GRAPH_TOOL --binary CANDIDATE_LAYER --identity CANDIDATE_RUNTIME_IDENTITY`

Preparation is not simulation approval. Review all five frozen inputs, commands, identities, capacities and expected observability. Formal approval JSON requires `status: PASS`, `approved_to_run: true`, `independent_reviewer`, exact `prepared_manifest_sha256`, and `{path, sha256}` references for `phase_b`, `old_mode_regression`, `independent_review` and `reuse_decision`. Each referenced artifact must be PASS; review/reuse artifacts must bind the same prepared-manifest hash.

The reuse decision contains exactly CS and MC decisions, each with a boolean `reuse` and nonempty `reasons`. A true decision additionally needs explicit checked conditions (`accepted_all_gates_pass`, `same_runtime_options`, `old_paths_unchanged`, `old_mode_exact_parity`, `equivalent_passive_observers`, `all_artifacts_pinned`) and hashed evidence. The runner itself checks exact control input bytes and loaded native library closure. False means one necessary affected baseline run, not a parameter search.

`python run.py execute --private NEW_CAMPAIGN --approval FORMAL_APPROVAL`

The runner stops on the first failed guard or correctness gate. Successful results appear in `five-strategy-results.json` and a compact `results.csv`, retaining NEW/REUSED provenance. Keep raw/private routing, payload and packet detail out of public deliverables.
