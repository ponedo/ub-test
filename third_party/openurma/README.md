# Upstream attribution

The scheduler overlay derives from `bojieli/OpenURMA`, fixed at the commit in
`UPSTREAM.json`, under Apache-2.0. The original SPDX identifier and comments are
retained. `LICENSE` is the unmodified upstream license. The patch changes bounded
queue admission and adds optional payload-byte DRR. Other OpenURMA source is
fetched on demand rather than vendored. OpenClickNP (also Apache-2.0) is fetched
at its separately fixed commit; its compiler/runtime source is not modified.

New experimental helpers in `experiments/openurma` and `scripts/openurma` are
provided under Apache-2.0. Reports and raw simulation logs describe this local
prototype and do not represent upstream validation or hardware measurements.
