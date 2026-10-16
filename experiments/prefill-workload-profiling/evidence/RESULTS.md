# Measured prefill workload results

Measured **32 series / 55,658 input observations**, each raw and chat. Counts include overlapping GPQA subsets and separately selected populations; this is not a deduplicated union of all datasets.

No model inference or network simulation was run. See [methods](../METHODS.md), [capacity audit](../CAPACITY.md), [source ledger](profile-ledger.json) and [locked revisions](../sources.lock.json).

## Coverage

| Series | N / status | Available population / scope |
|---|---:|---|
| codeforces_train | 9556 | full selected default split |
| codeforces_test | 468 | full selected default split |
| swe_bench_test_issue_only | 2294 | full 2294 benchmark issues |
| swe_bench_full_agent_prompt | not_available | Repository checkout/retrieval/tool/system context policy used by UltraEP is unknown; issue-only lengths cannot estimate a complete agent prompt. |
| dapo_unique | 17398 | full canonical parquet, exact prompt deduplication |
| gpqa_main | 448 | full official author archive subset; subsets overlap |
| gpqa_diamond | 198 | full official author archive subset; subsets overlap |
| gpqa_extended | 546 | full official author archive subset; subsets overlap |
| longbench_narrativeqa | 200 | full original v1 subtask; _e variants excluded |
| longbench_qasper | 200 | full original v1 subtask; _e variants excluded |
| longbench_multifieldqa_en | 150 | full original v1 subtask; _e variants excluded |
| longbench_multifieldqa_zh | 200 | full original v1 subtask; _e variants excluded |
| longbench_hotpotqa | 200 | full original v1 subtask; _e variants excluded |
| longbench_2wikimqa | 200 | full original v1 subtask; _e variants excluded |
| longbench_musique | 200 | full original v1 subtask; _e variants excluded |
| longbench_dureader | 200 | full original v1 subtask; _e variants excluded |
| longbench_gov_report | 200 | full original v1 subtask; _e variants excluded |
| longbench_qmsum | 200 | full original v1 subtask; _e variants excluded |
| longbench_multi_news | 200 | full original v1 subtask; _e variants excluded |
| longbench_vcsum | 200 | full original v1 subtask; _e variants excluded |
| longbench_trec | 200 | full original v1 subtask; _e variants excluded |
| longbench_triviaqa | 200 | full original v1 subtask; _e variants excluded |
| longbench_samsum | 200 | full original v1 subtask; _e variants excluded |
| longbench_lsht | 200 | full original v1 subtask; _e variants excluded |
| longbench_passage_count | 200 | full original v1 subtask; _e variants excluded |
| longbench_passage_retrieval_en | 200 | full original v1 subtask; _e variants excluded |
| longbench_passage_retrieval_zh | 200 | full original v1 subtask; _e variants excluded |
| longbench_lcc | 500 | full original v1 subtask; _e variants excluded |
| longbench_repobench-p | 500 | full original v1 subtask; _e variants excluded |
| openscience_OS-Q2.5-32B-10 | 5000 | 393091; uniform sample of converted PREFIX only; not representative of entire source config |
| openscience_OS-Q2.5-32B-4 | 5000 | 75720; uniform sample of complete converted config |
| openscience_OS-Q2.5-72B-10 | 5000 | 415848; uniform sample of converted PREFIX only; not representative of entire source config |
| openscience_OS-Q3-235B-4 | 5000 | 315579; uniform sample of complete converted config |

DAPO: 1,791,700 raw rows − 1,774,302 exact repeats = **17,398 unique prompts**. Dataset naming is not an observed cardinality.

## Per-request tokens

Both modes and all exceedance columns are in [length-statistics.csv](length-statistics.csv). The table below is chat mode; all counts are untruncated. Each plot includes raw/chat CDF and histogram.

