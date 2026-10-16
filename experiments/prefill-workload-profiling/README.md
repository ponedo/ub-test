# Prefill Workload Profiling

Actual input-only tokenization of six public source families with pinned Qwen3-235B-A22B tokenizer, per-request distributions and synthetic IID batch sums. This module adds no simulator/planner changes and performs no model execution or performance scan.

- [Measured results and future token points](evidence/RESULTS.md)
- [Sources, prompt reconstruction, tokenizer, sampling and limitations](METHODS.md)
- [Read-only EP64 capacity audit](CAPACITY.md)
- [Source revisions](sources.lock.json), [tokenizer file hashes](evidence/tokenizer-manifest.json), [download/range hashes](evidence/range-manifest.json)
- [Individual sample lengths](evidence/lengths/), [summary CSV](evidence/length-statistics.csv), [batch CSV](evidence/batch-statistics.csv), [CDF/histograms and batch plots](evidence/plots/)
- [Verification](evidence/check.log), [artifact hashes](evidence/artifact-manifest.json)

From the repository root, reproduce with Python 3.12 and network access:

```bash
bash experiments/prefill-workload-profiling/run.sh
```

The command creates/uses `/workspace/prefill-profile-venv` and `/workspace/prefill-profile-cache/run`, installs the locked libraries, fetches exact revisions, tokenizes, calculates statistics, audits source, generates the report, checks artifacts and writes hashes. Public downloads need no model weights, GPU, torch, credentials or acceptance of gated HF terms. Use `PROFILE_CACHE`, `PROFILE_VENV` and `PROFILE_OUT` to override paths; keep cache/venv outside the repository. Outputs default to this module's `evidence/`. Pin the repository base in `sources.lock.json` as well when reproducing the executor audit. HTTPS availability and disk capacity are external prerequisites.

For the delivered run, these same Python stages were executed separately while preparing the module; `prepare.log`, `profile.log`, `statistics.log`, `audit.log`, `research.log` and `check.log` retain stage evidence. Wall times are profiling observations only. Two resolved local setup failures are preserved separately; the completed ledger distinguishes measured data, failures and missing full-agent prompts. Re-running replaces generated evidence and may change wall-time/platform metadata.

No raw source text or tokenizer blobs belong in git. CSVs contain file/row positions, hashes, character counts and token counts only. OpenScience sampling covers exactly the converted population named in each ledger entry, including two explicitly partial prefixes. SWE-bench issue-only is not a full agent prompt. GPQA subsets overlap. Batch sums do not reproduce the paper's serving scheduler or real expert routing.
