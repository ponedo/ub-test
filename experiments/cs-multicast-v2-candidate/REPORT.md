# CS+Multicast v2 Candidate：固定 3136 Gbps 小规模探索

## 结论

**不替换已验收 v1，不进入完整真实 Trace 验证。** 固定简历版本仍是 `e3efc29e901024cea6343196f6ab33958e3b02cd`，原有源码、报告和五策略结果保持不变。这里的 v2 Candidate 是策略版本，不是新的组播线上格式。

本轮唯一候选为 Stage I/II 队首一次性、不可延长的 **5 ns APP 等待**，不是新的可靠传输协议。目标带宽下，没有一组对照改善整层时延。压力用例 V08 中：

- Stage I Payload 合并率：**98.9593% → 99.5270%**；Stage II 原本就是 **100%**，保持不变。
- Envelope：**3163 → 3169**；源端 Wire Bytes：**3,816,775 → 3,810,751 B**，减少约 **0.158%**。
- Weight Duration 改善 **8.222 ns**，但 Layer Latency 增加 **10 ns**。该用例有固定的 **200 μs 人为完成延迟**，不是自然真实工作负载。

这是有限的通信量收益与时延权衡，不是整体性能成功。不能将这些小用例的覆盖率外推为真实 Qwen3 的覆盖率改善。未验证的时序条件仍明确保留，总体为 **NOT_GENERAL_ADMISSION**。

## 配置核对与历史纠正

最初沿用了 100 Gbps 合成夹具，发布前发现与目标 3136 Gbps 不符。此前 **52 次执行只作为非目标带宽诊断历史**，不用于下述目标结论。随后不改变候选二进制、5 ns 等待策略、Planner、Relay Tree 或窗口参数，将双方实际仿真输入统一纠正到 3136 Gbps。实际输入首行字段和 C++ 到 UbPort 的配置路径均核验，执行前新增硬检查。

目标带宽共 **39 次执行**：原 37 次逻辑矩阵加一组固定 64 KiB 对照，用于暴露真实流水重叠；它不计入干净性能样本。合计历史为 **91 次小仿真**。未运行完整真实 256 Tokens、512/1024/2048 Tokens 或五策略性能矩阵，未扫描 Chunk、Window、Fanout 或等待时长。详见 [配置纠正记录](analysis/CONFIGURATION_CORRECTION.md)。

原 12 KiB V04 在高带宽下下游首发与完整 Expert 接收恰好同刻，因此保留为未观察到严格重叠。新增 64 KiB 用例使用相同的 Planner、放置、树结构和 4096 B Chunk，仅扩展合成对象长度；v1/v2 在两条 Relay 上均观察到下游首发比完整接收早 **65 ns**。没有通过修改依赖或时间比较条件制造通过。

## 交付导航

- [AUDIT.md](AUDIT.md)：回退原因、实际源码函数与行号；历史小例子明确区分目标与非目标证据。
- [DESIGN.md](DESIGN.md)：唯一候选、不变量与未覆盖条件。
- [REPRODUCE.md](REPRODUCE.md)：固定目标输入、守护运行、保留未覆盖结果的有限续跑方法。
- [目标对照 CSV](analysis/paired-metrics.csv)、[逐次目标结果](analysis/execution-summary.csv)、[阶段覆盖率](analysis/role-coverage.csv)。
- [合成配方与输入哈希](results/case-input-hashes.json)、[等待和缺口](results/hold-and-gap-closure.json)。
- [原基线保护](baseline-protection.json)：11,090 个已验收文件和 3,504 个原生源码/构建文件保持一致。

## 边界

原生 RR 算法、槽位/游标规则、5 ns 仲裁服务、同一 TP 的原生队首顺序和可靠性机制未修改。但 APP 资格抑制会改变实际授权时序与竞争，不能宣称两组实际授权序列完全一样。CNP/ACK/GBN 保留原生优先关系；缺失的动态绕过实例不会被静态代码判断替代。

Whole-expert Direct Fallback 不增加等待。兼容 hybrid-summary 字段沿用 v1 格式，candidate-summary 才说明启用后的实际等待策略；不能把继承字段误读为候选没有等待。没有新增组播 ACK、重传状态机、非队首抽取或全 Relay 同步。

