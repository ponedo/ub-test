# N256 quick screening plan

Goal: test whether the exact real-token N256 natural layer-37 workload reproduces
the 3136-Gbps Multicast reversal at low measured host cost. Do not search other
token sizes in this round. This is a tested candidate, not a proof of minimum.

Sequence:
1. Verify the exact accepted source/native patch chain and runtime binaries.
2. Retain accepted observer/native-window unit tests and Roofline model oracle;
   run only pure new harness/analyzer contract tests. No new token canary run.
3. Guarded source-prefix validation, shared-plan graph emission and independent
   preflight for Chunk Streaming and Multicast v2.
4. Freeze source, runtime, harness and input identities. Independent read-only
   review binds the prepared manifest and minimal-gate receipts.
5. Root approval admits exactly one sequential formal run per strategy, with
   unchanged resource guard and passive bounded all-node aggregates.
6. Retain full online, graph, network/lifecycle and compute checks; extract only
   aggregate evidence. Stop on the first failure; never rerun automatically.

Conditions, limits and exclusions are in `matrix.json`; exact command templates
are in `command-manifest.json`; endpoint and interpretation rules were frozen in
`preregistered-analysis.md`. Each case has a short specification under `cases/`.
Raw trace, prepared inputs, payloads and bounded rings stay private. Public
delivery contains the harness and sanitized result summaries only.
