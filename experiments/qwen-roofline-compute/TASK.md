# Expert Compute Roofline
Authorized task: user message Sentinel_42d154f7d87c819184eabfcd46a61da7, 2026-10-20.
Base ef1ec5c801ab854363b6382a2af9aa5237ade4c8. Original dot host, fresh restored checkout.
Only compute duration and read-only evidence/configuration change. No Planner, routing, network, protocol or scheduler change.
Models: legacy exact accepted calculation; roofline max(F/100 TFLOPS, B/2692 decimal GB/s), launch zero, m=0 zero.
Activation assumption: three separate GEMMs, fused SiLU/mul, no inter-GEMM on-chip cache; BF16 2m(3H+6I). FP8 weights 3HI read once per nonempty invocation from resident HBM; no cross-invocation cache. Excludes network DMA traffic.
Guard: 6 GiB process-tree RSS, 7 GiB address space, host reserve max(20% visible RAM,4 GiB), disk8GiB/tmp2GiB, runtime4800s per real case (previous longest2773s; bounded 1.73x margin), logicalpayload8GiB/tasks1e6. No concurrent build tasks.

2026-10-20 19:54 UTC user override (Sentinel_8dc6a1d3e3188191aa0ade2bec2aa137): host available-memory reserve is now 1 GiB, superseding both the original 4 GiB/20% floor. Per-case6GiB, address-space, disk, time, payload and WQE guards remain unchanged. Already running native-j2 build retains its earlier stricter4GiB floor; subsequent stages use1GiB.