## Corrected 3136 Gbps target analysis

## Scope and current evidence status

This section uses fresh 3136 Gbps / 20 ns outputs only. Baseline and candidate binaries and the fixed 5000 ps Stage I/II hold policy are unchanged. The earlier 100 Gbps results are off target and are separated by [analysis/CONFIGURATION_CORRECTION.md](analysis/CONFIGURATION_CORRECTION.md).

V01–V08 now have paired runtime measurements. V04's required physical-streaming witness is not exercised at this bandwidth in either arm, so availability of its performance measurements does not make its mandatory coverage pass. Final fault-validation and coverage accounting appears below; incomplete witnesses are not hidden by a completed runtime.

## Target tradeoff, not an inherited conclusion

Candidate-minus-baseline layer latency deltas for V01–V08 are 0, 0, 0, +5000, +10158, 0, +5000, +10000 ps. Weight-duration deltas are 0, 0, 0, +5000, +5000, 0, +5000, −8222 ps. V01–V07 have no source-wire or envelope-count change. V08 gains six envelopes and saves 6024 source weight wire bytes.

Thus no measured non-fault case improves end-to-end layer latency, but V08 does improve the weight phase. The result is a small mixed tradeoff, not “no benefit of any kind,” and not a general proof that holding cannot help. Mandatory coverage limitations and fixture relevance still matter independently of the performance sign.

### V08 role coverage and completion tradeoff

At the corrected bandwidth, the gain is in Stage I:
- Stage I coalesced payload: 2,142,210→2,154,498 out of 2,164,738 bytes, or 98.9593198%→99.5269635% (+0.5676438 percentage points). Envelopes: 1047→1053; native fallback packets: 22→10.
- Stage II is already 100% in both arms: 4,329,476 coalesced logical bytes and 2116 envelopes, with no native fallbacks.
- Total envelopes: 3163→3169. Source weight wire: 3,816,775→3,810,751 bytes, −6024 bytes (approximately −0.1578%).
- Weight completion improves by 8222 ps, while layer latency increases 1,018,074,082→1,018,084,082 ps (+10000 ps).

The actual timeline explains why an earlier weight gate is not equivalent to a faster layer. Weight gate moves 1017412829→1017404607 ps, but dispatch span grows 196573→209795 ps. The last compute remains on node 2: its start/end are each 5000 ps later, and final layer completion is 10000 ps later. These are measured phase boundaries, not an additive causal attribution to each individual hold. See [analysis/v08-completion-tradeoff.csv](analysis/v08-completion-tradeoff.csv).

V08 retains `weight_completion_ns=200000`, a deliberate 200 µs artificial completion/retention pressure. Its tiny weight/wire gain is not a natural-workload result and alone does not justify real256, larger-token, strategy, chunk/window, or fanout experiments.

## Fresh target hold evidence

There are 37 recorded held heads across these non-fault pairs: V04=1, V05=2, V07=1, V08=33; the other four cases have none. All 37 expire at their deadline; no early release is observed. This is release behavior, not continuous eligibility history. A peer could become ready between queries; missing head snapshots cannot prove otherwise.

A freshly verified V04 group-1, offset-0, 1024-byte chain shows candidate absence at 201000 ps, both expected heads present at the 206000 ps deadline, a no-ingress allocation outcome at 206000, and merge/source TX at 211000. Baseline normally allocates 201000→206000 and merges/transmits at 206000. Candidate source serialization is 3061 ps at the corrected rate. This supports the extra-allocation-window explanation for this specific target event. Baseline initial peer absence remains unobserved and is not inferred. Only one hold occurs in target V04, not the earlier off-target count.

Target V08 actual fallback aggregates are five member-priority and five already-consumed packets. These are not the old 100 Gbps task-mismatch counts. Aggregate counters are distinct from sampled pull metadata; native-limited −1 remains unknown. Full hold ledger completeness does not imply complete native event or continuous eligibility history.

## Source artifacts and limits

