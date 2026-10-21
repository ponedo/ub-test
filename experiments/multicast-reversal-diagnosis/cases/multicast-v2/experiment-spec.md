# multicast-v2: passive real diagnostic

Input: immutable bandwidth-private/real-3136/multicast-v2; 3136 Gbps, accepted roofline
compute (100 TFLOPS, 2692 GB/s HBM), topology/routing/Planner/protocol unchanged.
Simulator: diagnostic layer plus separately built diagnostic native libraries.
Observation: diagnostic ON, summary log, bounded recorder.
Success: accepted complete summary except verification_wall_ns and per-expert
compute/weight readiness exactly unchanged; all independent validators PASS.
Artifacts remain private. Per-case wall bound 4800 seconds and accepted guards.
Stop on parity, identity, resource or correctness failure. No intervention.
