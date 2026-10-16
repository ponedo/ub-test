# Native shared-Jetty capability probe

Compiled and executed against both the original and indexed native builds. The native capability gate fails in both; see the observed failure and retained raw events below.

`shared-jetty-probe.cc` is a standalone ns-3 application. Its two nodes, direct link, routes, paired RTPs and single sender Jetty follow `ub-target-execution-test.cc` and its node fixture. It uses production `CreateWqe`, `SubmitWqe`, explicit packet payloads, target executor and sender callback paths. It neither changes native code nor models an independent transport.

## Cases and prediction

Default `concurrentmulti`: submit IDs 1001, 1002, 1003 in the same simulator event before simulation advances, on Jetty 3, ORDER_NO. Each has four 1024-byte fragments and a 32-byte tail. Target completions are delayed by 50–70 us according to payload identity. ID 9001 is submitted at 200 us using the same Jetty. No whole-WQE serialization is introduced. `--delayedLastNs` optionally delays the last initial submission, while the other initial submissions remain concurrent.

Controls: `--mode=single` has one multi-segment WQE and no late WQE; `--mode=onesegment` has the same concurrent-plus-late pattern with one segment each. Count defaults to 3 and applies to initial concurrent WQEs only. This is an application capability test, not a throughput benchmark.

The falsifiable requirement is that every accepted WQE receives exactly one correctly identified sender callback after all its target bytes and all target completions, with no mixed ownership. The known contiguous-SSN WQE completion assumption can violate this for interleaved WQEs. A failure is evidence to retain, not permission to patch the protocol.

## Oracle and artifacts

Every fragment's explicit payload starts with a 16-byte little-endian record: magic, WQE ID, absolute byte offset, fragment length. The remainder is a deterministic WQE-and-offset-specific pattern. Target verification decodes this record, validates task identity and boundaries, compares every byte against the prepared payload, and marks independently located byte coverage. Neither SSN times segment size nor SSN minus start determines payload location.

The send trace records SSN-to-WQE ownership; target receipt verifies it, rejects duplicate fragment offsets and validates native request metadata. Callbacks validate Jetty/WQE identity, exact-once count, all byte coverage and delayed execution count. End checks require every expected fragment and callback, peak outstanding >1 for concurrent modes, sndUna == sndNxt and no active WQE/idle Jetty.

`PREFIX-events.csv` is flushed after every event and failure, preserving native abort evidence. `PREFIX-summary.txt` starts with `INCOMPLETE_OR_NATIVE_ABORT` before native setup and becomes PASS or FAIL only after final checks. A native crash must remain failed/incomplete even if no final oracle check ran. Preserve stderr and exit status for each invocation. Completion counters are incremented immediately before invoking the native target completion callback, so zero-time native synchronous execution is not incorrectly considered early.

## Separate ABI-matched builds (lead only)

Use old checkout headers with frozen A libraries and indexed checkout headers with frozen B libraries. Never compile once and reuse that executable across A/B: UbTransaction layout changed. These commands build only the standalone application and do not rebuild native libraries.

```sh
# Set SRC to the absolute shared-jetty-probe.cc path; set OUT to evidence directory.
# Set FROZEN_A and FROZEN_B to the verified frozen library directories (ending /lib).
# Set A_ROOT and B_ROOT to baseline and indexed native checkout directories.
mkdir -p "$OUT"
c++ -std=c++20 -O2 -g "$SRC" -I"$A_ROOT/build/include" \
  -L"$FROZEN_A" -Wl,--disable-new-dtags -Wl,-rpath,"$FROZEN_A" \
  -lns3.44-unified-bus -lns3.44-network -lns3.44-core \
  -o "$OUT/shared-jetty-A"
c++ -std=c++20 -O2 -g "$SRC" -I"$B_ROOT/build/include" \
  -L"$FROZEN_B" -Wl,--disable-new-dtags -Wl,-rpath,"$FROZEN_B" \
  -lns3.44-unified-bus -lns3.44-network -lns3.44-core \
  -o "$OUT/shared-jetty-B"
# Run sequentially, retaining nonzero status rather than stopping the whole matrix.
# Verify ldd resolves every libns3 dependency to the intended frozen side first.
for side in A B; do
  for mode in single onesegment concurrentmulti; do
    prefix="$OUT/${side}-${mode}"
    "$OUT/shared-jetty-$side" --mode="$mode" --output="$prefix" >"$prefix.stdout" 2>"$prefix.stderr"
    echo "$?" >"$prefix.exit"
  done
done
```

If invoking under `set -e`, wrap each run in `if ...; then rc=0; else rc=$?; fi` and save `rc`, so all failures remain in the evidence matrix. A further bounded overlap case is `--mode=concurrentmulti --lateNs=25000`, with the late WQE entering before delayed completions. An optional staggered-submission case is `--delayedLastNs=20000`. Neither is a repair or a replacement for the default simultaneous case.

## Native contract and observed failure

The checked-in evidence/shared-jetty files are actual A/B execution data. Both controls pass. Both concurrent multi-segment cases fail: WQE 1001 owns SSNs 0,3,6,9,12; its sender callback is at 70,309 ns, before target completion for SSN 9 at 70,335 ns. All payload bytes ultimately validate and callbacks are exactly once; no payload loss was observed.

This violates the native WRITE contract: `ub-transaction-rules.cc` requires a response; `ShouldCompleteOnTpAck` refuses transport-ACK-only success, and `ub-transaction.cc` creates the TA response only after the target done callback. Source analysis identifies interleaved SSNs versus `UbJetty::IsWqeCompleted` contiguous-range assumptions, followed by terminal cleanup of still-outstanding segments. The intermediate UNA advancement is inferred from source, not separately measured. Final UNA==NXT is insufficient proof of genuine ACK reclamation because terminal cleanup also marks outstanding sequence bits.

Task 2 pair mapping is stopped. No native completion changes or whole-WQE serialization were made. Run `run-shared-jetty.sh` with the documented A_ROOT, B_ROOT, FROZEN_A, FROZEN_B and a new OUT directory to reproduce the known failure. Its overall success means the expected original failure reproduced, not that shared-Jetty capability passed.
