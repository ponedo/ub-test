# window-1024-chunk-streaming

Status: pending.

Strategy: chunk-streaming; link: 3136 Gbps; TA window: 1024;
allocator: original. Changed variable: jetty_ta_window.

Topology, workload, Planner, trace, routing, transport, roofline compute and
observability follow experiment-plan.md without any other intervention.

Prediction: Reduced explicit full-window eligibility intervals may improve MC-minus-Chunk weight delta.
Falsification: No predicted interval reduction or no MC-minus-Chunk improvement.

Private output directory: ablation-private/real-3136/window-1024-chunk-streaming.
Required artifact and checkpoint contract: matrix.yaml and experiment-plan.md.
