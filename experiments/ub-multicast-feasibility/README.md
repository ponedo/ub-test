# UB multicast feasibility audit

Start with [REPORT.md](REPORT.md). This is a documentation-only, source-based feasibility audit. It does not implement or benchmark multicast.

## Deliverables

- REPORT.md: conclusion, source versions, evidence boundaries.
- NETWORK_SWITCH_AUDIT.md: actual switch routing/queue/credit/port/link call paths and Packet copying.
- TRANSPORT_JETTY_AUDIT.md: WQE/TA/TP/Jetty identities, ACK versus Response, patched completion, failure and cleanup gaps.
- DESIGN_OPTIONS.md: preconfigured groups, packet-carried destinations, dynamic control-plane install, costs, two distinct PoC designs, specification limits.
- CALL_PATHS.md: actual call diagrams and clearly marked proposed paths.
- CHANGE_SCOPE_AND_GATES.md: expected files/functions, regression targets, risks and Go/No-Go gates.
- audit_sources.py, verify_anchors.py and evidence/: reproducible read-only checks, bounded search, scoped provenance and validation summaries. Broad source inventories remain private on the cloud host and are not included in this public directory.

## Reproduce without changing or running the simulator

Use the exact native base plus accepted patches documented in evidence/provenance.json. `NATIVE` is the native source tree; `PROJECT` is the UltraEP-on-UB source tree. Output goes to a separate audit directory, never into native source. Python 3 standard library only.

```sh
python audit_sources.py --native "$NATIVE" --project "$PROJECT" --out /tmp/ub-audit-before
python verify_anchors.py --native "$NATIVE" --out /tmp/ub-audit-anchors.json
# Perform read-only source inspection.
python audit_sources.py --native "$NATIVE" --project "$PROJECT" --out /tmp/ub-audit-after --compare /tmp/ub-audit-before/source-manifest.json
```

The locally retained snapshots capture 119 native files and 195 protected project source/script/patch files. The two broad source-manifest.json inventories (including path/hash lists and tracked-change details) are excluded from this public release. Public evidence includes their comparison outcome and scope counts, not their full contents. Native inventory covers `src/unified-bus` source/doc extensions plus Packet and COW headers and assertion definition. Project inventory excludes this newly created documentation directory, .git, build directories and caches. It covers available reconstructed source files, not missing files from an arbitrary full repository checkout. The before/after comparison proves unchanged bytes during the captured interval, not all earlier historical activity. The five recorded accepted-patch source hashes also match the existing published recovery provenance.

`evidence/before/bounded-search.json` contains one lexical hit: a generic ns-3 Packet UID broadcast comment. There are zero such matches in the examined UB module. Neither negative grep nor this generic comment establishes UB specification capability. Actual positive call-path inspection is the evidence for current single-output and single-target behavior.

`evidence/source-anchor-checks.json` records 20 checked function/text anchors at cited line ranges. This verifies location/existence only, not every semantic conclusion or all possible runtime behavior. The private source SHA256 inventories pin the audited files, including supporting COW/assertion headers. Public evidence/provenance.json retains only the scoped accepted-patch source identities already pertinent to this audit. Reproduction creates inventories locally; do not automatically publish those outputs.

## Validation actually performed

- Read-only source inventory and bounded lexical search.
- Exact-file SHA256 comparison against accepted recovered native snapshots.
- 20 concrete source-anchor checks.
- Before/after native and protected-project source equality.
- Independent review of switch credit accounting, endpoint matching, ACK/Response separation, completion order, assertions, and artifact scope.

No multicast simulation, compilation, protocol mutation, UltraEP parameter changes or performance sweep occurred. Future test lists are explicitly unexecuted.

## UNKNOWN and limits

- Existing real UB hardware multicast forwarding, group tables, programming latency and reliable multicast protocol are not established by this simulator audit.
- The user-supplied UB Base Specification 2.0.1 §8.6 fused-operation example contains multicast as a functional composition; it does not specify the required switch-native replication/ACK design. See DESIGN_OPTIONS.md for exact source/version/page and the PDF hash/public-link limitation. The PDF is not redistributed.
- End-to-end network replication, dynamic membership, bounded target failure, retry exhaustion, parallel simulation safety and performance need implementation and tests.
- A packet COW copy is not an ASIC copying latency model. Packet tags are not counted wire bytes. Group/control setup has no measured cost here.
- Existing target-error/timeout behavior is not assumed to provide an adequate all-target terminal failure contract.

No private Router Trace, Payload, prompt, access credential or original restricted dataset is included. The public deliverable consists of documents, analysis scripts and small source provenance/search evidence. Publication requires an independent branch, remote Commit SHA and file-completeness verification.
