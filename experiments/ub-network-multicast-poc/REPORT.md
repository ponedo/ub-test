# ns-3-ub 单交换机网络组播 PoC

## 结论

已实际编译并运行网络复制原型：源端只提交一份 Payload，经真实源端链路到达交换机，在原生 VOQ 中形成各目的分支，再经原生仲裁、有限出口队列、CBFC 和链路到达各目标。动态成员、出口竞争和背压测试通过。

13 个正向网络案例通过，4 个非法请求按预期拒绝，7 个验证器破坏用例检出。原生 QUICK 测试实际为 **48/49 suite 通过**；一个 examples suite 因原有外部解析脚本缺失而失败，已用旧、新版本实际运行确认同一限制，未改断言或伪造 PASS。

原有四策略小规模应用回归的模拟结果保持逐项一致。独立审查结论为 `PASS_WITH_DOCUMENTED_COVERAGE_LIMIT`，详见 [review.json](results/review.json)。

## 版本、源码与调用路径

- GitHub 审计/交付父版本：`64b69b888ec602cf064bd12d8a16f814840c5a12`。
- 原生 Git 基线：`d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b` 加已有单播修复，保留为独立本地快照。
- 本轮原生实现本地 Commit：`828f393d685a3ecfcc88292327c456eb1c419051`。这是原生工作树提交，与外层 GitHub 交付 Commit 区分。
- 完整变更源码在 [native/src/unified-bus/model](native/src/unified-bus/model)，最小差异在 [network-replication.patch](patches/network-replication.patch)，已有基线重建补丁在 [accepted-unicast-baseline.patch](patches/accepted-unicast-baseline.patch)。限定变更文件的 SHA256 在 [source-provenance.json](source-provenance.json)。

调用路径：

```
A: SubmitNetworkPacket
   → native generated-data UbPacketQueue
   → RR/DWRR allocator → finite UbEgressQueue → UbPort → UbLink
Switch: SwitchHandlePacket → HandleNetworkPacket
   → native CBFC receive/piggyback handling
   → one input reservation + native InPortProcessingDelay
   → CompleteNetworkProcessing → native per-output VOQs
   → RR/DWRR allocator / CanEnqueue / downstream CBFC
   → independent finite egress queues → UbPort → UbLink
B/C/D: SwitchHandlePacket → network sink → actual payload comparison
   → native receive-credit return
```

关键位置（交付源码行号）：

- [ub-switch.cc](native/src/unified-bus/model/ub-switch.cc)：724 网络入口选择；1895 `NotifySwitchDequeue`；1936 `EnableNetworkReplication`；1964 `SubmitNetworkPacket`；2000 `HandleNetworkPacket`；2061 `CompleteNetworkProcessing`。
- [ub-queue-manager.cc](native/src/unified-bus/model/ub-queue-manager.cc)：264 `MoveProcessingToNetworkBranches`；276 `PopNetworkBranch`。
- [ub-switch-allocator.cc](native/src/unified-bus/model/ub-switch-allocator.cc)：709、1031，RR 和 DWRR 均使用父包释放结果控制上游信用归还。
- [ub-tag.h](native/src/unified-bus/model/ub-tag.h)：`UbNetworkReplicationTag`，64-bit bitmap、父包身份、对象/分段/目标标识。
- [ub-cbfc.cc](native/src/unified-bus/model/protocol/ub-cbfc.cc) 与头文件：只增加只读计数/查询；不改变信用消耗、返回和恢复算法。

`ub-port.cc`、`ub-link.cc`、WQE、TA、ACK/Response、Planner、计算模型和 Relay 实现未修改。

## 缓存、分支与信用

这版采用共享输入 Payload 的分支引用模型，不能把逻辑分支字节误称为独立的入口物理副本：

1. 一个入站包按原生 admission 规则占用一份 ingress/processing/physical VOQ 空间。
2. 每个选中的出口拥有自己的 VOQ 引用、逻辑 backlog 和目的 metadata。描述符数量受有限入站包数量与最多 64 个目的限制。
3. 所有分支注册完成后才唤醒仲裁，避免同步仲裁回调提前清除父状态。
4. 每个分支必须通过原生 `CanEnqueue`，进入真实有限 egress；分别消耗该输出的下游信用。
5. 非最后分支不释放父包空间，不重复返还上游信用；最后分支释放一次。采用已有 `upstreamCreditAlreadyReturned` 机制抑制重复返回。
6. 原始数据包的 piggyback credit 在复制前清除，避免把同一份反向信用复制给多个目标。
7. 收包端实际验证字节后，沿原生 CBFC 路径归还本分支信用。

