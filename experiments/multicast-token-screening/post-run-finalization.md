# Post-run documentation finalization

Formal execution finished with exactly two PASS N256 cases and independent
read-only result review. Only publication copies of README.md and run-ledger.md
are finalized after the run; correctness-gates.json, input-identities.json and
source-provenance.json are newly derived sanitized evidence summaries.

The original frozen harness, native/runtime sources, binaries, cached sources,
prepared cases, private ledger and receipts are not edited or rerun. All frozen
identities were verified again while creating these documentation copies.
Runtime and executable harness Python hashes in source-provenance.json identify
the exact executed versions. Post-run administrative documents are not presented
as preregistered execution inputs.

Published material excludes private paths, raw source records, token routing,
assignments, payloads, host/PID/namespace details, raw rings, complete diagnostic
logs and large private identity maps. Only bounded aggregate facts and hashes are
included. The final read-only review is distinct from the preflight review;
correctness-gates.json labels the two explicitly.
