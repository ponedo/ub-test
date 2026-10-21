# window-1024-multicast-v2

Status: pending.

Strategy: multicast-v2; link: 3136 Gbps; TA window: 1024;
allocator: original. Changed variable: jetty_ta_window.

Topology, workload, Planner, trace, routing, transport, roofline compute and
observability follow experiment-plan.md without any other intervention.

Prediction: Reduced explicit full-window eligibility intervals may improve MC-minus-Chunk weight delta.
Falsification: No predicted interval reduction or no MC-minus-Chunk improvement.

Private output directory: ablation-private/real-3136/window-1024-multicast-v2.
Required artifact and checkpoint contract: matrix.yaml and experiment-plan.md.
