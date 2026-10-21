# Reproduce the gated APP experiment

These are the supported script interfaces, not permission to bypass approval gates. Run from the application repository root, with Python assertions enabled (`PYTHONOPTIMIZE` unset or `0`). Set `APP=experiments/chunk-streaming-multicast`. All other uppercase shell variables below are **operator-supplied verified paths**, not bundled files or suggested absolute locations. Every `NEW_*` output must be fresh; its parent must already exist.

Required inputs are the accepted native build and full identity, accepted application executable, accepted graph tool, frozen candidate source, and independently reviewed approvals. The scripts pin path-aware identities and reject drift. Do not rewrite an identity just to make a failed check pass. See `NATIVE-PATCH.md` for the inherited native chain.

## 1. Clean application build, not native restoration

```sh
python3 "$APP/build.py" prepare \
  --out "$NEW_BUILD" --native "$ACCEPTED_NATIVE" \
  --accepted-identity "$ACCEPTED_BUILD_IDENTITY" \
  --graph-tool "$ACCEPTED_GRAPH_TOOL"
```

Review `build-plan.json`, its actual APP include closure, the accepted native/library pins and resource admission. `BUILD_APPROVAL` must be a reviewed JSON receipt containing `status: PASS`, `approved_to_build: true` and the exact `build_plan_sha256`. Preparation alone runs no compiler and grants no execution authority.

```sh
python3 "$APP/build.py" execute --out "$NEW_BUILD" --approval "$BUILD_APPROVAL"
```

Outputs include `layer`, `runtime-identity.json` and `provenance.json`. The command compiles only APP code against existing accepted libraries. Missing or changed native artifacts are a blocker, not a reason to rebuild native. A stopped build is not implicitly retried.

## 2. Fresh Phase-B preparation and execution

Use the additive `phase_b_reproduce.py` entry point for a clean run. It reuses the original fixture matrix, preparation, execution loop, resource guards, approval gates, negative checks and parity checks. Only fresh F03 verification uses the reviewed cumulative-ACK oracle. All 50 declared simulator executions run; no archived evidence is imported or execution skipped. The original `phase_b.py` remains unchanged.

```sh
python3 "$APP/phase_b_reproduce.py" prepare \
  --out "$NEW_B" --binary "$NEW_BUILD/layer" \
  --accepted-binary "$ACCEPTED_LAYER" \
  --runtime-identity "$NEW_BUILD/runtime-identity.json" \
  --accepted-identity "$ACCEPTED_BUILD_IDENTITY" \
  --graph-tool "$ACCEPTED_GRAPH_TOOL"
```

This constructs and checks declared small fixtures, freezes commands, and runs no simulator. Review the complete prepared manifest before supplying `B_APPROVAL`: `status: PASS`, `approved_to_run: true`, `phase: B`, exact `prepared_manifest_sha256`, and `row_ids` equal to the next declared contiguous prefix. A reviewed continuation of a **PAUSED** prefix additionally binds its prior ledger hash and sets `approved_to_continue: true`. A **STOPPED** ledger cannot be resumed with this interface.

```sh
python3 "$APP/phase_b_reproduce.py" execute --out "$NEW_B" --approval "$B_APPROVAL"
```

The runner stops on the first failure and preserves evidence. It includes twelve accepted/candidate old-mode comparison pairs. The wrapper writes `f03-cumulative-ack-witness.json` for the original F03 fixture only: observed PSNs 0–11 without wrap, lost task 128 / PSN 9 / reverse TP 9→2. It does not generalize the oracle to arbitrary loss tests. Its source and checker are included in the new preparation identity. A successful fresh run ends in `phase-b.json` with complete PASS coverage and `old-mode-regression.json` with twelve PASS pairs. It needs no archival continuation.

The independently reviewed additive wrapper passed seven pure tests and a fresh complete live validation: all 50 simulator executions were NEW, all 38 declared rows and 14 required coverage categories passed, and all twelve old-mode comparison pairs matched exactly. No prior evidence was imported, no guard failed, and no formal simulation was rerun. Validation receipt SHA-256: `91c83711e3703c238118834e9b9eb6ebd241fc3725c912fff63746a58bfaa658`; fresh `phase-b.json` SHA-256: `1401021e7c90729bc463a7f5d68ce889195a3423bf2c75d008a4d4694b3c321d`.

## 3. Exact historical F03 correction and continuation (audit only)

This section explains the evidence used by the completed formal campaign; it is not needed for the fresh workflow above. F03's simulation and payload validation succeeded, but the original checker incorrectly required a later cumulative TPACK to retain the dropped ACK's task tag. Native ACK tags belong to their triggering packet; recovery is scoped to the directed TP and 24-bit PSN. The additive checker reads preserved outputs only:

```sh
python3 "$APP/ack_oracle.py" "$PRESERVED_B/runs/F03/candidate" \
  --out "$POSTHOC_RECEIPT"
python3 "$APP/phase_b_extension.py" prepare \
  --base "$PRESERVED_B" --out "$NEW_EXTENSION" --receipt "$POSTHOC_RECEIPT"
```

This importer intentionally accepts only the reviewed original v3 manifest digest `9df7df70b91b8bc422f978b9a5a950ee8748c852c51a47465d61840cc77fb34c` and the specific F03 stop. It imports fourteen original PASS rows and one explicitly posthoc-revalidated F03 row, preserves the entire old tree by hash, and copies only unexecuted F04-onward inputs to a fresh tree. No old simulation is rerun and no original verdict is overwritten. These commands are an **archival continuation**, not a generic fresh-run bypass.

`EXTENSION_APPROVAL` must bind the exact new manifest and initial ledger, explicitly set `approved_to_import_prior: true` and `approved_to_continue: true`, bind the posthoc receipt hash, and authorize all remaining declared row IDs, in addition to the normal Phase-B approval fields.

```sh
python3 "$APP/phase_b_extension.py" execute \
  --out "$NEW_EXTENSION" --approval "$EXTENSION_APPROVAL"
```

The accepted receipt proves the unique lost-ACK physical route, later same-pair cumulative ACK coverage and terminal UNA=NXT=12 with drained native state. It does not establish an instantaneous per-ACK UNA timestamp or live PSN wrap. `POSTHOC_F03.md` documents this scope; its statement that Phase C was then unauthorized is historical, not the final campaign status.

The completed historical Phase-B result is PASS: 38 declared rows plus the aggregate witness row, with all required coverage and twelve exact old-mode paired regressions. Do not fabricate that result for a fresh run.

## 4. Formal N256 preparation, reuse and execution

Exact formal reproduction requires authorized private routing/model inputs, the frozen Planner outputs, and the approved accepted campaign artifacts. They are not included in a public code or synthetic-fixture package. Without them, one can inspect the implementation and reproduce small synthetic checks, but cannot claim to regenerate the private N256 result.

```sh
python3 "$APP/run.py" prepare \
  --private "$NEW_C" --accepted-campaign "$APPROVED_ACCEPTED_CAMPAIGN" \
  --graph-tool "$ACCEPTED_GRAPH_TOOL" --binary "$NEW_BUILD/layer" \
  --identity "$NEW_BUILD/runtime-identity.json"
```

Preparation fixes exactly five N256 strategies: NoBal, Direct, CS, MC, CS+MC. It grants no simulation authority. Formal approval must contain `status: PASS`, `approved_to_run: true`, an independent reviewer, the exact prepared-manifest hash, and hashed `{path, sha256}` PASS evidence for `phase_b`, `old_mode_regression`, `independent_review`, and `reuse_decision`. Review and reuse evidence must bind this same prepared manifest.

Historical CS/MC reuse is allowed only after exact seven-file input equality, identical runtime options except executable/output paths, identical loaded ten-library closure, untouched old paths, twelve exact regressions, equally complete passive diagnostics, and pinned accepted artifacts are proved. The explicit CS and MC decisions need reasons, checked conditions and evidence. A false decision authorizes only the reviewed necessary affected control rerun, never a sweep.

In the completed campaign, two administrative files had accepted post-run updates. A separately approved reconciliation retained all 4,019 other identity entries and exposed a fresh read-only accepted-campaign view; the original evidence was not changed. This is not permission to automatically rebase arbitrary stale identities. Supply the approved view/receipt or obtain a new review.

```sh
python3 "$APP/run.py" execute --private "$NEW_C" --approval "$C_APPROVAL"
```

The completed formal result is PASS with NoBal, Direct and CS+MC marked NEW, and CS and MC marked REUSED. Inspect `five-strategy-results.json`, `results.csv`, the ledger and source/native identities together. NoBal's zero weight time is not a weight-speedup denominator.

## Resource and failure boundary

One simulator at a time; no concurrent build, MPI or MTP. Limits are process-tree RSS 6 GiB, address space 7 GiB, 4,800 seconds per stage, at least 7 GiB available host memory before admission and 1 GiB during execution, 8 GiB free case storage and 2 GiB free temporary storage. Formal output is Summary, not full raw Events. Hard failures retain completed evidence and stop admission: no implicit restart, enlarged limits, alternate topology or additional token counts.

All approvals are reviewed artifacts, not files to synthesize from this document. New paths, source changes or replacement inputs require fresh pins and review. The historical evidence receipts are audit anchors, not transferable execution approvals.
