# WR results 1.0

`run.json` declares `result_schema: wr-results/1.0`, the input SHA256, policy,
backend profile and explicit identity mappings. This profile has a single source,
one shared 100 Gbps forward link and independent reverse link, pooled RX and
memory service, destination-specific memory, and 1 ps timestamp resolution.
Application sidecars are not consumed. The backend has no MoE-specific logic.

`systemc.wr.csv` has one row per original WR. IDs, sequence, destination and phase
are copied from the validated trace. PSN is actual TP assignment. All timestamps
are integer simulated picoseconds, not wall-clock time:

| Field | Event |
|---|---|
| ready_ps | `ready_ns * 1000`, independent of eligibility/backpressure |
| eligible_ps | first observed ready, dependencies complete, same-Jetty predecessor submitted |
| submit_ps | successful insertion into source FIFO |
| enqueue_ps | admission to scheduler's per-Jetty queue |
| dequeue_ps | scheduler chooses the WR, before its 1 ns processing wait |
| dispatch_ps | scheduler offers WR to downstream FIFO, before any blocked write |
| ordered_ps | WR leaves initiator ordering gate |
| tx_start_ps / tx_end_ps | actual first/last byte serializer service boundary |
| memory_ps | full payload committed after target's 4 ns service |
| complete_ps | successful returned TAACK consumed at source |

`systemc.events.csv` records these events plus byte chunks, request arrival, ACK
serialization and ACK arrival. `jetty` is the original logical Jetty ID; `offset`
is the chunk's **starting** wire offset, `bytes` its length, and `time_ps` its
serialization completion time. The first 64 wire bytes are the experiment's
assumed header. Chunking is serializer granularity, not UB packet segmentation.
No observer advances simulation time. Per-run manifests and metrics preserve
node/Jetty identities; mapped RC numbers are internal adapter details.

## Metrics

`evaluation.analyze` validates per-WR event multiplicities and timestamps,
contiguous actual request/ACK byte chunks, identities, queue accounting and
serialized byte timing before writing `metrics.json`. A failed assertion stops
the experiment. Simulator checks additionally verify every payload byte,
completion, PSN, retirement, dependency, and per-Jetty ordering.

- Makespan: last completion minus earliest ready (does not include the 10 ns
  drain guard or arbitrary leading idle time).
- Payload throughput: `sum(payload_bytes) * 8 / makespan_ns`, in Gbps; includes
  ready/queue waits, headers, startup and completion latency. This is finite-batch
  useful throughput, not steady-state hardware bandwidth.
- P50/P99: linear interpolation at `(N-1)*q`; no nearest-rank rounding. Both
  ready→complete and submit→complete are reported globally and per Jetty.
- Queue wait: submit→dequeue; includes doorbell/ingress/queue backpressure.
  Scheduler wait is enqueue→dequeue; admission wait is ready→submit (dependencies,
  same-Jetty head blocking and source FIFO pressure). No claim of pure contention
  time for the combined queue-wait field.
- Per-Jetty throughput uses the same global makespan denominator, not a different
  active period for each Jetty.
- Byte fairness: Jain index of measured wire or payload byte service in a fixed
  half-open window. Partial chunks are time-overlap prorated from measured
  serialization completion records, at the declared 100 Gbps rate. All active
  Jetties from the trace must have strictly positive scheduler queue occupancy
  throughout the entire window under **every** compared policy. An empty queue,
  including a same-timestamp transient, conservatively invalidates the common
  comparison. Missing eligibility is never interpreted as unfair service.
  Invalid fairness is JSON null / blank CSV, not zero and not a selected subset.
- Synthetic windows remain fixed at 2–6 us to preserve baseline comparisons.
  For MoE-derived batches the initial diagnostic windows (low 2–6 us, high
  100–500 us, skew 50–200 us) proved invalid under FIFO. The final rule selects
  the longest intersection of all-Jetty-positive queue intervals across **all
  three policies**, then rounds inward to integer ns. This uses occupancy alone,
  not byte service or Jain scores; ties choose the earlier interval. Selected
  bounds and the initial diagnostic bounds are saved. If the intersection is
  empty, fairness remains null. The selection is an evaluation procedure, not
  additional simulation or a performance model.

`summary.json`, `summary.csv`, and `per_jetty.csv` use these same definitions for
all generators. Fairness is conditional on the window; short finite batches and
phased/non-backlogged arrivals do not support saturated fairness claims.
