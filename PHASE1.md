# Phase 1：独立 WR Trace 与 Workload Generator

本分支基于已发布的 `9394048466813e747ca52a72ec0f0463a0c327c6`，仅新增 Phase 1 文件。原 SystemC 源码、15 CTest 和 16 E2E 基线全部保留；本阶段没有 adapter、没有新调度算法、没有新的 FIFO/RR/DRR 性能运行。

- [短报告与结果](docs/phase1/REPORT.md)
- [源码核验与事实/近似边界](docs/phase1/SOURCE_EVIDENCE.md)
- [通用 CSV Schema 1.0](workloads/schema/README.md)
- [一键复现](experiments/phase1/run.sh)
- 图和统计：`experiments/phase1/output/analysis/`
- 可直接读取的 traces、路由与 MoE 侧车：`experiments/phase1/output/traces/`

```bash
# Generator / validator / tests：Python >=3.10 标准库即可，无需 SystemC 或 NPU。
python3 -m unittest discover -s workloads/tests -v
python3 -m workloads.generators.synthetic --sizes 64,256,1024 --output /tmp/synthetic.csv
python3 -m workloads.generators.moe_dispatch --tokens 4096 --capacity 4096 --seed 42 --output /tmp/moe.csv
python3 -m workloads.schema.validate /tmp/moe.csv

# 图表需要 Matplotlib；依赖已可用时直接运行：
./experiments/phase1/run.sh
# 如未安装：在自己的虚拟环境中安装 experiments/phase1/requirements-analysis.txt。
# 支持 PHASE1_OUTPUT=/absolute/output 指定新输出目录。
```

Synthetic 参数：`--jetties`、`--wr-per-jetty`、`--sizes`（一个值或每 Jetty 一个值）、`--src-node`、`--dst-node`、`--arrival batch|burst|poisson`、`--burst-size`、`--burst-gap-ns`、`--mean-gap-ns`、`--start-ns`、`--seed`。默认三 Jetty、各 256 WR、每次 8 WR 交替，大小为 64/256/1024 B；`--sizes 256` 为等长对照。默认源/目标编号是 0/1；需要与原 C++ 源/目标地址编号一致时使用 `--src-node 1 --dst-node 2`。基线对齐测试核对 WR ID、Jetty、sequence、大小和提交时刻。

MoE 参数：`--tokens`（每个被纳入源 rank 的实际数）、`--capacity`（配置最大数，省略时 max(1,tokens)）、`--hidden-size`（元素数）、`--dtype bf16|fp8`、`--sf-packs`（int16 pack 个数）、`--top-k`、`--experts`、`--ranks`、`--aivs`、`--src-nodes 0,1|all`、`--score-factor`、`--hot-rank`、`--seed`、`--start-ns`、`--aiv-stagger-ns`、`--token-prep-ns`。默认只纳入源 rank 0；目标来自所有 ranks。FP8 必须显式传正的 sf-packs，BF16 必须为 0。本阶段只实现 uncached Dispatch data WRITE profile。

需要核查原始公开源码时，可在独立位置 clone 后固定提交（不需要 NPU 库或子模块）：

```bash
git clone https://github.com/deepseek-ai/DeepEP-Ascend.git /tmp/deepep-source
git -C /tmp/deepep-source checkout 3b25377d04b24fc6154698ded78a2bcb2c59afff
python3 experiments/phase1/verify_source.py /tmp/deepep-source
```

所有 ready_ns 都是假设输入，分布统计不是硬件采样或 SystemC 性能证据。相同配置、seed 和受测 Python 版本生成相同 CSV/JSON 字节；不声称与 NPU torch RNG 相同。
