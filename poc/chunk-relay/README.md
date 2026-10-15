# 三节点 Chunk Streaming Relay PoC

本目录是独立 ns-3-ub 应用 PoC，不改 Nano-UB/SystemC 代码或 ns-3-ub 底层。真实路径为 A(port0) ↔ B(port0)，B(port1) ↔ C(port0)，两个独立 UbLink；B 是接收后重新发起 WQE 的应用中继。没有固定延迟代替通信，没有使用 OnTaskCompleted 或 LastPacketReceivesNotify 判定 Chunk ready。

## 固定版本与复现

- ub-test 基线：`9394048466813e747ca52a72ec0f0463a0c327c6`
- ns-3-ub：`d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`
- ns-3-ub-tools：`29009175f1778f76a22d929063c3a0821cb91e56`
- 本次工具：Python 3.12、CMake 4.4.4、Ninja 1.13.2、g++；单构建进程 `-j 4`。

从 ub-test 根目录运行：

```bash
bash poc/chunk-relay/run.sh
```

可指定 `NS3_ROOT`、`BUILD_TOOLS`、`PYTHON`、`BUILD_JOBS`、`OUT`（建议绝对路径）。脚本在缺少仓库时从 GitCode 克隆并检出固定提交；已有仓库 HEAD 不符则停止，不覆盖用户版本。它验证固定子模块、在工作目录内安装缺失的 CMake/Ninja、复制两个应用文件至 ns-3 scratch、配置 UB 依赖闭包、编译、运行双节点诊断与两个三节点案例、执行测试。未安装图形/拓扑生成 Python 依赖，未修改全局环境配置。`OUT` 中的同名证据会由新运行替换。

单独运行参数化网络应用（先完成脚本构建）：

```bash
cd /workspace/ns-3-ub
PATH=/workspace/build-tools/bin:$PATH PYTHONPATH=/workspace/build-tools \
python3.12 ./ns3 run --no-build \
'chunk-relay --chunk0Bytes=65536 --chunk1Bytes=262144 --segmentBytes=8192 --computeNs=5000 --output=/tmp/relay.csv'
```

## 实现和语义

`tracker.h` 是无 ns-3 依赖的区间覆盖/去重组件。每条通知绑定 ID、offset、length；相同 ID 的冲突范围拒绝，重叠范围取并集，缺口不算完成，完整覆盖只产生一次 ready。`chunk-relay.cc` 独立实现拓扑、RTP 通道、Jetty、目标执行回调、动态 SubmitWqe、计算事件与 CSV 时间线。

每 hop 每 Chunk 使用一个全新 Jetty，TASSN 从 0 开始；任务 ID 编码 hop 和 Chunk。offset = TASSN × segmentBytes，在此限定映射下校验源/目标、opcode、resolved metadata、逻辑长度、payload 长度和完整覆盖。默认两个 Chunk 是 65,536 B 和 262,144 B，各拆为 8 和 32 个 TA，每跳合计 40 TA。每端口 100 Gbps，链路传播 20 ns；这些是本 PoC 的仿真参数，不是实际硬件性能声明。

`SetTargetExecutor` 接收的是传输层重组后的完整请求。应用调用 `done(success)` 后记录 `target_ta_complete`，随后通知 Tracker；最后一个 TA 才产生 `chunk_complete`。B 在相同仿真时刻调用 Send(1,chunk)，仅该 Chunk 有依赖，不等另一个 Chunk。独立 NPU 事件在 B ready 时开始、由 `Simulator::Schedule` 在 computeNs 后结束，不阻塞转发；没有计算容量/排队模型。

事件必须区分：

- `ta_send_admitted`：真实 TP 接纳 TA 的事件，非首字节上线时间。
- `target_ta_received`：目标执行回调入口，已重组的请求。
- `target_ta_complete`：本应用完成目标执行并调用 TA completion；不是发送端 ACK 完成。
- `chunk_complete`：应用累计完整覆盖的瞬间。
- `forward` / `chunk_send`：提交下一跳动态 WQE。
- `sender_wqe_complete`：Jetty 发送端完成回调；本应用没有 UbApp phase 和额外 100 ns 的依赖可见性通知。
- `compute_start/end`：参数化独立计算事件。

