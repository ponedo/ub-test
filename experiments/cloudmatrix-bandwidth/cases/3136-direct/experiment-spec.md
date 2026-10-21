# 3136-direct

Delivery expansion of the pre-registered common matrix; no new case or changed prediction.

Role: treatment-measured. Same Qwen3 L37, 2048 tokens, EP64, 128 experts, top-k8, H4096, I1536, FP8 weights and BF16 activations. Single switch, 3136 decimal Gbps logical endpoint rate,20ns propagation; compute100TF/s,HBM2692GB/s. Other controls and prediction: ../../experiment-plan.md.

Evidence: ../../results/performance.csv (filter the rate and strategy named above). New unchanged native ns-3 execution with online payload,WQE/TA,TP drain,CBFC,independent network and compute checks. Summary logging, independent simulator clock and private outputs. Only link rate changed.
