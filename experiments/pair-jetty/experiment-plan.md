# Pair Jetty controlled implementation

Baseline: accepted native 2fde39d02920e639f5b200d0c5262a517326deb8 (index and both completion fixes), application delivery f0e45bcb4a3d57d6a5707d992f45e79c5f80b483. Compare per-WQE versus per-directed-pair Jetty only. Native code, network, routing, payloads, WQE granularity, TA segment size, expert compute and relay dependency graph fixed. No native changes authorized here.

Prediction: pair count bounds Jetty count and reduces ACK-window storage. Shared admission queues/windows can change simulated timing. Falsification: different logical transfer graph or bytes, early target-ready, missing/duplicate callback or native protocol deadlock. Preserve failed cases and stop for new native bugs.

Sequential gates: A manager + concurrent real-network 2–4-node probes, then B No Balancing, then C all weight strategies, then D 5K/10K/20K/50K resource comparisons; 100K only within resource guard. All logs, input hashes, exit statuses, wall/CPU/RSS, counters and verifier results preserved. Legacy native/app regression controls retained. No simultaneous benchmarks. Limit run wall 300 seconds, process-tree RSS 6 GiB, address space 7 GiB, host available memory 1.5 GiB minimum, output disk free 8 GiB minimum, /tmp free 2 GiB minimum.