[analysis/clean-pair-outcomes.csv](analysis/clean-pair-outcomes.csv), [analysis/role-coverage.csv](analysis/role-coverage.csv), [analysis/clean-hold-aggregates.csv](analysis/clean-hold-aggregates.csv), [analysis/clean-fallback-causes.csv](analysis/clean-fallback-causes.csv), and [analysis/v08-completion-tradeoff.csv](analysis/v08-completion-tradeoff.csv) contain the bounded target measurements. V08 summary-mode native tails remain bounded; full early packet chains or unobserved baseline heads must not be reconstructed from aggregates. Final fault evidence and execution accounting below use target-specific outcomes only, without substituting 100 Gbps witnesses.

## Final execution and coverage accounting

All 39 target executions are now complete: the original 37-record small matrix plus two explicitly authorized S64 physical-streaming coverage executions. All actual target inputs use 3136 Gbps; the preserved earlier 52 executions remain 100 Gbps-only. Completion does not mean every original required witness passed.

V04 baseline, candidate, and disabled-policy control do not exercise the original physical-streaming witness at this rate. V09 candidate does not exercise its intended stale-grant rejection. These gaps remain explicit; naturally observed rejections elsewhere are not substitutes. S64 establishes streaming capability in its declared larger tiny fixture, not retroactive success of V04. Disabled-policy parity and expected-negative outcomes remain separately classified.

Target V12 baseline initially stopped under an over-restrictive cumulative-ACK oracle. Its higher same-TP ACKs were already in flight when the earlier ACK was dropped: requiring their entire physical path to begin after the loss incorrectly excluded valid coverage. The corrected check requires later reception of the covering same-TP ACK and safe terminal advancement, while preserving all identity/path checks. Existing baseline outputs were rechecked without rerunning the simulator; the original STOPPED status is preserved alongside posthoc PASS. Candidate then passed the corrected oracle in its target execution. This is an oracle correction, not a runtime or policy change.

Across the original target matrix's completed hold summaries, 44 holds expire; S64 adds 85, giving 129 total. Zero early releases and zero active-hold priority-bypass queries are observed. Absence of an observed bypass is not proof of its behavior under unobserved arrivals, and zero early releases does not mean no early-ready state occurred between queries. Maximum recorded APP inhibition remains 5000 ps.

### S64 is coverage evidence, not a clean optimization case

Both arms have two actual relay streaming witnesses. Baseline chunk readiness is 496872 ps, downstream TX 506872, full-expert RX 571872. Candidate corresponding times are 501872, 511872, and 576872 ps. Both therefore transmit downstream 65000 ps before receiving the full expert: actual physical overlap, not merely delayed application readiness. See [analysis/s64-streaming-witnesses.csv](analysis/s64-streaming-witnesses.csv).

S64 gains 40 envelopes and saves 40160 source wire bytes, but layer latency increases by 5000 ps. Its 85 holds all expire. It is an authorized coverage extension, not a member of the original clean V01–V08 optimization comparison, and cannot be pooled to disguise their results.

### Corrected target fault evidence

[analysis/fault-path-witnesses.csv](analysis/fault-path-witnesses.csv) contains seven bounded target paths, freshly selected from the corrected outputs using the frozen same-UID ordered-route logic. Original merged data carries an envelope UID on the source link and a distinct decoded branch UID on the target link; the CSV labels both explicitly.

- V10 lost task 128, TP 2→9, PSN/SSN 9/9, is retried as native unicast UID 0 at 5397188→5419999→5424999→5447810 ps (source TX, switch RX, switch TX, target RX).
- V11 lost task 134, TP 12→26, PSN/SSN 5/5, is retried as native unicast UID 214 at 5475091→5497902→5502902→5525713 ps. The target PSN is 5, not the off-target PSN 3.
- V13 reverse TAACK task 134, TP 26→12, PSN/SSN 5/5, recovers with UID 923 at 5669376→5689534→5694534→5714692 ps. It is reverse native recovery, not multicast WRITE replay.
- V12 candidate loses task 128's ACK PSN 9 at 402188 ps. Higher same-TP ACKs PSN 10/11 arrive at 412188/422188 ps; terminal sndUna=sndNxt=12. Baseline corresponding arrivals are 407188/417188 after its drop at 397188 ps. Exact instantaneous sndUna advancement is not recorded and is not claimed. The oracle remains fixture-bound to no-wrap PSNs 0–11.
- V14 duplicates task 134 once. It has one chunk-ready and one edge-ready event, with 18 each globally; sender completions=remote WQEs=42, TA count=target segments=96, completed tokens=64. Losses, WRITE retries, pending associations, pending members, and active codecs are all zero.

