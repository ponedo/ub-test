# Configuration correction and evidence separation

The intended small validation target is 3136 Gbps with 20 ns link delay. The first 52 simulator executions used 100 Gbps. That configuration error invalidates their use as evidence for the intended bandwidth target, not their recorded outcomes at 100 Gbps. The mistake is in the experiment setup, not a demonstrated candidate runtime defect.

Those observations are preserved separately and withdrawn from target publication. Their performance signs, coverage percentages, hold totals, fault paths, and ACK witnesses must not be transferred to 3136 Gbps. In particular, the earlier Stage II coverage gain is not the target result.

Fresh target executions use the same binaries and fixed 5 ns candidate policy. Only the network bandwidth configuration is corrected; the remaining fixture conditions are unchanged, including V08's artificial 200 µs weight-completion delay. No parameter tuning or larger experiment is part of this correction.

All CSVs in this target-analysis directory are newly extracted from the 3136 Gbps outputs. Case and arm IDs identify evidence without machine-specific paths. Missing or unexercised witnesses remain explicit and cannot be replaced by the earlier 100 Gbps evidence.