| Series | N | Mean | P50 | P90 | P95 | P99 | Min | Max | CDF / histogram |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| codeforces_train | 9,556 | 635.9 | 594.0 | 988.0 | 1,138.2 | 1,525.5 | 26 | 4,184 | [plot](plots/codeforces_train-lengths.png) |
| codeforces_test | 468 | 803.8 | 763.0 | 1,228.6 | 1,363.7 | 1,646.0 | 179 | 1,741 | [plot](plots/codeforces_test-lengths.png) |
| swe_bench_test_issue_only | 2,294 | 521.1 | 303.0 | 1,037.7 | 1,516.9 | 3,116.6 | 18 | 26,519 | [plot](plots/swe_bench_test_issue_only-lengths.png) |
| dapo_unique | 17,398 | 157.6 | 145.0 | 217.0 | 254.1 | 389.0 | 76 | 1,552 | [plot](plots/dapo_unique-lengths.png) |
| gpqa_main | 448 | 215.7 | 185.0 | 337.4 | 411.6 | 720.5 | 47 | 2,777 | [plot](plots/gpqa_main-lengths.png) |
| gpqa_diamond | 198 | 224.8 | 190.0 | 348.6 | 434.1 | 771.1 | 50 | 2,777 | [plot](plots/gpqa_diamond-lengths.png) |
| gpqa_extended | 546 | 240.4 | 188.0 | 349.5 | 438.8 | 933.0 | 47 | 12,394 | [plot](plots/gpqa_extended-lengths.png) |
| longbench_narrativeqa | 200 | 29,941.0 | 31,402.0 | 60,431.4 | 64,231.2 | 65,409.0 | 8,382 | 65,412 | [plot](plots/longbench_narrativeqa-lengths.png) |
| longbench_qasper | 200 | 5,204.4 | 4,815.5 | 7,644.2 | 9,355.1 | 17,963.7 | 2,087 | 22,057 | [plot](plots/longbench_qasper-lengths.png) |
| longbench_multifieldqa_en | 150 | 7,181.5 | 7,313.0 | 11,647.1 | 13,444.4 | 15,286.3 | 1,362 | 16,510 | [plot](plots/longbench_multifieldqa_en-lengths.png) |
| longbench_multifieldqa_zh | 200 | 4,506.1 | 3,993.5 | 7,624.2 | 8,818.1 | 9,581.5 | 893 | 10,008 | [plot](plots/longbench_multifieldqa_zh-lengths.png) |
| longbench_hotpotqa | 200 | 13,458.5 | 15,032.5 | 17,036.5 | 17,195.1 | 17,580.7 | 1,910 | 17,667 | [plot](plots/longbench_hotpotqa-lengths.png) |
| longbench_2wikimqa | 200 | 7,558.0 | 6,701.0 | 13,380.1 | 15,207.5 | 16,996.4 | 1,030 | 17,062 | [plot](plots/longbench_2wikimqa-lengths.png) |
| longbench_musique | 200 | 16,354.7 | 16,815.5 | 17,316.6 | 17,475.8 | 17,805.9 | 6,813 | 17,910 | [plot](plots/longbench_musique-lengths.png) |
| longbench_dureader | 200 | 10,647.4 | 10,417.5 | 14,232.5 | 15,232.3 | 17,373.0 | 5,274 | 19,212 | [plot](plots/longbench_dureader-lengths.png) |
| longbench_gov_report | 200 | 10,635.4 | 8,945.0 | 18,282.5 | 22,233.3 | 41,694.8 | 2,092 | 52,567 | [plot](plots/longbench_gov_report-lengths.png) |
| longbench_qmsum | 200 | 13,958.7 | 13,046.0 | 25,609.0 | 26,155.1 | 30,444.0 | 2,644 | 30,449 | [plot](plots/longbench_qmsum-lengths.png) |
| longbench_multi_news | 200 | 2,698.7 | 2,098.5 | 4,745.8 | 6,211.9 | 12,945.9 | 177 | 14,323 | [plot](plots/longbench_multi_news-lengths.png) |
| longbench_vcsum | 200 | 9,223.2 | 7,990.0 | 16,988.0 | 18,561.6 | 23,823.2 | 708 | 26,449 | [plot](plots/longbench_vcsum-lengths.png) |
| longbench_trec | 200 | 6,855.9 | 6,900.0 | 10,665.8 | 11,068.2 | 11,294.0 | 1,905 | 11,494 | [plot](plots/longbench_trec-lengths.png) |
| longbench_triviaqa | 200 | 12,220.0 | 12,251.5 | 20,329.4 | 21,704.1 | 23,113.8 | 1,558 | 24,346 | [plot](plots/longbench_triviaqa-lengths.png) |
| longbench_samsum | 200 | 9,208.9 | 9,416.0 | 15,346.8 | 16,351.6 | 17,184.2 | 1,422 | 18,059 | [plot](plots/longbench_samsum-lengths.png) |
| longbench_lsht | 200 | 14,173.4 | 13,689.5 | 21,989.8 | 23,371.6 | 25,363.8 | 3,697 | 28,165 | [plot](plots/longbench_lsht-lengths.png) |
| longbench_passage_count | 200 | 15,423.7 | 15,889.5 | 21,519.3 | 23,396.4 | 24,912.2 | 5,067 | 29,640 | [plot](plots/longbench_passage_count-lengths.png) |
| longbench_passage_retrieval_en | 200 | 12,927.1 | 12,828.0 | 14,509.6 | 14,772.5 | 15,565.5 | 10,395 | 15,653 | [plot](plots/longbench_passage_retrieval_en-lengths.png) |
| longbench_passage_retrieval_zh | 200 | 4,763.4 | 4,727.0 | 5,582.2 | 5,762.6 | 6,158.3 | 3,403 | 6,795 | [plot](plots/longbench_passage_retrieval_zh-lengths.png) |
| longbench_lcc | 500 | 3,237.9 | 2,310.5 | 5,840.7 | 7,909.7 | 15,087.8 | 1,016 | 32,646 | [plot](plots/longbench_lcc-lengths.png) |
| longbench_repobench-p | 500 | 10,943.6 | 9,218.5 | 19,662.0 | 23,380.2 | 33,162.9 | 2,624 | 39,280 | [plot](plots/longbench_repobench-p-lengths.png) |
| openscience_OS-Q2.5-32B-10 | 5,000 | 183.3 | 174.0 | 271.0 | 314.0 | 505.0 | 64 | 1,369 | [plot](plots/openscience_OS-Q2.5-32B-10-lengths.png) |
| openscience_OS-Q2.5-32B-4 | 5,000 | 140.7 | 130.0 | 210.0 | 245.0 | 330.0 | 47 | 816 | [plot](plots/openscience_OS-Q2.5-32B-4-lengths.png) |
| openscience_OS-Q2.5-72B-10 | 5,000 | 198.1 | 177.0 | 309.0 | 376.0 | 679.0 | 64 | 1,448 | [plot](plots/openscience_OS-Q2.5-72B-10-lengths.png) |
| openscience_OS-Q3-235B-4 | 5,000 | 129.4 | 124.0 | 186.0 | 209.0 | 268.0 | 43 | 593 | [plot](plots/openscience_OS-Q3-235B-4-lengths.png) |