[analysis/ack-summary.json](analysis/ack-summary.json) retains these bounded identity/completion facts and the baseline posthoc correction, without raw tails or machine paths.

### Allocation and final interpretation

Target V08 allocation totals are baseline 58953 requested = 47833 committed + 0 rejected + 11120 no-ingress; candidate 58970 = 47827 committed + 1 rejected + 11142 no-ingress. Measured no-ingress aggregate elapsed is 55600000→55710000 ps, and rejected elapsed 0→5000 ps. These are overlapping port totals, not a decomposition of layer or hold delay. They are not the old 100 Gbps totals.

No target pair improves layer latency. The correct conclusion nevertheless preserves the small V08 weight/wire benefit and S64 bandwidth/coverage benefit, rather than declaring no benefit or that 5 ns holds can never work. The tested policy shows mixed tiny phase/bandwidth gains with non-improving end-to-end latency, an artificial V08 stress condition, and explicitly unexercised original witnesses. This supports retaining the bounded evidence, not broad admission, tuning, or forbidden scale expansion.

Final bounded accounting files are [analysis/execution-summary.csv](analysis/execution-summary.csv) (39 rows, original status preserved), [analysis/paired-metrics.csv](analysis/paired-metrics.csv), [analysis/allocation-outcomes.csv](analysis/allocation-outcomes.csv), and [analysis/hold-aggregates.csv](analysis/hold-aggregates.csv). No further simulations or tuning were used to prepare this section.


## 工程交付状态

目标 39 次执行中，33 次非负向运行的在线/独立正确性、原生安全排空和累计计数守恒通过；6 次负向运行被各自指定的不变量正确拒绝。原 V04/C-V04 的重叠缺口、V09 候选没有形成注入过期授权，以及早释放/活动等待期间本地优先流量绕过等未覆盖条件均保留。V12 原停止记录也未改写，另附候选局部修正的累计 ACK 观察校验：后续 ACK 可在丢包时已在途，只要求实际到达在丢失之后，完整 TP/PSN/UID 路径及最终窗口检查均保留。此修正只影响检查器，不改协议或仿真运行。

所有 129 次目标候选等待均在 5 ns 到期，状态最终回收；没有观察到早释放。这不证明整个间隔中始终没有可合并状态，也不能用等待次数乘 5 ns 当作整层额外时延。

保留 6 GiB RSS、7 GiB 地址空间、4,800 s 运行上限、磁盘和主机内存保护，未触发保护。目标 39 次仿真宿主机 Wall Time 合计约 15.172 s，全部 91 次约 36.154 s，仿真峰值 RSS 60,412 KiB；APP-only 编译另计约 49.49 s / 1.49 GiB。宿主机耗时与模拟时延分开报告。未修改或重编原生 UB 库。

没有将更高合并率包装成预设加速比；本轮不推荐直接进入完整真实 Trace。后续若研究其他机会，应先补齐小场景时序证据，而不是覆盖 v1 历史结果。

不上传真实路由数据、真实逐 Token 记录、原始 Payload 或大型 Debug Trace。配方、精确命令、输入哈希、限定事件样本及资源来源足以检查本轮范围；完整派生输入和原始失败证据被保留。发布后的提交与逐文件核验见 REMOTE-VERIFICATION.md。


### Why the short overlap fixture is not a barrier proof

The actual first chunk (task 128) in the 12 KiB control dequeues its four native TAs at PSN/SSN 0, 3, 6 and 9; in the 64 KiB control they are 0, 16, 32 and 48. Thus the observed native task admission/send stream interleaves chunks; the first chunk is not transmitted as four contiguous native PSNs. The records in [first-chunk-native-order.csv](analysis/first-chunk-native-order.csv) are **native dequeues, not physical TX timestamps**. The separate physical overlap witnesses remain authoritative. These observations explain why a very short object can leave little overlap window without introducing a full-expert readiness barrier. The candidate does not reorder this native stream.
