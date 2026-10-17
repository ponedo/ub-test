# Qwen3-235B real prefill trace: historical access-stage report

Update: the user subsequently supplied the authorized single request file. See [the completed structural PoC](../../experiments/qwen-real-prefill-trace/README.md). This document preserves the earlier access-stage observations; it does not describe the current extraction status.

## Result

**Blocked before accessing any request file.** The public Hugging Face dataset API reports `gated: "auto"` at revision `27febb7b2d24169560a9f6f83d38eb53f94916cf`. No login, gate acceptance, credentials, sample-content request, weight download, model run, or GPU execution was performed.

Dataset: https://huggingface.co/datasets/core12345/MoE_expert_selection_trace

The public landing page requires agreement to share contact information to access files/content. The user must review that access request personally. No access entitlement or permission to transmit contact information is inferred here. This report does not circumvent the gate or supply an alternate content route.

## Public metadata observed

- Main metadata response: HTTP 200, 100,000 sibling paths, including 23,760 under `Qwen/Qwen3-235B-A22B-FP8/`. Exactly 100,000 entries is not evidence of a complete repository inventory.
- One public recursive Qwen tree page: HTTP 200, 1,000 entries (103 directories and 897 files). A `rel="next"` pagination link was returned and deliberately not followed after the access blocker was established.
- All 897 visible file entries have a `.json` extension. JSON serialization, schema and internal structure were not verified from content.
- Smallest file **on that page only**: `Qwen/Qwen3-235B-A22B-FP8/Chinese-SimpleQA/中华文化/206.json`, 1,485,105 bytes. It is not claimed to be the globally smallest request and was not downloaded.
- The visible page’s file sizes sum to 2,581,140,427 bytes. The main API’s `usedStorage` value (704,439,059) is recorded separately; neither is used as a whole-dataset download estimate.
- No license field appears in the returned top-level API metadata. This does not prove there is no license elsewhere. Raw-route/prompt/CSV redistribution is not authorized by this evidence.

Machine-readable metadata and SHA-256 hashes of the two locally retained public API responses are in `access-metadata.json`. Only public metadata, this report, and a metadata consistency check are added to Git. Raw responses remain local and contain no retrieved request content.

## Scope and limits

A new sparse worktree branches from accepted local commit `73c636b618c9f30694bc00a10443ea61c09dcd9a`, tree `71d3a598b7cde54a73528ba031857f8743b6742c`. The source checkout is unchanged. No applicable `AGENTS.md` was present in this checkout or its workspace ancestry. No old large evidence was copied. Initial filesystem availability was approximately 8.6 GiB; no large download was started and no logs were deleted.

Actual Prefill versus Decode separation, request identity, token-number meaning, layer-ID meaning and ordering, original token identity, complete-layer coverage, and eight-distinct-expert IDs in `[0,127]` are all **UNVERIFIABLE**. No per-token CSV, extraction implementation, independent raw validator, load statistics, figure, or matched-N synthetic control has been produced. Dataset descriptions must not be substituted for raw evidence. Structural consistency alone would not prove original token identity even after access.

The EP64 placement, simulator, Planner, Relay, network model, compute model, model-size configuration, and performance scans are unchanged. E128/k8 compatibility and N=256/512/1024 request/prefix feasibility have not been established from a raw trace. FP8 router provenance must remain distinct from any future assumed BF16 compute weights.

## Resumption conditions

1. The user reviews and completes any required Hugging Face access/contact-sharing step themselves; do not request a token in chat or bypass access controls.
2. Confirm a permitted access route and license/redistribution status before retrieving content.
3. Inspect a bounded public Qwen directory scope at the pinned revision and select only one smallest request in the explicitly inspected scope. Record pagination boundaries without claiming a global minimum. Apply a download-size/free-space guard preserving at least 8 GiB headroom. Do not download an archive or the full dataset.
4. Inspect actual content, then implement extraction and independent raw-versus-export validation against the observed schema. Preserve source order, original IDs and request boundaries; mark unsupported semantics UNVERIFIABLE.
5. Keep raw data and per-token routes local unless redistribution is explicitly permitted. Report statistics only after validation; document any same-layer prefix and matched-N Zipf control without claiming routing equivalence.

To reproduce the completed metadata checks, GET the exact public `dataset_api_url` and `tree_page_url` in `access-metadata.json` without authentication. Dataset revision and metadata may change; this report records the observed snapshot. Do not resolve/download a request file while access remains unapproved.

Local consistency check: `python docs/qwen-real-prefill-trace/check_access_metadata.py`.

## Independent public-source cross-check

- [Dataset card](https://huggingface.co/datasets/core12345/MoE_expert_selection_trace/blob/main/README.md) describes one JSON per request, item zero as prefill (input-token × selected-expert matrix per layer), and subsequent items as decode. These are documented claims, **not file-validated results**. Layer-index base, original token identity, exact serialization, expert rank ordering, tokenizer/model revisions, batching and chunked-prefill details remain unverified.
- [Paper v5](https://arxiv.org/html/2510.05497v5), Section V-A, describes SGLang collection using H100/H200 systems. Appendix A.2 identifies an Apache-2.0 **code** license; it does not establish a license for this separately hosted dataset or its derived per-token CSVs. No explicit dataset redistribution license was established. Obtain an applicable data license or author permission before bundling trace rows.
- [Official FP8 model config](https://huggingface.co/Qwen/Qwen3-235B-A22B-FP8/blob/5fc1e2a2307b76ebe108872c04da9d5d3d2a7397/config.json) gives 94 hidden layers, 128 experts, 8 experts per token, decoder_sparse_step=1 and mlp_only_layers=[]. This provides expected architecture, not proof of the dataset's layer numbering or actual routing tensor axes. The model’s license is also separate from the dataset’s license.