## IID synthetic batch sums

All 1/2/4/8/16/32-request, raw/chat statistics are in [batch-statistics.csv](batch-statistics.csv). Each series/B uses 100,000 draws with replacement. No packing, truncation, arrivals or scheduler. Selected chat examples follow.

| Series | Requests | Mean sum | P50 | P90 | P99 | Batch plot |
|---|---:|---:|---:|---:|---:|---|
| codeforces_train | 1 | 636.9 | 595.0 | 989.0 | 1,526.0 | [plot](plots/codeforces_train-batches.png) |
| codeforces_train | 8 | 5,081.4 | 5,019.0 | 6,112.0 | 7,324.0 | [plot](plots/codeforces_train-batches.png) |
| codeforces_train | 32 | 20,355.5 | 20,279.0 | 22,443.0 | 24,464.0 | [plot](plots/codeforces_train-batches.png) |
| swe_bench_test_issue_only | 1 | 522.0 | 303.0 | 1,036.0 | 3,363.0 | [plot](plots/swe_bench_test_issue_only-batches.png) |
| swe_bench_test_issue_only | 8 | 4,178.3 | 3,588.0 | 6,385.1 | 14,682.0 | [plot](plots/swe_bench_test_issue_only-batches.png) |
| swe_bench_test_issue_only | 32 | 16,682.9 | 15,561.5 | 22,531.0 | 39,859.0 | [plot](plots/swe_bench_test_issue_only-batches.png) |
| dapo_unique | 1 | 157.4 | 145.0 | 217.0 | 389.0 | [plot](plots/dapo_unique-batches.png) |
| dapo_unique | 8 | 1,259.9 | 1,231.0 | 1,472.0 | 1,895.0 | [plot](plots/dapo_unique-batches.png) |
| dapo_unique | 32 | 5,040.8 | 4,997.0 | 5,506.0 | 6,172.0 | [plot](plots/dapo_unique-batches.png) |
| gpqa_main | 1 | 215.4 | 185.0 | 343.0 | 768.0 | [plot](plots/gpqa_main-batches.png) |
| gpqa_main | 8 | 1,723.7 | 1,637.0 | 2,169.0 | 4,148.0 | [plot](plots/gpqa_main-batches.png) |
| gpqa_main | 32 | 6,904.6 | 6,727.0 | 8,051.0 | 10,105.0 | [plot](plots/gpqa_main-batches.png) |
| longbench_narrativeqa | 1 | 29,974.8 | 31,402.0 | 60,435.0 | 65,412.0 | [plot](plots/longbench_narrativeqa-batches.png) |
| longbench_narrativeqa | 8 | 239,334.3 | 237,540.5 | 303,739.5 | 359,200.3 | [plot](plots/longbench_narrativeqa-batches.png) |
| longbench_narrativeqa | 32 | 957,449.1 | 955,689.0 | 1,084,503.3 | 1,192,462.1 | [plot](plots/longbench_narrativeqa-batches.png) |
| longbench_qasper | 1 | 5,209.1 | 4,850.0 | 7,646.0 | 17,941.0 | [plot](plots/longbench_qasper-batches.png) |
| longbench_qasper | 8 | 41,625.9 | 40,226.0 | 52,176.0 | 64,725.0 | [plot](plots/longbench_qasper-batches.png) |
| longbench_qasper | 32 | 166,583.2 | 165,116.0 | 186,607.1 | 208,172.1 | [plot](plots/longbench_qasper-batches.png) |
| longbench_repobench-p | 1 | 10,978.7 | 9,238.0 | 19,770.0 | 34,144.0 | [plot](plots/longbench_repobench-p-batches.png) |
| longbench_repobench-p | 8 | 87,423.1 | 85,964.5 | 112,253.6 | 136,699.1 | [plot](plots/longbench_repobench-p-batches.png) |
| longbench_repobench-p | 32 | 350,126.2 | 348,832.0 | 398,864.1 | 443,297.1 | [plot](plots/longbench_repobench-p-batches.png) |
| openscience_OS-Q3-235B-4 | 1 | 129.2 | 124.0 | 186.0 | 268.0 | [plot](plots/openscience_OS-Q3-235B-4-batches.png) |
| openscience_OS-Q3-235B-4 | 8 | 1,035.0 | 1,026.0 | 1,196.0 | 1,367.0 | [plot](plots/openscience_OS-Q3-235B-4-batches.png) |
| openscience_OS-Q3-235B-4 | 32 | 4,140.0 | 4,130.0 | 4,462.0 | 4,765.0 | [plot](plots/openscience_OS-Q3-235B-4-batches.png) |