原生 VOQ 的 OutPort 视图本来没有独立物理容量；真正有限的是 ingress reserve/shared/headroom 与物理 egress。实现保持这个模型，没有禁用 CBFC、无限增大队列或绕开出口容量。

源测试接口还有 1024 个排队包、单包 Payload 4096 B 的显式上限；不能装入实际 egress 的包会明确拒绝。该接口不负责 WQE 或可靠事务。

## 固定测试配置

- 5 个端点：A/B/C/D/E，加一个 Switch；E 是未选中观察端/竞争流源。
- 所有链路 100 Gbit/s、20 ns；模拟时钟精度 PS；原生入口处理 10 ns。
- 普通案例：每入口/VL reserve 16,384 B，shared/headroom 均为 0，egress 4,096 B。
- 背压案例：reserve 2,240 B，egress 1,040 B。
- CBFC cell=20×8=160 B，初始信用 floor(reserve/160)，返回粒度 1 cell，control-return threshold 1 cell。
- 普通和背压是明确的两组配置；每组 Direct/Multicast 保持参数完全相同。小队列用于主动制造背压，没有为了让组播通过而放宽容量。
- 固定 Payload 种子 `20261018 + object_id`；数据流分成 1024 B Payload 的包；每包真实 data-link header 4 B。
- 测试提交时刻 100 ns。独立背景流也在该时刻提交。
- Summary 输出；不保存完整原生 Packet Trace。只有小型单播对照为字节级回归保留了私有 Trace。

## 实测结果

完整数据见 [performance.csv](results/performance.csv)、[targets.csv](results/targets.csv)、[ports.csv](results/ports.csv)、[summary.csv](results/summary.csv)、[arbitration.csv](results/arbitration.csv)。

### 基础 Direct 对照

以下时延为源接口提交到最后目标完成的真实模拟时间差；CSV 同时保留绝对接收时刻。

| 对象 | 方式 | A Payload 字节 | A 数据线上字节 | 最后目标完成耗时 |
|---|---|---:|---:|---:|
| 64 B | Multicast | 64 | 68 | 70.880 ns |
| 64 B | Direct | 192 | 204 | 81.760 ns |
| 64 KiB / 64包 | Multicast | 65,536 | 65,792 | 5.405600 µs |
| 64 KiB / 64包 | Direct | 196,608 | 197,376 | 15.932320 µs |

64 KiB 组播的交换机产生 192 个输出分支；B/C/D 各接收 65,536 B，每个目标 SHA256 与源一致：

`2bf6bb87884cb57a66af95cbc7abda5d2eb27081e87127aa68a46699a76b9ea8`

全部完整哈希见 [verification.json](results/verification.json)。

### 动态成员与出口竞争

- 对象 0 → B/C，对象 1 → C/D；保留同源对象顺序和对象内分段顺序。没有旧成员污染；A/E 不收到未选中的数据。
- E→B 的独立背景流与 A→B/C/D 并发。组播对象 0 的绝对完成时刻：C/D 为 **8.457200 µs**，B 为 **10.686720 µs**；说明 B 分支排队时其他分支仍可前进。
- `completion_ns` 是包括背景对象的所有任务最后接收时刻；`primary_object_completion_*` 才是 A 的对象 0。不能混用两者。

### 背压与守恒

- RR 小队列组播观测到 **933** 次 credit-blocked 查询；DWRR 为 **1807**。这是阻塞查询次数，不是阻塞持续时间或丢包数。
- 每入口峰值 **2056 B ≤ 2240 B**；每物理出口峰值 **1028 B ≤ 1040 B**。
- 两个入口的父包总峰值 3084 B 合法，不应拿它与单入口 2240 B 上限比较。
- A 发出 64 个包，每个 1028 B，对应 7 cells；Switch 向 A 归还 **448 cells**，不是 1344 cells。
- B/C/D 分支分别消耗/归还 448 cells；B 还有来自 E 的 896 cells 背景流，单独纳入统计。
- 所有端口最终 free credit 恢复到初始值、pending=0；父包/分支/描述符/VOQ/egress 全部排空。
- 156 B 与 157 B Payload 案例验证 160 B cell 边界：加 4 B header 后分别是 160/161 B，正确计 1/2 cells。

所有接收对象均经过实际字节对比、完整 SHA256 和独立 Python 验证。重复、缺失、错误目标、错误字节和顺序检查不依赖总计数代替逐对象验证。

## 正确性、回归与失败记录

