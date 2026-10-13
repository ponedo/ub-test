# Nano-UB 多 Jetty FIFO/RR/DRR 实验

2026-10-13：通用 WR Trace 接入与 Phase 2 实测见 [报告](docs/phase2/REPORT.md)；`scripts/run_phase2.sh` 完整复现。

2026-10-12 已在 ub-test 完成最小 SystemC 端到端 WRITE 实验。实现、假设、结果与复现说明见 [docs/E2E_REPORT.md](docs/E2E_REPORT.md)。

## 当前可运行路径

`bench/scheduler_e2e.cpp` 将 `JettyFairScheduler` 接到真实 Nano-UB UB URMA TX、RX、内存及返回完成模块。三策略同路比较。原模块保留默认行为，实验通过显式选项启用 RC 保留、精确 ACK 回收、保守排序及完整 WRITE 负载/完成反馈。链路字节串行化是新增实验模型。

```bash
./scripts/bootstrap_systemc.sh
source .deps/env.sh
./scripts/run_e2e.sh
```

已通过 15 项回归/边界测试、16 次 E2E 运行、3 次确定性重复对照。真实事件和统计在 `eval/e2e/`。混合负载三策略 payload 吞吐均为 87.046 Gbps；DRR 在所选积压窗口改善字节 Jain 和总体 P50，但大 WR 的 P50 变差，未提高总吞吐。

## 必须保留的边界

- `64 + mem_len` 是线字节成本假设，不是规范精确线长。
- 链路按最大 64 B 块搬运真实数据；块不是独立 UB 数据包。WR 仍是原子调度对象，只有一个 PSN/TASSN。
- Fence 为保守屏障，排序为保守全局域；不宣称完整 UB Fence/ROI/ROT 语义。
- 不覆盖丢包恢复、PSN 回绕、多 TP 通道；无实际 NIC 性能主张。
- 原根目录 `results.csv` 与纯 C++ 微基准不是此次 SystemC E2E 证据。

新增模块入口：`include/nano/experimental/serialized_link.h`；调度器：`include/nano/ub/fair_scheduler_sc.h`；边界测试：`tests/m13_scheduler_guards.cpp`；分析器：`scripts/analyze_e2e.py`。