Half-sample stability: **10 of 384** series/mode/B cases exceed a 5% relative discrepancy in P50/P90/P99 between the two 50,000-draw halves. [Full diagnostic](batch-stability.csv). This tests Monte Carlo stability, not source representativeness.
Flagged cases (raw and chat): gpqa_diamond B=1, longbench_gov_report B=1, longbench_lcc B=2, longbench_multi_news B=1, swe_bench_test_issue_only B=1. For B=1, use the exact full empirical quantiles in length-statistics.csv as the source-distribution reference; sampled quantiles can jump across discrete CDF steps. The flags remain reported, not silently replaced or called converged.

## Suggested future global-token points

Derived from measured chat lengths/batch sums, rounded upward to multiples of 256; **suggestions only, no execution**. Algebraic scaled checks assume H64/I128/bf16/3 matrices/R31 and k8. Planner check below is the A≤2M bound alone; placement/numeric constraints also apply. Real Qwen H4096/I1536 with R31 fails the weight-byte admission check for every point.

| Source | B | Quantile | Measured tokens | Suggested global T | Scaled executor bounds | Planner assignment bound |
|---|---:|---|---:|---:|---|---|
| gpqa_main | 1 | P50 | 185.0 | 256 | pass bounds only | pass bound only |
| dapo_unique | 8 | P90 | 1,472.0 | 1,536 | pass bounds only | pass bound only |
| codeforces_train | 4 | P50 | 2,489.0 | 2,560 | pass bounds only | pass bound only |
| codeforces_train | 8 | P90 | 6,112.0 | 6,144 | pass bounds only | pass bound only |
| longbench_qasper | 1 | P90 | 7,646.0 | 7,680 | pass bounds only | pass bound only |
| longbench_narrativeqa | 1 | P90 | 60,435.0 | 60,672 | requires changes | pass bound only |
| longbench_narrativeqa | 8 | P90 | 303,739.5 | 303,872 | requires changes | exceeds bound |
| longbench_narrativeqa | 32 | P99 | 1,192,462.1 | 1,192,704 | requires changes | exceeds bound |

No gate routing can be inferred from these lengths. Use separately labelled synthetic skew until real layer-wise traces are obtained. Context exceedance and sum-budget exceedance remain separate diagnostics in the CSVs; neither was used to discard observations.

## Remaining gaps

- Exact UltraEP serving preprocessing, mixture, scheduling configuration and real routing traces are unavailable in the inspected public revision.
- SWE-bench full agent/repository-context prompts remain unmeasured.
- Two OpenScience 10-choice populations cover only converted prefixes.
- Codeforces reconstruction and uniform chat wrapping are explicit choices, not verified author recipes.
- Current executor capacity bounds preclude several realistic global token sums and Qwen-size replicated weights; no runtime feasibility claim is made.

Recorded source-processing failures in this completed ledger: **0**.
