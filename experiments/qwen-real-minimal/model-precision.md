# Qwen3-235B-A22B-FP8 precision and sizing

This experiment uses official model dimensions with **ideal FP8 expert-weight payloads and BF16 activation transport**. It does not execute a numerical Qwen model or measure hardware performance. Verification used public config, tensor-name index, repository metadata and official implementation source; no model-weight tensors or shard headers were downloaded.

## Official dimensions and weight format

Pinned model revision: `39eb2b067ea6b8e3e1dd97d3cd0c7ffeaf3e1a35`.

The [official config](https://huggingface.co/Qwen/Qwen3-235B-A22B-FP8/resolve/39eb2b067ea6b8e3e1dd97d3cd0c7ffeaf3e1a35/config.json) specifies hidden size H=4096, routed-expert intermediate size I=1536, 128 experts, top-k=8 and 94 layers. Use `moe_intermediate_size`, not the separate `intermediate_size=12288`. Quantization is E4M3 FP8 with 128×128 weight blocks and dynamic activation quantization; `torch_dtype` is BF16.

[Transformers v4.51.0 Qwen3-MoE](https://github.com/huggingface/transformers/blob/v4.51.0/src/transformers/models/qwen3_moe/modeling_qwen3_moe.py#L223-L252) implements three bias-free matrices: gate/up [1536,4096] and down [4096,1536]. Therefore:

- Parameters per expert: 3HI = 18,874,368.
- **Simulated ideal FP8 payload: 18,874,368 bytes = 18 MiB per expert.**
- [FP8Linear v4.51.0](https://github.com/huggingface/transformers/blob/v4.51.0/src/transformers/integrations/finegrained_fp8.py#L294-L353) uses FP32 `weight_scale_inv` with ceil(out/128)×ceil(in/128) entries. Three matrices require 1152 scales = **4608 additional bytes per expert**.
- FP8 weights plus scale tensors: 18,878,976 bytes per expert. The experiment omits these scale bytes (0.0244140625% of the ideal weight payload), runtime padding/repacking and allocation overhead. Its 18 MiB transfer size must not be described as exact checkpoint or runtime footprint.

The [pinned tensor-name index](https://huggingface.co/Qwen/Qwen3-235B-A22B-FP8/resolve/39eb2b067ea6b8e3e1dd97d3cd0c7ffeaf3e1a35/model.safetensors.index.json) confirms separate weight and scale entries for all three expert matrices. Scale shapes/dtype above are established from config plus matching-version official implementation, not inspection of individual stored tensor headers. Index total tensor bytes are 239,034,937,344; [HF revision metadata](https://huggingface.co/api/models/Qwen/Qwen3-235B-A22B-FP8/revision/39eb2b067ea6b8e3e1dd97d3cd0c7ffeaf3e1a35) reports both F8_E4M3 and F32 storage. The checkpoint is not uniformly FP8, and BF16 config dtype must not be mistaken for every stored tensor's dtype.

## Activation and compute assumptions

Dispatch and combine each carry an H-dimensional BF16 vector: **2H=8192 bytes per token-expert assignment per direction**, or 16,384 bytes round trip, before metadata/protocol overhead. Actual network traffic also depends on locality. BF16 wire precision is an explicit simulator assumption. Dynamic FP8 GEMM-input quantization in the official implementation does not imply FP8 expert-parallel network transport.

Counting multiply-add as two FLOPs, the three GEMMs cost **6HI=37,748,736 FLOPs per assignment**. SiLU, elementwise product, routing, weighted combine and quantization overhead are outside this GEMM count. Effective compute stays at the existing hypothetical **500 GFLOP/s** (`peak_gflops=1000`, `util_permille=500`), regardless of weight precision: 75.497472 microseconds per assignment before fixed setup. This is an assumption, not an FP8 hardware benchmark.

## Existing fixed compute cost, unchanged

Read-only source verification against local application commit `73c636b618c9f30694bc00a10443ea61c09dcd9a` (published matching tree at `289abb53132171b0028c8b3bb0b95a5c0f5ae172`) found no local change to [pair-layer.cc](https://github.com/ponedo/ub-test/blob/289abb53132171b0028c8b3bb0b95a5c0f5ae172/experiments/pair-jetty/pair-layer.cc#L316-L323) (SHA-256 `cc7f27573d9f0934b14d879b943b04dd33d4e76be1dd173ab16076a998e6cbbf`). `Duration(count)` adds `setup*1000` picoseconds after ceiling the GEMM duration. `Compute` calls it once for each physical expert on that rank with nonzero quota, serially; idle experts incur no setup.

The existing [fixed configuration](https://github.com/ponedo/ub-test/blob/289abb53132171b0028c8b3bb0b95a5c0f5ae172/experiments/qwen-prefill-token-scaling/fixed-config.json) sets `setup_ns=100`. Thus each nonempty physical expert's duration remains:

`ceil(count × 6HI × 10^6 / (1000 × 500)) + 100,000` picoseconds.

The 100 ns term is per nonempty physical expert, not per assignment. Existing planning=200 ns and reroute=100 ns are separate fixed settings and are unchanged. This verification did not modify simulator compute source or those timing settings.
