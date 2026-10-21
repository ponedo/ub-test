# Phase B: fixed bounded correctness matrix

This manifest is declared before building or running the candidate. No timing or
performance result is a pass criterion. `fixtures.py` is the executable source
of the manifest, `phase_b.py prepare` binds actual input/topology identities, and
`phase_b.py execute` requires the parent's exact manifest approval. A missing
merge, path, offset transition, or native-window witness stops admission; an
eligible graph alone never establishes runtime coverage. No native source or
accepted controls are edited.

## Minimal workload set

Ten inputs, 16–200 synthetic tokens, ten normal executions plus duplicate-ready
and stale-grant controls, five native fault executions, nine rejection tests,
and 12 paired old-mode comparisons: 50 simulator executions total. Small input
reuse avoids a token-size or performance sweep. The accepted four strategies
are NoBal, Direct, CS and MC; NoBal remains main-only and is not assigned the
balanced plan.

| ID | Input | Main required evidence |
|---|---|---|
| B01 | 4 ranks, 32 tokens, zero slots | Zero weight groups; full layer completes |
| B02 | 4 ranks, 16 tokens | Singleton ordinary native WRITE, zero envelope |
| B03 | 4 ranks, 32 tokens, adaptive relay | Unchanged whole-expert Direct fallback, actual fanout 3 envelope |
| B04 | 8 ranks, 64 tokens | Stage I fanout 2; two Stage II relays/fanout 2; real both-hop envelopes and physical streaming |
| B05 | B04 + 20 us service delay at relay 1 | Own relay ready strictly before other parent; unchanged all-main GroupChunk release |
| B06 | 8 ranks, two hot experts, 128 tokens | Concurrent experts, exact separate expert/chunk groups |
| B07 | 4 ranks, 32 tokens, dimensions 65×129×3 | Matrix-exact bytes; interior shard cut 33540; chunk 2000 and segment 333 tails |
| B08 | 4 ranks, 32 tokens, 20 us chunk-0 completion delay | Reordered target completion callbacks, not packet OOO |
| B09 | 20 ranks, 200 tokens, unchanged default relay policy | Sixteen replicas; natural Stage I fixed fanout-4 path |
| B10 | 8 ranks, 64 tokens, 1,082,369 weight bytes | 1058 chunks, >1024 lifetime groups, native TA window stays 512, actual saturation and safe cleanup |
| B11 | B04 + duplicate-notify | Benign duplicate coverage notification, exact baseline summary/CSV parity |
| B12 | B04 + invalidateGrant | Native GrantRejected count at injected source exceeds B04, with safe subsequent progress |

B10 has 64 tokens, not 512/1024/2048 tokens. Its fixed chunk count stresses the
native 512-TA window and lifetime resource reuse together; it is not a window
parameter scan. B05 is a barrier test, not a physical-streaming claim: service
delay can make the whole expert physically arrive before the callback releases
chunk zero.

The static expected topology must actually be generated before admission. In
particular, B09's planner produces sixteen replicas; the unchanged default
rule selects four relays, giving a real four-member Stage I envelope opportunity.
No force/max-relay parameter is changed to manufacture fanout four. If a fixture no longer produces its declared graph, preparation fails;
there is no post-hoc relabeling or silent adjustment.

## Native loss and duplicate evidence

F01 drops the final original native WRITE TA of one Stage I child; F02 does the
same on Stage II. F03 drops its tail TPACK; F04 drops the reverse TAACK/Response
for a Stage II tail; F05 duplicates a Stage II native tail delivery. Each uses
the existing post-ingress-accounting delivery fault seam (return multiplicity
0, 1 or 2), a role/task-bound target, native GBN with its accepted fixed RTO and
attempt limit, and bounded Events. No source-envelope drop is simulated.

The two WRITE tests require the lost original PSN to be retried as ordinary
native unicast, and validate every retry against its original TP/PSN/SSN/task/length,
source TX → switch RX → switch TX → intended target RX, with no other-pair
retries. A chunk-tail loss may still replay a legitimate native GBN suffix from
later chunks on that reused pair; one retry packet is not assumed. F04 requires the repeated reverse TAACK's
actual physical path, even when that target has no hybrid source proxy and the
hybrid proxy retry counter stays zero. TPACK loss can be repaired by native
retry or a later cumulative ACK; the checker does not invent an extra retry.
Group completion and TP-safe drain are distinct checks.

