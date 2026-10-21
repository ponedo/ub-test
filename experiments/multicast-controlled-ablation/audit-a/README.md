# A: no-candidate callback suppression audit

**Outcome: UNSUPPORTED_SEMANTIC_PRESERVATION.** The minimal suppression reverses
cross-TP native ACK-queue arbitration order. It does not demonstrate intra-TP
reordering or broken reliability. A is stopped before native runtime modification
or formal workload execution. See [source audit](SOURCE-AUDIT.md).

This is a small scheduler unit counterexample, not a real 3136 Gbps LayerLatency
run. It uses accepted pair proxies and native TP/RR/CBFC paths, 5 ns selected
allocation service, and a 3136 Gbps port setting. Synthetic queued ACK packets
have a real VL7 datalink header. A fault sink prevents physical transmission.

Reproduce with an **unmodified, already-built accepted diagnostic native tree**:

```sh
python3 experiments/multicast-controlled-ablation/audit-a/reproduce.py \
  --native /path/to/accepted-diagnostic-native \
  --out /path/to/new-private-audit-output
```

The script verifies all nine source hashes from the accepted diagnosis manifest
and the accepted proxy hash, compiles this unit only, runs two bounded processes,
checks the exact witness, and verifies native sources/libraries did not change.
It never builds, edits, or patches the native tree. It refuses existing output
paths and outputs inside the native tree. Limits: 2 GiB address space, 128 MiB
per file, no core dumps, 120-second compile timeout, 15 seconds per test.
The optional B instrumentation tree will intentionally fail the accepted-native
manifest check; use a separate immutable accepted diagnostic tree.

Expected exact outputs:

```text
native fc=CBFC link_gbps=3136 allocation_ps=5000 callbacks=3 suppressed=0 commits=A@10000ps,B@25000ps
suppress fc=CBFC link_gbps=3136 allocation_ps=5000 callbacks=2 suppressed=2 commits=B@6000ps,A@11000ps
```

B arrives at 1 ns, A arrives at 2 ns, both after a null selection at 0 ns. Native
holds the 5 ns episode and selects A first; immediate suppression selects B
first. The common late 20 ns wake is an artificial drain stimulus. Only the
first packet is required to falsify order preservation.

The archived result JSON records the exact linked binary/library identities,
source identities, guards, and observed outputs. Its `COUNTEREXAMPLE_CONFIRMED`
audit status does not mean experiment A passed. No A performance value exists.
