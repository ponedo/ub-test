# Remote verification receipt

- Repository: `ponedo/ub-test`.
- Delivery branch: `experiments/chunk-streaming-multicast-dot-20261021`.
- Accepted parent: `3a33cc6a249667fc46bf02ac0fed4e1127d7c1ab`.
- Verified content commit: `90740eab1b4cb5d947ac02921a5f10e37289206c`.
- Verified content tree: `0c8d19c2af20937bc4df9275d1ae36d4a9994b75`.
- Verification date: 2026-10-21 UTC.

## Checks completed before receipt commit

The complete remote recursive tree was retrieved without truncation. Every one of the 76 delivered content files matched its local Git blob SHA and byte size (1036255 bytes total). All 11013 accepted baseline blobs remained unchanged. There were no unexpected additions outside `experiments/chunk-streaming-multicast/`.

The final delivery commit adds only this receipt to the verified content commit. The final branch tip and all 77 files are independently checked after branch creation; the final commit SHA is provided in the delivery message rather than embedded recursively in its own content.

## Scientific and engineering evidence

The formal N256 campaign is PASS with exactly three new simulations (NoBal, Direct, CS+MC) and two strictly verified reused controls (CS, MC). All five logical outputs agree. The prior staged Phase B evidence retains its caught defects and posthoc ACK-oracle correction. A separate clean reproduction entrypoint also passed all 50 newly executed small simulations, with no imported results or formal reruns.

Native sources and loaded libraries were unchanged. No restricted routing trace, per-token private data, raw payload or full Debug trace is included. Reports explicitly distinguish simulated time, host cost, observed correlations, low per-hop merge coverage and pending batched credit returns.

See [REPORT.md](REPORT.md), [fresh reproduction receipt](results/phase-b/fresh-reproduction-receipt.json), [independent review](final-independent-review.json), [five-strategy results](five-strategy-results.csv), and [native provenance](NATIVE-PATCH.md).

Automated GitHub CI is not claimed as PASS based on an absence of checks. Experiment checks are the explicit locally executed and independently reviewed evidence above.