没有注册 traffic phase，因而也不会伪造或完成不存在的 phase。每次动态 WQE 准入都检查 ACCEPTED。拓扑/通道初始化参考固定版本的 `ub-node-test-fixture.h`、`ub-target-execution-test.cc`，但运行不调用测试 helper 或直接注入 TA；数据走 UbFunction → Transaction → Transport → Port/Link → 目标 Transaction，TA 响应走原模型返回。

## 双节点 Processed 0 tasks 诊断

原工具 `task_statistics.py` 的 `pattern="*.tr"` 与旧正则不能读取当前 `time_ps,event,...` CSV。模型确实运行并完成四个 WQE：完成时间分别为 31.368760、31.702680、33.369640、33.613627 µs。目标侧每任务有 7 个唯一 TA SSN；原始通知重复记录两次，不能简单按行数认定有 14 个 TA。保留的 ACK trace 有 856 行（包含重复行），仅证明实际 ACK 活动，不能当作 856 个独立 ACK。

`diagnose-smoke.py` 在应用侧直接解析 CSV 并输出 `smoke-diagnosis.json`，不更新固定 tools 提交。接收侧 `WQE Segment Completes` 在 `CompleteInboundTaUnits → HandleInboundTaUnit` 之后记录，不是目标执行 done 的专用 trace；不能把这条日志单独冒充目标执行完成。原案例的发送端完成加原始 TA/ACK 事件支持“统计工具不匹配而非真实未完成”；三节点程序另外直接记录 executor completion，消除这一观测边界。

## 已执行结果

所有时间为仿真时间，单位 µs；完整原始时间线在 `evidence/events.csv`（整数 ps）。

| 事件 | Chunk 0 | Chunk 1 |
|---|---:|---:|
| A 提交 | 0.010 | 0.010 |
| B 目标 TA 全部完成 / Chunk ready | 10.120 | 26.945 |
| B 立即转发 | 10.120 | 26.945 |
| A 发送端 WQE 完成 | 10.155 | 26.980 |
| B 计算开始 | 10.120 | 26.945 |
| B 计算结束 | 15.120 | 31.945 |
| C Chunk 完成 | 15.519 | 48.496 |
| B 发送端 WQE 完成 | 15.554 | 48.531 |

A→B Chunk 1 与 B→C Chunk 0 的真实 TA 活动区间重叠 **5.399 µs**；验证器还要求重叠窗口内两跳各有目标 TA 到达事件，避免仅用提前提交的 WQE 制造重叠。B Chunk 0 计算与通信重叠 **5.000 µs**。C 最终收齐 2 个 Chunk，共 80 个目标 TA 完成，4 个发送端 WQE 完成，无丢失、提前或重复转发。

第二个真实网络案例使用 65,537 / 262,147 B、4096 B TA、2000 ns 计算，覆盖非整除末段：164 个目标 TA、2 个 C Chunk、通信重叠 5.445 µs、计算重叠 2 µs。结果见 `variant-verification.json`。

自动化检查：Tracker 测试覆盖乱序、完全重复、重叠覆盖、单字节缺口、重复完成、冲突 ID、零长度、越界、整数溢出与 Chunk 独立性；8 个 Python 测试验证正常事件，并拒绝缺失 TA、错误长度、提前/重复转发、缺失 C 完成和错误计算依赖，另测试不相交/端点相接不算重叠。网络验证器逐 TA 检查覆盖和次数、每 Chunk ready/转发/发送端完成关系、两跳及计算重叠。上述元数据负例操作 Tracker 或事件副本；最终版本另有真实网络 payload 单字节损坏负例（见下文），不模拟物理链路随机错误。

## 完整性能力边界

