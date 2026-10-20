# Multicast WRITE v2 开发与验证报告

## 当前结论

已实现 Tag-free Wire Envelope、原生子 TP 发送资格合并、交换机按真实 Header 路由并拆成单播 WRITE。接收端使用原生协议栈，没有 v2 接收解析器。本报告全部最终结果已在原 dot 云主机重新编译和验证。14 个正向网络场景、故障测试和旧项目回归通过；原生完整套件 48/49，唯一失败为已知的缺失解析脚本。

基于已验收项目 `1b35acbdc83226b90f39aeb5aad935425dec3a04`，在独立分支 `experiments/ub-multicast-v2-dot-20261020` 开发。历史项目源码未修改，新增文件均位于本目录。原生库是独立 GitCode 工作树：固定 d6aa9e2 基线加三份已验收补丁，先核验108个源码哈希一致，再审计和实施；新增原生改动以可重放补丁交付。八个原生变更文件已在独立基线工作树重放并逐字节核验。

## 审计与实现

[AUDIT.md](AUDIT.md) 逐项记录原生构造、路由和 Tag 消费位置。默认78B前缀为 Link4 + UB Network6 + IPv4 20 + UDP8 + TP16 + TA8 + MA16。WRITE 的 UDETAH 可使前缀增加4B，不能把78B当成所有包的固定事实。

FlowTag 参与 taskId/事务查找；CorrelationTag 参与原生操作/分段生命周期和响应校验；ExplicitPayloadTag 决定把实际收到的字节交给原生事务执行。因此三者均保留原始仿真语义，但不序列化进 v2 wire。

[FORMAT.md](FORMAT.md) 定义完整字段。Extra Header 固定20B，Header Lengths每目标2B，Native Header去掉每个子包4B Link，Payload仅一次。实验性DL Config=0xF及UBW2 magic/version均来自实际序列化字节，不依赖选择Tag。下行恢复标准原生IPv4配置，并复用原有路由查找。只支持原生IPv4无选项的WRITE，1..64目标，每包Payload不超过4096B；对象通过原生分段发送。

[adapter-v2.h](adapter-v2.h) 继承旧SharedSource的控制报文优先级和all-ready窗口检查。每个子WRITE由原生GetNextPacket分配/推进PSN、SSN和未确认状态；子包不再独立进入物理发送队列。逐目标验证任务、目的地、WRITE类型、长度，Payload逐字节相等后才生成Envelope。未修改ACK、Response、重传或完成算法。

交换机复用原生VOQ、RR/DWRR仲裁、有限出口及CBFC。输入保留一份原始Envelope缓存归属，逻辑出口按各原生单播实际大小记账。最后分支出VOQ时，Allocator向CBFC提交原始输入Packet归还一次输入Credit；各出口独立消耗下行信用。普通单播和v1默认等长路径及其追踪顺序保留。

内部关联表仅保存原生三个Tag和原生Header的完整性比对副本；不提供Payload或替代Wire Header。表容量受安装的原生发送窗口限制，最多64成员/项，严格递增操作ID、不可回绕sequence、逐成员单次消费、10ms过期检查，最后成员恢复后删除。交换机验证恢复回调没有改变任何Packet字节。这里存在未建模的真实硬件查表、存储、编程和复制成本；不能声称硬件零成本或官方UB组播机制。

## 已执行验证

- Codec：1/2/4/8/64目标，混合74/78B Native Header，5组往返；6353个截断、非法长度、重复目标、错误类型/版本/Flags/Payload Length等输入被拒绝。
- 关联机制：恢复三个Tag且Wire bytes完全不变；重复、未知、过期、成员错序、Header身份不匹配五个负例均拒绝。
- 14个正向网络场景：12KiB和64KiB v1/v2、动态组、出口竞争、小队列背压、TP窗口2，以及v2混合Header和DWRR不等长分支压力场景。全部实际Payload正确，所有v2场景的Native Header与发送端原生子包逐字节一致，原生ACK/Response正常、WQE逐目标完成、组完成不早于任一目标且仅一次。
- 三目标12KiB产生12个源Envelope、36个下行原生WRITE、36个原生事务反馈。v2输入释放总字节15312，恰等于源端Envelope总字节；关联恢复36次、Header检查36次。
- 小队列v2实际发生369次CBFC阻塞查询；TP窗口2场景发生44次窗口等待。全部输入/输出缓存、关联表、Header参考及原生TP/Jetty状态最终清空。
- 默认CBFC批量返回可保留少量待发送信用（例如4 cells），验证使用 `consumed = restored + peer.pending`，没有抹去这部分状态冒充信用全归还。原有压力夹具阈值1场景最终所有pending为0、自由信用恢复初值。
- v1/v2各自缺失/重复/错误反馈共六个负例按预期失败；v2实际接收Payload损坏在原生目标数据验证处失败，未被内部映射替换或掩盖。
- 旧回归：原生单播/共享队列7组wire、events、ports、Payload精确一致；原有Full Multicast5个正例及3个预期拒绝；网络复制PoC13个正例（含DWRR）及原负例；旧并发组播9个用例；小型no-balancing/direct/two-stage/chunk-streaming四策略均通过。没有运行大规模UltraEP、Qwen Token Scaling或18MiB可选点。