N01–N09 exercise actual byte corruption, relay-buffer corruption, early relay,
local-ready-but-other-relay-pending GroupChunk, premature final expert ready,
premature target ready, early sender completion, duplicate sender completion
and duplicate forwarding. Each requires the declared invariant error, an
unsuccessful exit, and no false PASS artifact. Relay-buffer corruption alone
may reach the exact adapter payload-equality SIGABRT invariant before the target
validator; only that named invariant is admitted, never a generic SIGABRT. Resource kills and unrelated
crashes are not successful rejections. Core dumps are disabled.

## Offset mixing and physical streaming

Every bounded Events run independently partitions every original member byte
from `hybrid-events.csv`: full fixed-group envelope or that member's native
first-send, exactly once. Retries do not advance that partition. Envelope
sequence is contiguous over actual envelopes, not computed from byte offset.
The overall gate additionally requires a real group with native-first → later
merge and a real envelope → native → envelope group. Pure fabricated trace
unit tests validate the checker but do not satisfy these live coverage keys.
If natural fixtures do not exercise these transitions, Phase B is INCOMPLETE;
add a separately reviewed native micro fixture, never a wait/partial collection
or fake completion in production.

The streaming witness requires:

Relay chunk-0 physical RX ≤ target usable-ready ≤ all-main GroupChunk ready ≤
actual downstream source TX < relay's final physical full-expert RX.

The witness identifies expert, relay physical ID, group, exact chunk and native
packet range. Source native-pop or Submit timestamps alone are insufficient.
Every actual envelope is also joined to source TX/switch RX and each restored
native branch's switch TX/target RX. Native packet routes join on actual UID,
PSN/task and port identities, not four unrelated aggregate timestamps.

## Regression and verifier self-tests

Zero, B04 and B07 are run under each original strategy using both the exact
accepted `token-screen-private/build/layer` (SHA256
`27b3eae2b2aa7cd3c932359261c410238ae53beb4a752ca0d1e62e225befc85b`)
and the candidate with its original default transport. The loaded native
library closure must match byte-for-byte. All accepted deterministic summary
fields and physical/timeline/compute CSV outputs are compared exactly; only
host wall/CPU/RSS and verification host timing are omitted. NoBal and balanced
strategies each retain their own correct plan; controls are never rewritten to
force parity.

The genuine successful B04 output is copied before verifier mutations. Missing
or duplicate members, wrong expert/range/source, missing member bytes, delayed
native submission, premature completion, false safe state, leaked association,
and packet/wire-count corruptions must be rejected. These tests are explicitly
labeled mutated evidence, not runtime fault coverage. Actual raw byte
corruption is exercised by live N01/N02; Summary has no full payload dump.

`test_hybrid_contracts.py` is pure Python: imports, fixed manifests, existing
read-only accepted graph fixtures, independent GroupChunk reconstruction,
metadata/byte-identity mutations, real-trace checker contracts, physical-route
joins, approval/no-resume gates and syntax. It starts no compiler, standalone
graph executable or simulator. Passing it is only Phase B0 evidence.

## Guard and stopping rules

Every child is sequential and uses the accepted resource guard: 6 GiB tree RSS,
7 GiB address space, 4800 seconds maximum per case, at least 1 GiB host available,
8 GiB free output disk and 2 GiB free `/tmp`. Admission reserves 7 GiB available
memory. Output is Summary except small witness/fault/rejection cases using
bounded Events (combined hybrid event/physical cap 131072); no raw Debug. Global
Jetty completeness, per-pair safe native state, CBFC conservation, switch drain,
full online payload validation and token/combine correctness remain mandatory.

A successful explicitly approved startup prefix pauses with INCOMPLETE status.
Continuing requires a new approval with approved_to_continue=true, the exact
prior ledger SHA256, and the next ordered row_ids. It does not rerun prior rows.
A stopped/failed manifest cannot resume or auto-rerun. The parent must review a new
frozen manifest for any new attempt. Final `phase-b.json` is PASS only with all
rows and all 14 coverage categories. `old-mode-regression.json` independently
records all 12 paired comparisons. Both are admission artifacts, not authority
to run formal N256.

## Honest limitations

Not exercised: native TA wire-SSN wrap (the fixed pressure fixture has about
1058 TAs per pair, not 65536). This is not represented as a PASS.

Unsupported: native packet out-of-order injection, persistent-loss recovery or
graceful exhaustion, source-envelope loss, lost CBFC credits, Selective/CC, and
multi-switch reliability. Completion callback reordering and feedback loss do
not get relabeled as unsupported native packet OOO. No full debug, arbitrary
performance sweep, native-window change, larger real-token experiment, or
protocol modification is introduced.
