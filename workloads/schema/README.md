# WR Trace 1.0

这是独立于 Nano-UB、SystemC 和 MoE 的**通信需求接口**，不是仿真结果格式。UTF-8 CSV、逗号分隔、LF 换行、标准 CSV 转义，字段顺序固定：

```csv
schema_version,wr_id,src_node,jetty_id,dst_node,opcode,payload_bytes,ready_ns,sequence,depends_on,phase
1.0,0,0,1,2,WRITE,128,0,0,,dispatch_data
1.0,1,0,1,3,WRITE,256,100,1,0,dispatch_data
```

| 字段 | v1.0 约定 |
|---|---|
| schema_version | 字符串 `1.0`；未知版本拒绝。空 trace 仅保留该版本的固定表头 |
| wr_id | 全 trace 唯一的非负 int64；不要求连续。Generator 输出从 0 开始连续 ID |
| src_node / dst_node | 非负 int64 节点 ID；v1 为远程 WRITE，源目标相同拒绝；节点编号不要求连续 |
| jetty_id | 非负 int64，命名空间为 src_node；`(src_node, jetty_id)` 才是端点身份，不是 TP Channel ID |
| opcode | 目前仅 `WRITE`；其他操作拒绝，不悄悄转换 |
| payload_bytes | 正整数；WR 实际要求传送的应用内存字节数，等于所有有效 SGE 长度之和。包括**确实被传送**的应用布局 padding；不包含链路头部、SQE/SGE 描述符或 ACK。不是只计 hidden tensor 的有用数学数据 |
| ready_ns | 非负整数 ns，应用最早可提交时刻；既不是实际派发时间，也不是完成时间或服务时间；本阶段生成值均为假设 |
| sequence | 每 `(src_node, jetty_id)` 从 0 开始连续递增的提交序号，与 CSV 中该 Jetty 的行顺序一致 |
| depends_on | 可选依赖语义，空单元格表示无依赖；否则为 `;` 分隔的不重复 wr_id。所有依赖必须指向文件中更早的行，表达这些 WR **完成后**才有资格提交；因此缺失、自依赖、前向引用、循环均拒绝 |
| phase | 可选标签，空值允许；最多 64 个 ASCII 字母、数字、`_`、`-`、`.`。只是标签，不隐含屏障或依赖 |

所有整数采用无符号十进制文本（零或非零数字开头），上限 2^63−1。拒绝小数、科学计数法、负值、NaN、Inf、bool、重复表头、额外字段、缺字段和坏 CSV。不得添加 policy、quantum、完成时间、Flit、PSN 等实现字段。

CSV 全局按 `ready_ns` 非递减；同时间行的原有顺序是稳定的候选入场顺序，不强制模拟器在不同 Jetty 之间采用该顺序调度。`sequence` 保证 Jetty 内提交顺序，**不等于所有前序请求都必须完成**；完成依赖必须用 `depends_on` 明示。若后端不支持某个字段语义，必须拒绝或报告，不得静默丢弃。

v1 的所有列必须存在，但依赖和阶段内容可空。`wr-trace-v1.schema.json` 是 JSON 行对象的机器可读约束；CSV 中 `depends_on` 解码后为整数数组。跨行唯一性、时间排序、sequence 和依赖拓扑由 `trace.py` 检查，不能仅靠单行 JSON Schema。Generator 不导入模拟器、调度策略或 NPU 库；验证器仅依赖 Python 标准库。

## 元数据与支持边界

`TRACE.csv.meta.json` 记录 Generator 参数、假设和配置的 Jetty 集合（含空 Jetty），可独立于 CSV 使用；通用 validator 不需要该文件。MoE 独有的 token、SGE、布局、路由和末 SQE 标记位于独立 `.moe.jsonl` / `.routes.jsonl`，以 wr_id 或 token 身份关联，不增加通用字段。

应严格区分：

1. token：应用对象；可发送到多个去重后的远端 rank；本地 rank 只做本地拷贝。
2. SGE：一个内存片段；当前 MoE profile 每 token-rank 对有 hidden 和 metadata 两个 SGE。
3. payload_bytes：实际传送的 SGE 数据总量；侧车另记 `semantic_bytes` 和 `padding_bytes`，二者相加等于 payload。
4. SQE 描述符、WQEBB：本地发送队列占用，不是 WR payload 或网络线字节。
5. 线字节：后端依据其明确的网络模型推导。**v1 不写死 `64+payload`**，也没有带宽、链路延迟、ACK 或完成结果。

通用 v1 未覆盖多 SGE 目标地址、内存 key、传输 ODR、Fence、CQE 策略、原子操作、局部失败、取消或跨阶段控制通信。MoE profile 保存末 SQE fence/CQE 来源事实于侧车，但不冒充通用完成依赖。这意味着 Phase 2 只能明确选择“远程 data WRITE 需求模型”，或先扩展接口处理传输标志；不能宣称 v1 已重放完整 Dispatch 协议。

## 命令

```bash
python3 -m workloads.schema.validate experiments/phase1/output/traces/moe_high.csv
python3 -m unittest discover -s workloads/tests -v
```

版本升级：改变单位、payload 含义、排序/依赖约束或增加必需字段时必须新版本并提供显式转换；当前严格拒绝未知版本和额外列。
