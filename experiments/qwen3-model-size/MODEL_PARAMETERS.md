# Official Qwen3-30B-A3B parameter check

Retrieved 2026-10-17 UTC. No weights were downloaded or executed.

## Pinned sources

- Official model repository `Qwen/Qwen3-30B-A3B`, revision `ad44e777bcd18fa416d9da3bd8f70d33ebb85d39`; repository API reported last modified 2025-07-26T03:45:17Z. This is the repository date, not the date of the last change to config.json.
- [Official config](https://huggingface.co/Qwen/Qwen3-30B-A3B/resolve/ad44e777bcd18fa416d9da3bd8f70d33ebb85d39/config.json): 963 bytes, SHA256 `2850ddb3bf7aecad20b611e2d44f3077fc8193f4827c93beddd4c02ad63c2297`.
- [Qwen model implementation in Transformers v4.51.0](https://github.com/huggingface/transformers/blob/0720e206c6ba28887e4d60ef60a6a089f6c1cc76/src/transformers/models/qwen3_moe/modeling_qwen3_moe.py#L205-L263). Tag resolved to immutable commit `0720e206c6ba28887e4d60ef60a6a089f6c1cc76`. `Qwen3MoeMLP` has gate/up/down linear projections without biases; `Qwen3MoeSparseMoeBlock` has 128 routed experts and no additional shared-expert path. Router weights are separate from each expert's three matrices.

## Config facts

Hidden size H=2048; expert intermediate size I=768; 128 experts; top-k=8; BF16; SiLU activation. The config also contains general `intermediate_size=6144`, which is NOT the routed-expert width: the sparse block explicitly passes `moe_intermediate_size`. There are 48 layers, but the requested experiment models one MoE layer only. The config's sparse-step and dense-only-layer settings select MoE at each decoder layer. Top-k is normalized in the reference router; this experiment instead supplies synthetic Zipf assignments and does not reproduce real model gate outputs.

## Derived quantities and simulation assumptions

Per expert, three dense matrices contain `3*H*I = 4,718,592` parameters. BF16 storage is `2*3*H*I = 9,437,184` bytes = exactly 9 MiB. This excludes the shared router, metadata, padding and allocator overhead.

A BF16 hidden vector is `2*H = 4,096` bytes. Using one hidden vector per dispatch and one per combine gives 4,096 bytes per direction per remote assignment (8,192 bytes round trip). This is a simulator payload convention, not a complete network-byte prediction: task metadata and UB protocol headers must be counted separately if present. Local assignments incur no remote dispatch/combine payload. Top-k=8 means eight logical assignments per token, not one WQE per original token.

Under the conventional GEMM count of two FLOPs per multiply-accumulate, the three projections cost `6*H*I = 9,437,184` FLOPs per assignment. For an expert assigned M tokens, the GEMM approximation is `6*M*H*I`. It omits SiLU, the elementwise gate/up multiplication, weighted combine, router and other kernels. These omissions should remain stated rather than silently modifying the accepted compute model. For assumed effective G GFLOP/s, the pure GEMM duration in ns is `F/G`, with the existing executor's fixed overhead and rounding rules applied unchanged. G is assumed effective throughput, not an Ascend measurement.

Compared with H64/I128: expert parameters, weight bytes and GEMM FLOPs increase 192-fold; vector payload increases 32-fold. Baseline expert weight is 49,152 bytes (48 KiB), baseline GEMM FLOPs 49,152 per assignment, baseline vector payload 128 bytes. The model-size comparison must adjust all these together.

Fixed effective throughput ignores load-dependent GEMM utilization, memory-bandwidth/weight-read costs, kernel-launch costs beyond any existing configured constant, cache effects and hardware scheduling. This is a model-size sensitivity experiment with synthetic routing, not measured Qwen3 inference latency or full-model performance.
