# Single-switch network replication PoC

This is a network-only research prototype. A source submits one bitmap-tagged data packet to a native generated-data queue. One configured switch creates shared-payload branch references in its native VOQs; each reference is arbitrated into a finite physical egress queue and sent over a native UB port/link. The recipients consume actual received bytes.

It does **not** implement a multicast WQE, TA, transaction acknowledgment, retransmission, source-side group CQE, member failure recovery, multi-switch routing tree, or UltraEP strategy. Test completion is the observed last target receive time. The metadata is an idealized PacketTag: it contributes **zero** serialized link bytes; the real data-link header and control-credit frames do consume link bandwidth.

## Ownership and bounded resources

- One ingress packet owns one native ingress reservation. Processing/physical-VOQ accounting counts it once.
- The bitmap creates at most 64 descriptors (actual topology excludes sending back to ingress). Branches share immutable input payload, but have distinct destination metadata and output queue references.
- Per-output VOQ backlog counts each logical branch. Native VOQs are input-buffer-backed views, not separate fixed-capacity packet stores. No new infinite payload queue is introduced.
- The parent reservation stays until the last branch moves into physical egress. Each branch is subject to native egress CanEnqueue and independent downstream CBFC.
- Nonfinal branch dequeues suppress upstream return with the existing flow-control context flag. Last dequeue releases the reservation and returns one input packet's rounded credit cells.
- Source injection uses a bounded 1024-packet application queue and a 4096-byte payload ceiling; oversized packets that cannot fit egress are rejected.
- CBFC incoming piggyback is consumed/cleared before replication. CBFC at each receiver returns its branch credit normally.
- Native recovery/transport/congestion-control paths are not used by these headerless network test packets; untagged unicast keeps its original path. Multicast configuration is restricted to CBFC and a single switch.

## Files

- `network-poc.cc`: real-link fixture and runtime assertions.
- `run.py`: protected, sequential positive/negative matrix.
- `verify.py`: independent actual-byte, membership, port and credit checks.
- `test-verifier.py`: validation corruption tests.
- `patches/`: minimal native delta and baseline reconstruction information.
- `results/`: compact CSV/JSON evidence.
- `REPORT.md`: measured results, limits and reproduction commands.

Raw source/received `.bin` files are generated only in the private run directory for independent SHA256 comparison, not published.