**最终版本已使用固定底层版本提供的 ExplicitPayload API，未修改协议实现。** A 按 Chunk ID 与绝对 offset 生成非恒定确定性字节，设置 `UbWqe::SetExplicitPayload(Create<Packet>(bytes,...))`；UbFunction 分 TA、UbTransport 再分包，接收端重组后由 `request->GetExplicitPayload()->CopyData` 读取实际字节。B、C 对每个 TA 逐字节与独立计算的期望值比较；B 将真正收到的 buffer 作为下一跳 payload，绝不在 B 重新生成数据。每个正常运行共校验 655,360 个 hop-payload 字节（327,680 B × 两跳）。

真实网络负例 `--corrupt=1` 在 B 转发 Chunk 0 前翻转一个字节，C 在 13.500 µs 以 `payload byte mismatch` 拒绝；脚本要求进程失败且出现此错误才判负例测试通过。证据在 `corrupt-console.txt`、`corrupt-test.txt`。这验证了本案例显式字节的应用完整性，不等于任意业务负载、随机网络位翻转、物理硬件或完整 tensor 模型验收通过。

最初元数据版的源码与证据保留于提交 `7ae0407c93cfa6feed634f8cbe63496efb65d68d`，交付包另附原始证据。其“未检查字节”是历史范围，不是底层能力限制。底层既支持长度占位 Packet，也支持显式 payload；之前未启用后者。
尚未证明任意拓扑/拥塞/丢包/重传负载下的 relay 正确性与性能。重复和乱序通知目前在应用组件层验证；主网络运行使用模型正常流量。计算仅是独立定时事件，不是完整 Compute 解析模型。三节点 PoC 已到此停止。

## 文件和证据

- 源码：`chunk-relay.cc`、`tracker.h`。
- 复现与校验：`run.sh`、`verify.py`、`diagnose-smoke.py`、`tests/tracker-test.cc`、`tests/test-verifier.py`。
- `evidence/events.csv`、`variant-events.csv`：每个 TA 和 Chunk 的完整时间线。
- `evidence/smoke-raw/`：原双节点 Task、Packet、ACK CSV；`smoke-diagnosis.json` 是适配解析结果。
- `evidence/*console.txt`、`configure.txt`、`build.txt`：真实运行/构建输出。
- `evidence/*verification.json`、`*tests.txt`：自动化验证结果。

仅新增本目录文件；没有更改现有模块。ns-3 工作树只增加 scratch 应用文件，未修改跟踪的底层源码。全部仅本地保存和 commit，不 push。

## Future Work（待研究假设）

后续可研究 UB 动态硬件组播是否可用、组配置与控制成本、与 Chunk Relay 的比较，以及不同拓扑和 replica fanout 下的适用条件。目前不假定 UB 或本 ns-3 模型具备此能力，也不把“论文为何选择 Relay”当成已证实事实。下一里程碑须等待用户验收后决定。


## 最终复核补充

每个 hop 一个 Chunk 对应一个 WQE，但拆成多个 TA：Chunk 0 为 8 TA，Chunk 1 为 32 TA，因此 (8+32)×2=80 TA；两个 Chunk × 两跳=4 次发送端 WQE 完成。TA ready 使用真实 `UbTransaction::SetTargetExecutor` 注册的回调，回调在重组请求进入 `RunInboundTransaction` 后调用；应用做字节验证、调用 `UbTargetCompletion done(success)`，再更新 Chunk Tracker。

通信窗口定义：每 hop/Chunk 的区间为首个 `WqeSegmentSendsNotify` 接纳时间至最后目标 TA 完成时间。默认 A→B Chunk 1 为 [0.010,26.945] µs，B→C Chunk 0 为 [10.120,15.519] µs，交集 [10.120,15.519] µs。窗口内两跳都必须存在真实目标 TA 到达事件。该定义不是精确物理链路逐字节忙碌区间。计算区间 [10.120,15.120] µs，由 computeNs=5000 明确参数生成；与通信交集为 5 µs。链路 20 ns 是 UbLink 传播参数，未用固定延时直接触发网络接收或 Chunk ready。

重复/乱序/覆盖/缺口负例均实际执行于 `tracker-test.cc`；网络字节损坏负例实际走 B→C 链路。最终默认与末段变体重新构建运行，8 项 Python 测试重新通过。验收结论为本三节点案例及所列测试通过，非全部系统需求验收通过。
