# 3136 Gbps source audit

## Scope and status

Read-only inspection of the original host snapshots: `multicast-native` at `b8375b51a094d3b1217b697989e1ab979f609e64` and `real-batch-native` at `d6aa9e242d5a93f5bbd1ad54f39b1620c1b8757b`. The audit was then checked against `bandwidth-native`, restored from native base `b8375b51a094d3b1217b697989e1ab979f609e64` with the four accepted patches. The parent reports that all 109 candidate native-file hashes match the accepted project `3c2275eafea79426a441c819c8b65268492ff08e` manifest; its expanded source identity contains 3406 native source entries. References below are relative to this restored `bandwidth-native` tree. DataRate, clock, CBFC, link, and timer files cited here match the originally inspected snapshot; changed port/allocator/switch citations were rechecked.

No source changes, builds, simulations, or runtime tests were performed for this audit. Arithmetic examples are predictions, not measured results.

## Rate and clock precision

`src/network/utils/data-rate.cc:85–88,220–237` parses Gbps into a 64-bit bit rate and computes packet serialization using fixed-point division. The requested rate is 3,136,000,000,000 bits/s, representable without rate overflow. No bandwidth-induced overflow or zero-duration serialization was identified for ordinary bounded, nonempty WRITE, envelope, ACK, or credit packets at picosecond resolution. Their exact generated sizes must still be captured in the bounded tests.

`src/unified-bus/examples/ub-case-runner.cc:1036` and `scratch/network-poc.cc:69` set `Time::PS`. `src/core/model/nstime.h:238` rounds the calculated time to integer ticks. At 3136 Gbps the ideal time in ps is `packet_bytes × 125 / 49`.

| Serialized bytes | Ideal ps | Expected rounded ps |
| ---: | ---: | ---: |
| 1 | 2.551 | 3 |
| 40 | 102.041 | 102 |
| 64 | 163.265 | 163 |
| 160 | 408.163 | 408 |
| 4096 | 10448.980 | 10449 |

These are byte-count examples, not assertions that a WRITE or envelope has a particular size. The 40-byte control-credit packet is established by `model/protocol/ub-datalink.cc:45–53` and `model/protocol/ub-header.h:128` under `src/unified-bus/`.

The alternate `src/unified-bus/examples/ub-mtp-remote-tp-regression.cc:560` sets nanosecond resolution. A 40-byte control-credit frame rounds to zero there at 3136 Gbps. Do not reuse that clock configuration for this experiment.

## Wire time, queues, and allocation

- `src/unified-bus/model/ub-port.cc:807–842`: serialization uses actual packet bytes; egress completion additionally includes interframe gap and optional packet-rate padding.
- `src/unified-bus/model/ub-link.cc:184–200`: delivery is scheduled after serialization plus propagation. `ub-remote-link.cc:46–50` similarly carries a `Time` arrival value.
- `ub-port.cc:515–530`: ordinary port ownership is released at transmit completion before the next transmit trigger.
- `ub-switch-allocator.cc:109–113,187–206`: default allocation latency is 5 ns per scheduling round. This can dominate small-packet serialization at 3136 Gbps. Preserve it and distinguish allocation-limited throughput from wire rate.
- `ub-switch.cc:1364–1378`: control frames enter the ordinary priority-0 VOQ, retaining queue service. Do not replace ordinary sends with `TransmitPacketDetached` (`ub-port.cc:850–874`), which does not reserve ordinary port busy time.

## Wire bytes versus CBFC cells

`src/unified-bus/model/protocol/ub-cbfc.cc:121,234,335` consistently computes the ceiling of serialized packet bytes divided by cell bytes for credit eligibility, consumption, and return. Defaults in `ub-port.cc:271–300` are 20-byte flits, eight flits per cell, and 6553 initial cells. Thus a 160-byte credit cell is an accounting unit, not an instruction to serialize every packet as a multiple of 160 bytes.

CBFC return is threshold/piggyback driven (`ub-cbfc.cc:351–400,431–455,496–519`), rather than a rate-scaled timer. Native-envelope sink handling returns credit for the original serialized packet before delivering reconstructed data (`ub-switch.cc:2054–2065`). Preserve that ordering and one-envelope reservation semantics.

## Timers and observability

- DCQCN pacing computes 64-bit bits and converts seconds to `Time` (`protocol/ub-dcqcn.cc:610–613`); its default control timers remain 50–55 microseconds (`:60,75,80`).
- CAQM defaults to a 500 ns update interval (`protocol/ub-caqm.cc:523`); retransmission base RTO defaults to 25,600 ns (`protocol/ub-retrans.h:312`). Do not rescale these merely to make throughput approach line rate.
- CAQM RTT EWMA converts samples to integer ns (`protocol/ub-caqm.cc:135–145`), losing sub-ns detail in artificial near-zero-propagation cases.
- Legacy packet tags use ns (`ub-port.cc:803,861,889`), as do some branch-wait statistics (`ub-switch.cc:1925,2128`). Equal displayed timestamps are not evidence of zero simulator duration. Prefer existing `time_ps` traces or direct `Time` measurements.

## Initial cross-snapshot check

The inspected DataRate, UbPort, and UbLink files are byte-identical between the two host snapshots. The inspected CBFC differences add diagnostic counters rather than changing credit arithmetic. This is not a claim that the complete projects are identical.

## Minimal proposed validation

1. At PS resolution, assert the parsed rate and positive serialization for the table sizes and the actual generated WRITE/envelope/ACK/control-credit packet sizes; compare against rounded ideal time within one ps.
2. Send back-to-back real packets through ordinary two-node ports. Check advancing transmit completions and receive time equal to send time plus serialization and propagation.
3. Check CBFC boundary sizes 159/160/161 bytes and actual serialized envelopes: expect 1/1/2 cells for those boundary examples and balanced consume/return accounting.
4. Preserve the configured allocator and queues; separate allocation, serialization, propagation, and credit-stall contributions. Do not equate offered link rate with guaranteed application goodput.
5. Optionally add a separate NS negative-control test showing the 40-byte frame rounds to zero, guarding against accidental runner clock regressions.

All validation above is proposed, not executed.

## Restored-source nuance

The restored `ub-port.cc:578` explicitly recognizes WRITE envelopes as DLL data for packet-rate-control classification. The allocator changes include optional adapter commit revalidation with ordinary allocation delay and using the actual released input packet for credit return. These accepted changes do not replace wire serialization or ordinary busy-port service. The new test-only `rate-probe.cc` adds an ordinary egress queue plus actual `UbLink` byte-sink fixture; its completion trace is explicitly labeled an announcement, while next-send and receive times are observed. It does not claim upper-layer ACK/credit restoration coverage. Build/run validation remains the parent’s responsibility.