- 13 个正向案例：5 场景×2策略，加2个cell边界和DWRR背压。
- 4 个非法输入：空集合、反射回入口、未知rank、超大Payload，均非零退出且匹配预期错误。
- 7 个离线验证破坏：Payload损坏、截短、重复目标、错误成员、提前完成时刻、重复返信用、源copy计数错误，均检出。
- 原生 QUICK suites：49 attempted，48 PASS，1 FAIL，详见 [native-tests.json](results/native-tests.json)。MPI/MTP 未启用，未宣称覆盖对应配置。
- 失败项是 examples suite 的 dependency visibility 测试要求 `test/task_statistics.csv`，但当前原生工具子模块缺失。固定 gitlink 为 `29009175f1778f76a22d929063c3a0821cb91e56`，官方地址在原生 `.gitmodules`；本轮没有自行替换解析器。
- 原版和修改版的对应实际仿真均成功，均缺同一解析输出，且 **35 个原始事件文件逐字节一致**。见 [baseline-missing-parser.json](results/baseline-missing-parser.json)、[unicast-trace-parity.json](results/unicast-trace-parity.json)。失败断言及后续未执行的该suite子测试保留，不标记为PASS。
- 四个既有8NPU小规模 No Balancing/Direct/Two-Stage/Chunk 案例：Latency、WQE/TA、event count、全部阶段时间、payload hash、负载等所有模拟 summary 字段与已验收结果逐项相同，仅排除宿主机验证耗时；独立 Postflight PASS。见 [unicast-application-regression.json](results/unicast-application-regression.json)。随后又重新编译旧、新两个应用版本并各运行同一4策略矩阵，4/4新鲜对照通过，见 [fresh-unicast-parity.json](results/fresh-unicast-parity.json)。

构建期间遇到测试入口枚举/TypeId注册/const callback签名等测试夹具问题，已修正后完整重跑正向矩阵。没有通过关闭断言、放宽队列或削弱验证来通过。

## 宿主机资源与复现

网络案例实测峰值 RSS 约 17.9–19.2 MiB，CPU 约 0.020–0.055 s；保护程序观察的 Wall Time 约 0.25 s，包含其250 ms轮询粒度，不能用它推断精确程序耗时或模拟链路速率。

使用既有 3600 s/阶段、6 GiB RSS、7 GiB address space、8 GiB剩余磁盘、2 GiB /tmp、1.5 GiB可用内存保护。正向案例未触发保护。

在新建、干净的原生基线 checkout 中：

```
bash experiments/ub-network-multicast-poc/reproduce.sh /path/to/ns-3-ub /path/to/new-private-output
```

脚本先应用已有单播基线补丁，再应用本轮增量，复制测试入口后一次配置构建，运行矩阵、独立验证和原生 suites。依赖 C++20、CMake/Ninja、Python/psutil。若未取得官方 tools 子模块，原生 examples suite 会保留非零退出，不伪装成成功。

已编译环境中的主矩阵命令：

```
python3 experiments/ub-network-multicast-poc/run.py --binary /path/to/ns-3-ub/build/scratch/ns3.44-network-poc --private /path/to/new-runs --public /path/to/collected
python3 experiments/ub-network-multicast-poc/collect.py /path/to/collected /path/to/compact-summary
```

独立旧应用对照：`regress-unicast.py --baseline <accepted-native> --native <new-native> --private <new-output>`。每个版本重新编译应用并运行同一生成器/验证器，比较模拟字段。

## 限制与下一步

1. PacketTag metadata 的传输成本理想化为零；不是 UB 标准组播 Header。
2. 仅 network-only data packets、单交换机、CBFC，设计最多64rank；实际完整测试使用5端点，没有做64rank穷举。
3. 无多目标可靠事务、ACK/Response 聚合、丢包重传、成员失败恢复、组配置控制面时延或多交换机树。目标完成由接收观测判定，没有向A伪造组WQE成功。
4. 未接入 UltraEP；Direct 对照也使用同一网络测试接口分别发出单目标包。本轮结果只说明网络复制能力。
5. 未进行完整 sanitizer 矩阵；原生外部工具缺失项已明确记录。
6. 下一阶段可在本网络复制基础上独立设计可靠多目标状态与失败语义，需另行验收授权后开展。

## Knowledge Sources

- 前一轮 [可实现性审计](../ub-multicast-feasibility/REPORT.md)：原生单出口路径、信用归属和可靠性边界。
- 原生 `UbQueueManager::CheckIngressAdmission`、`UbEgressQueue::CanEnqueue`、`UbCbfc::IsFcLimited`：物理 admission、egress 和 CBFC 背压依据。
