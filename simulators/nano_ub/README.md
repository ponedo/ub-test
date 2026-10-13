# Generic WR Trace adapter

Run from repository root after building `trace_e2e`:

```sh
python3 -m simulators.nano_ub.run \
  --trace experiments/phase1/output/traces/synthetic_mixed.csv \
  --policy drr --semantics data-write --output-dir /tmp/nano-trace
python3 -m evaluation.analyze /tmp/nano-trace --window-ns 2000 6000
```

The Python adapter validates strict WR Trace 1.0 CSV. It emits a versioned,
strict internal TSV (`input.tsv`), and the C++ backend rechecks mapping, size,
identity, sequence and dependency invariants. C++ reads only generic WRs, never
routes, experts, AIV, tokens, generator internals or application sidecars.

One source is mapped to CNA 1; sorted destinations to CNA 2..; sorted Jetty IDs to
RC 1... Each destination has a separate contiguous byte address space in CSV
order. Address zero may exist at multiple destinations without aliasing. All
original identities and the mapping are recorded. The experimental topology is
one source/multiple Jetty/shared forward link/pooled receiver with isolated target
storage. Destination labels do not imply independent physical links or TP state.

`ready_ns` triggers an exact SystemC timed wake-up. Injection waits for every
listed prior completion and the prior same-Jetty sequence to be submitted.
Independent Jetties can advance while a dependency-blocked Jetty waits. Source
FIFO admission is nonblocking and wake-ups come from read/completion/timed events.
All ready observations are logged even when source FIFO is full. `phase` is an
opaque label, not an implicit barrier. Explicit dependencies use actual returned
completion time. They do not substitute for a transport Fence control.

Generic data-write profile only: a WRITE goes through the existing real UB
Doorbell, fair scheduler, ordering, builders, TP, PSN/retransmit, byte serializer,
parsers, target ordering, memory, completion and returned ACK path. Defaults for
new WRs are RC and no Fence/ODR. Unknown trace fields and non-WR opcodes are
rejected. In particular the Phase1 application-side final-SQE Fence/CQE transport
flags cannot be represented by WR Trace 1.0 and are **not** silently emulated.
Use the old explicit fence/ordering/ROT tests for those experimental paths.

Limits are explicit: one source, ≤1024 active Jetties, ≤60000 WRs (no 16-bit TASSN
wrap), each payload 1..16 MiB, ≤128 MiB total payload, ready horizon ≤1 second.
The C++ watchdog stops at last ready +100 ms if work is lost or blocked. Larger
or unsupported traces fail instead of truncating. A zero-row trace is valid.

`UbMemory.external_write` is opt-in external backing storage **after the original
4 ns memory wait**. The original 1 MiB module storage/default behavior is unchanged.
The experiment stores/copies and checks all bytes and maintains each destination's
bounds; it does not bypass target service or synthesize completion analytically.
See `evaluation/results_schema/README.md` for event/metric definitions and
`docs/phase2/REPORT.md` for limitations and actual measured results.
