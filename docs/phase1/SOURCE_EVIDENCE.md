# DeepEP-Ascend 源码核验

核验的公开仓库：https://github.com/deepseek-ai/DeepEP-Ascend 。固定提交 **`3b25377d04b24fc6154698ded78a2bcb2c59afff`**，提交标题 Initial public release，日期 2026-09-29。读取时 `origin HEAD` 与此提交一致。以下链接均固定 commit，文件 SHA256 另见 `source_manifest.json`。没有编译或执行 NPU kernel，也没有把注释中的时间数值当测量。

## 源码事实

| 主题 | 事实与代码证据 |
|---|---|
| AIV / Jetty | [hccl.hpp L196–228](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/csrc/kernels/comm/hccl.hpp#L196-L228) 创建一个 AIV 对应的本地 Jetty，供它的多个 peer 使用；[L237–269](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/csrc/kernels/comm/hccl.hpp#L237-L269) 的 channel/peer 表不意味着每个 peer 各自有一条独立 Jetty |
| 分区 | [dispatch.hpp L77–98、132–170](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L77-L170)：每 AIV 拥有 `ceil(max_tokens_per_rank / AIV)` 长的连续 token 区间，再裁到实际 num_tokens；必须区分实际 token 数与配置容量 |
| rank 路由及去重 | [L174–194](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L174-L194)：expert ID 除以 experts_per_rank 得到 rank；同一 token 内同 rank 去重；本地 rank 进入 local copy 路径。不能把 top-k expert 数直接当网络复制数 |
| 聚合边界 | [L199–207](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L199-L207)：每 AIV、每远端 rank 根据 histogram 分配 `ceil(count/6)` 个逻辑 SQE；[L257–282](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L257-L282) 映射到连续目的槽。每个非空 AIV/目的 rank 最多一个不满尾块，不跨 rank/AIV 补满 |
| Pair 是什么 | [L343–415](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L343-L415)：该 Dispatch 路径的一对是一个 token-rank 拷贝的 hidden SGE 和 metadata SGE，SGE 数是 pair 数的两倍，最多 6 pair/12 SGE。因此**仅在该路径**可把满 6 pair 理解为同一远端 rank 的 6 个不同 token 拷贝；不是任意 URMA 语境下“pair=token” |
| 数据量 | [token.hpp L17–42](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/layout/ep/token.hpp#L17-L42) 给出元数据布局和对齐；[compiled.hpp L33–43](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/common/compiled.hpp#L33-L43) 是 int16 scale pack、32 B 对齐等常量。Metadata 含 top-k IDs、weights、源 token ID，FP8 时还传 scale packs |
| 队列占用 | [dispatch L357–375、384–418](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L357-L418)：SQE header 48 B，SGE 描述符每个 16 B；每物理 SQE 预留四个 64 B WQEBB，空余可放 NOP。这些**不是网络 payload 或网络头部** |
| 发布机制 | [L598–608](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L598-L608) 明确所有 SQE 在 doorbell 前写好；[L847–857](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L847-L857) 等 SIMT 完成后一次 advance/ring。未找到按计时器、token 间隔或“凑不够就提前发”的流式 flush |
| 到达相关前置工作 | [L642–685](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L642-L685) 有跨 rank barrier 和 SIMT；[L431–448](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L431-L448) 等 metadata ready，local copy 也在门铃前。非 cached 的 rank/expert 统计与通知不是此 trace 中的 data WRITE；没有假造这些前置工作的周期数 |
| 请求顺序 | [L181–206、327–350](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L181-L350) 的 rank histogram、逻辑 SQE 基址、物理 SQE 计数由并行原子操作分配。源码不承诺跨 warp 的确定仲裁顺序，不能声称 CPU 排序就是实际物理顺序 |
| 最后一个 SQE | [L392–396](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/impls/ep/dispatch.hpp#L392-L396) 设置 final flags；[handle.hpp L18–32](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/include/deep_ep/comm/handle.hpp#L18-L32) 显示普通 WRITE ODR=1，末 WRITE ODR=5、fence=1、CQE=1。不能把它简化为每 WR 独立 CQE 后声称完整复现 |
| Gate helper | [gate.py L140–173](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/deep_ep/utils/gate.py#L140-L173) 用不同幅度随机分数和 top-k 构造倾斜；目标流量 ratio 的求解依赖随机采样和迭代。它是测试负载机制，不是生产模型路由的实测分布 |
| 边界 | [host dispatch L43–49](https://github.com/deepseek-ai/DeepEP-Ascend/blob/3b25377d04b24fc6154698ded78a2bcb2c59afff/csrc/kernels/ep/dispatch.hpp#L43-L49) 要求至少 16 AIV；设备侧最多 64、top-k 不超过 warp 32、当前 worker 512 threads。生成器取这些已核查边界并核验最坏 SQE 占用，不模拟容量不足时的虚构 flush |

## 模型选择，不属于源码保证

- 只生成 uncached Dispatch 的远程 payload WRITE。cached 重用布局、Combine、同步/统计信号、doorbell 本身、NOP、本地拷贝都不作为额外网络 WR；本地数据量另记。没有复刻完整 Dispatch kernel。
- token 在每个 AIV/rank 组中按 token ID 升序；远端 rank 块按相对 src 的循环次序。这是固定、可复核的原子仲裁近似，保留分组和数量，不声称重现真实并行顺序。
- Gate 采用 Python CPU double RNG 的 uniform score × hot-rank factor，然后选无重复 top-k；与源码 factor-score 家族对应，但与 torch/NPU RNG 不逐位一致。不实现 `precise` ratio 生成器或其迭代拟合。factor 是**分数幅度倍数**，不是最终流量比；hot-rank 可更换视作节点重编号扩展。
- 默认全 AIV 的 doorbell-relative ready_ns=0，把门铃前工作折叠掉。可输入 `start + AIV*stagger + owned_tokens*prep` 的假设，每个 AIV 的所有 WR 同时 ready，不改变聚合、不增加 timeout flush。没有使用源码注释的微秒数来伪装 NPU 测量。
- 不模拟 UB buffer 分阶段 MTE、专家 padding 分配、实际地址、cache、CQE drain 或吞吐；prefix sum 只取其决定目的槽连续性及分组的结果，不建立内部算子模型。SF pack 个数必须由用户显式提供，避免凭 hidden size 猜测量化格式。
- 最后 SQE 的 fence/CQE 记录在 MoE 侧车，不能无证据转换成“所有此前事务完成后才可提交该 WR”。通用 CSV 只表达通信需求和确定的提交顺序，Phase 2 应明确补充/拒绝缺失的传输顺序语义。

## 准确的大小公式（uncached）

令 H 为 hidden 元素数、B 为元素字节数（BF16=2、FP8=1）、K 为 top-k、F 为 int16 scale pack 数，A(x)=向上对齐到 32 B。

- hidden SGE 长度：H×B。
- metadata SGE 长度：A(2F) + A(A(8K) + 4K + 4)。当 F=0 第一项为零。
- 单 pair 的 WR 数据：上面两个 SGE 长度之和。
- 非 padding 的语义数据：H×B + 2F + 8K + 4K + 4。
- n pair 的 WR payload：n × 单 pair 数据，1≤n≤6。

样例 H=1024、BF16、K=4、F=0：hidden=2048 B、metadata=64 B、每 pair=2112 B，其中语义数据=2100 B、padding=12 B；WR 大小为 2112..12672 B 的六种整数倍。这里不添加原 Nano-UB 实验的 64 B 链路成本。
