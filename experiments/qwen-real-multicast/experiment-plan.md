# Real Qwen multicast comparison (preregistered 2026-10-19)

Question: Does accepted multicast improve weight delivery and layer latency versus Chunk Streaming at N2048?
Control: No Balancing; treatments: Direct, Chunk Streaming, Multicast. This compares complete implemented mechanisms, including dedicated multicast child endpoints versus Pair Jetty weight endpoints, not replication alone.
Fixed: 8 audited requests and identical same-layer prefix N2048, L37 then L0 then L52; EP64, H4096/I1536, 128 experts/top8, ideal FP8 18 MiB/expert, BF16 activation, 500 effective GFLOP/s, main e//2/source t%64, 100Gbps/20ns single switch, TA1024/chunk4096, accepted planner/relay parameters. Summary and full online/independent validation.
Prediction: multicast reduces main-source repeated payload for fanout>1; weight and layer benefit is uncertain because envelopes, feedback and endpoint sharing differ. Falsification: no source savings, slower weight or layer completion, correctness mismatch, or resource stop.
Evidence: actual per-strategy summary, native packets/queue/credit counters, graph fanout, inputs/source hashes, preflight/postflight, host resources. Never infer timing from host runtime or missing runs.
Gate: all three static capacity audits first; L37 four strategies fully pass before L0/L52. Stop on any unexpected protocol/resource/correctness failure. Reuse old results only with established equivalence and metric coverage; otherwise rerun accepted current executable.
Limits: each Preparation/Preflight/Simulator/Postflight 3600s, RSS6GiB, AS7GiB, disk8GiB, tmp2GiB, available1.5GiB. No limit changes.
Artifact contract: publish scripts, aggregate CSV/charts/report, small evidence only. Raw routing/config/mapping and complete payload stay private. No protocol or planner changes.