原生完整套件共49项，48项通过；unified-bus-examples在原有hasTaskTimes断言失败，解析脚本确实缺失，无保护停止。严格验收器核对完整套件清单、逐套件保护状态、返回码和具体失败断言，避免把新故障误判为已知问题。验收器自身2个有效输入及10个错误状态测试通过，优化模式Python被显式拒绝。DWRR压力场景通过，发生684次CBFC阻塞查询，资源与信用守恒。

## 小型 A/B 实测

三目标；1024B TA；100Gb/s、20ns链路、固定原生资源。数据字节不包含另外计数的原生控制报文。组完成时长从100ns实际提交事件起算，取最后原生目标WQE完成；不是完整MoE Layer时间。

| 对象 | 模式 | 源端数据B | 交换机下行数据B（合计） | 源数据包/分支 | 组完成时长ns |
|---|---|---:|---:|---:|---:|
| 12KiB | v1 Full | 17604 | 52812 | 12 / 36 | 1785.56 |
| 12KiB | v2 | 15312 | 39672 | 12 / 36 | 1573.00 |
| 64KiB | v1 Full | 93888 | 281664 | 64 / 192 | 8653.28 |
| 64KiB | v2 | 81664 | 211584 | 64 / 192 | 7646.16 |

这两个点源端数据减少约13.02%，下行数据减少约24.88%。控制报文仍按每目标原生协议独立发送，无组播ACK、无聚合PSN。[results/targets.csv](results/targets.csv) 保留各目标receiver_ready、sender_complete及group_complete；[results/packet-counts.csv](results/packet-counts.csv) 按物理TX记录所有包类型与字节；[results/ports.csv](results/ports.csv) 包含出口峰值和信用账本。

原 dot 云主机上，12KiB v1/v2 CPU（user+system）为0.032892/0.027677s，64KiB为0.046456/0.047335s；RSS分别19072/19036及19600/19516KiB。监控wall粒度约0.25s，不据此推断CPU性能改善。完整Host Wall/CPU/RSS及所有保护阈值见[results/host-resources.json](results/host-resources.json)。

## 复现与范围

按[README.md](README.md)在独立固定原生树应用补丁并运行reproduce.sh。原生补丁、源适配器、测试、命令清单、过程记录及紧凑证据均在本目录。初次测试编译出现辅助函数与ns3::Header同名冲突，改名后通过；失败日志保留，没有降低检查。所有阶段沿用3600s、6GiB进程树RSS、7GiB地址空间、8GiB工作磁盘、2GiB/tmp和1.5GiB可用内存保护，顺序执行。

限制：无丢包实验，不支持新的重传/组播可靠协议；CC、重传、多交换机、共享同一物理输出的多个成员均不在本模式范围。内部关联服务仅适用于当前单进程仿真，未证明MPI/RemoteLink或硬件实现。变化只涉及v2相关包构造及局部不同大小分支的归属，未改Planner或Chunk Streaming。源Header可变长已覆盖UDETAH，未扩展到其他事务或IPv4选项。没有MoE Layer Speedup结论。

实现最初误在新建云开发环境进行，纠正后所有源码和证据迁回原 dot 云主机，逐文件校验并重跑完整有界验证。本报告仅采用原主机最终结果。Codec覆盖64成员；端到端网络夹具覆盖三个目标，不宣称已经验证64目标网络规模。源码补丁与旧108项基线哈希一致性及8个变更文件重放均已核验。

## Knowledge Sources

原生AGENTS.md、doc/agents/implementation-workflow.md、QUICK_START.md用于构建与验证流程；原生queue-backpressure-vs-topology知识卡用于区分CBFC背压与丢包；历史协议审计与HEADER_MODELS.md用于确认v1对照。最终独立分支发布状态以GitHub提交及交付核验为准。
