# Single-request Qwen3-235B-FP8 real-routing PoC

## Result and boundary

One user-supplied request file was acquired through the user's own approved Hugging Face access and uploaded to the conversation. No gated remote content was fetched by this experiment. The uploaded file’s computed Git blob ID matches the public tree metadata for the chosen request at pinned dataset revision `27febb7b2d24169560a9f6f83d38eb53f94916cf`.

- Source: `Qwen/Qwen3-235B-A22B-FP8/Chinese-SimpleQA/中华文化/206.json` in [core12345/MoE_expert_selection_trace](https://huggingface.co/datasets/core12345/MoE_expert_selection_trace).
- Size: 1,485,105 bytes; SHA-256: `c054b6b9b490229b89bf71a8b4d0a99ecce37d10f677f5905dfdff9b1c20532d`.
- Git blob SHA-1: `2cda327aa5570890e14971e1df0694218438c61f`, exactly matching previously observed public tree metadata. This establishes file correspondence, not collection correctness or original token identity.
- 55 serialized records, each containing exactly 94 layer keys in source order `0` through `93`.
- Record 0: every layer has 22 rows × 8 distinct integer expert IDs. Records 1–54: every layer has 1 row × 8 distinct integer expert IDs. All IDs are in `[0,127]`.
- Record-0 assignment conservation: 22×8=176 per layer, 16,544 over 94 layers. All-record check: 57,152 assignments, 7,144 token-layer rows.
- All 94 record-0 layer CSVs are complete relative to this file's first record and the expected 94-key structure. They remain private. No rows are resampled, deduplicated, sorted, or synthesized.

**Phase interpretation is qualified.** The [dataset card](https://huggingface.co/datasets/core12345/MoE_expert_selection_trace/blob/main/README.md) says record 0 is prefill and later records are decode. The observed 22-row/1-row pattern agrees. The raw file has no explicit phase labels, so this is documentation-supported interpretation, not independent proof of prefill execution. No document-versus-shape discrepancy was observed.

## Identity and serialization limits

CSV columns are `token_id,expert_0,...,expert_7`. Here **token_id means the zero-based source row ordinal**, not a tokenizer vocabulary ID, original external token ID, or independently authenticated position. The file contains no prompt text, tokenizer IDs, embedded request ID, collection seed, original tokenizer/model revision, chunk/batch metadata, or explicit semantic labels for layers and expert rank. Request identifier `206` is filename-derived only. Layer keys and expert-column ordering are preserved exactly; their original model-layer and ranked-gate correspondence remains UNVERIFIABLE. Structural checks cannot prove original token identity.

The raw shape and assignment checks cover all 55 records, but only record 0 contributes to extracted routes and statistics. The 54 later records are never appended to prefill. No cross-layer or cross-request concatenation occurs.

## Aggregate load findings

All 128 experts, including zero-load experts, are included in each layer's metrics. `results/expert-counts.csv` contains 128 counts per layer and source; `count-histograms.csv` gives frequency histograms; `layer-statistics.csv` gives the metrics below.

Across this one request's 94 layers:

| Metric | Real layer minimum | Real layer maximum | Matched Zipf control |
|---|---:|---:|---:|
| Maximum / mean expert load | 8.0000 | 16.0000 | 12.3636 |
| Jain fairness | 0.083276 | 0.252083 | 0.205433 |
| Gini | 0.757635 | 0.922763 | 0.757990 |
| Population CV | 1.722481 | 3.317870 | 1.966664 |
| Hottest expert assignment share | 0.062500 | 0.125000 | 0.096591 |
| Hottest 8 experts assignment share | 0.392045 | 0.823864 | 0.460227 |
| Active experts | 20 | 55 | 60 |

These are descriptive single-request results, not uncertainty estimates or a population benchmark. The same N=22 synthetic control is reused across all layers, explicitly; its 94 repeated rows are not 94 independent trials. No routing-equivalence, quality, speedup, or hardware-performance claim follows.

For counts c_i over E=128 and total A=176, mean=A/E=1.375; Jain=A²/(E sum(c_i²)); Gini=sum_i sum_j |c_i-c_j|/(2EA); CV=sqrt(sum((c_i-mean)²)/E)/mean. Hot1 and hot8 shares divide the largest one/eight counts by A. The histogram includes zero loads.

## Matched synthetic control and EP64 compatibility

The existing, unchanged `experiments/prefill-capacity/stage.py` is actually invoked in `generate` mode with `--assignments 176`. It uses seed 20261016, weights `(expert+1)^-1.1`, draws with rejection of within-token duplicates, k=8 and E=128. Its synthetic source placement is token ordinal modulo 64, and main expert placement is `expert // 2`. The provenance file records the generator SHA-256. No Planner, adapter or simulation stage is invoked.

E128/k8 routes are structurally compatible with the current EP64 fixed expert placement (two experts per NPU), but recorded token-source-NPU assignment is absent. Any future token-source distribution would be an explicit simulator assumption, not recovered evidence. Model-layer numbers remain separate workloads; never combine layers as extra tokens in a single layer.

**N=256, 512 and 1024 are unavailable from this request's N=22 prefill record.** No valid same-layer prefix can exceed 22. A future smaller prefix must identify this request, the exact layer and the first N serialized rows; no prefix experiment is run here. Multi-request batching would require additional authorized requests and explicit boundary preservation; this run contains only one request.

The trace's documented origin is Qwen3-235B-A22B-FP8 routing. That provenance is distinct from the current simulator's prior Qwen3-30B-sized dimensions and BF16 weight/compute assumptions. No model-size substitution or FP8-to-BF16 routing-equivalence claim is made. EP64, placement, simulator, Planner, Relay, network, compute and model-size configuration are unchanged. No GPU/model execution or performance scan was run.

## Validation and reproduction

`extract.py` rejects duplicate JSON keys, missing/reordered layers, empty matrices, inconsistent per-layer token counts, unexpected record shapes, wrong top-k, duplicate experts, bool/non-integer IDs and IDs outside `[0,127]`. It requires the source's pinned Git blob before export, preserves source ordering, conserves assignments, and reads every exported integer back for exact comparison. `test_extract.py` uses only synthetic fixtures and tests malformed cases plus analytic metric endpoints. The independent validator does not import this parser or metric implementation.

With your locally supplied authorized file, run from repository root (Python 3; matplotlib needed only for plots):

```sh
python experiments/qwen-real-prefill-trace/extract.py \
  --input /private/206.json \
  --private-output /private/extracted \
  --stats-output experiments/qwen-real-prefill-trace/results
python -m unittest discover -s experiments/qwen-real-prefill-trace -p test_extract.py -v
python experiments/qwen-real-prefill-trace/independent_validator.py \
  --input /private/206.json --exports /private/extracted \
  --stats experiments/qwen-real-prefill-trace/results
python -m unittest discover -s experiments/qwen-real-prefill-trace -p test_independent_validator.py -v
MPLCONFIGDIR=/tmp/qwen-mpl python experiments/qwen-real-prefill-trace/plot.py
```

Never use a public repository directory for `--private-output` or commit the supplied JSON. The extraction script is deliberately scoped to this one pinned request, not a generic unverified dataset importer.

## Access and redistribution

The initial access-stage investigation remains under `docs/qwen-real-prefill-trace/`; its blocked status is historical and superseded by the user-supplied file for this run only. The user approved access personally and uploaded exactly one file. No access credential or contact information is stored here.

A dataset license authorizing raw or per-token derived redistribution has not been established. Apache-2.0 declarations for the paper's code and Qwen model do not establish a license for this dataset. Raw JSON, per-token CSVs and synthetic generation inputs remain outside Git. This commit contains original code, aggregate load counts/metrics/figures, hashes and short provenance only. No prompt, token route row or raw JSON snippet is reproduced.

Final validation: 23 tests passed (14 extractor/metric tests and 9 independent-validator tests). Independent readback verified all 16,544 exported assignments, 188 metric rows, 24,064 expert counts and 188 histograms. See `results/all-tests.txt`, `results/independent-validation.json` and `results/artifact-hashes.json`. Both figures were visually inspected. These checks establish structural fidelity and arithmetic, not original token identity or model execution semantics.
