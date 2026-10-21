# Scoped F03 oracle correction and continuation

The v3 simulator and independent validator completed F03 successfully, but the
runner stopped because its TPACK recovery oracle incorrectly required the later
cumulative ACK to retain the dropped ACK's task tag. Native ACK generation copies
the triggering packet's tag; sender progress is scoped to the directed TP and
24-bit PSN, not that task. No transport or compiled source is changed here.

`ack_oracle.py` is an additive, read-only checker. The receipt is explicitly bound
to F03's original PSNs 0 through 11 (no wrap), lost task 128 / PSN 9 / TP 9→2,
unique UID-matched four-event physical ingress path, later same-pair ACKs covering
observed original PSNs, and terminal sender UNA=NXT=12 with no unacked packets,
descriptors, timer or active WQEs. It does not accept generic completion/retries
or an unrelated ACK. Per-ACK instantaneous UNA transitions were not selected by
the original diagnostic filter; the receipt does not claim that timestamp.
Synthetic tests validate checker behavior only, including modular arithmetic;
they are not live wrap or runtime evidence.

`phase_b_extension.py prepare` preserves the entire original stopped tree by
hash, imports fourteen original PASS rows and one explicitly posthoc-revalidated
F03 row, and copies only the unexecuted F04-onward inputs into fresh directories.
Commands differ solely in those directory paths. The new manifest binds all
old artifacts, compiled/native identities, new checker, tests, importer, this
document and the exact posthoc receipt. No original verdict is overwritten.

The fresh ledger uses the existing runner's reviewed PAUSED-prefix entry point,
not a resume of the STOPPED ledger. Execution additionally requires explicit
`approved_to_import_prior`, the posthoc receipt hash, the exact new manifest and
initial ledger hashes, and all remaining row IDs. The unchanged original runner
retains resource limits, sequential execution and stop-on-first-failure. Neither
previous successful simulations nor F03 are rerun. Phase C remains unauthorized.
