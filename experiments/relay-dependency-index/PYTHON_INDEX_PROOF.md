# Python dependency indexes

## Exact predicate derivation

The accepted adapter and independent preflight have two predicates. For a
non-main source and scope 2, select every main-origin weight transfer whose
**destination expert, offset and bytes** equal the consumer's. For other scopes,
select every weight transfer whose **destination physical ID** equals the
consumer's source physical ID. There is no explicit group field in either old
predicate. Adding a selected-relay/group key would incorrectly narrow the
upstream group barrier. Main-origin consumers retain an empty list.

The adapter appends task IDs to two dictionaries while visiting the unchanged
weight-transfer sequence. Its chunk key is `(expert, offset, bytes)` and its
arrival key is destination physical ID. Each consumer gets a fresh copy of its
matching vector. The independent preflight instead enumerates graph-tool edges
and assigns task IDs as `start + edge ordinal`, using nested expert/chunk maps.
It imports neither the adapter nor its index helper, and never derives expected
dependencies from the submitted configuration. Both emit original traversal
order, with duplicates preserved. No sorting, sets, compressed barriers or
single-dependency substitution are used.

For each key, induction over the original traversal shows its vector contains
exactly the prefix elements satisfying the old predicate, in their original
order. At the final prefix it therefore equals the old scan list. List copying
preserves the old absence of cross-consumer mutation aliases. Index construction
is O(N) expected dictionary work; lookup and materialization are O(N + D), where
D is the complete dependency output size. This cannot eliminate the necessary
O(D) materialization.

## Validation retained

All existing preflight checks remain: individual routing/top-k and assignment
identity, all physical quotas, unique rank/expert and physical IDs, main placement,
weight provenance, replica slot budgets, independent UltraEP planner checker,
complete integer input contract, capacity/SSN/task/payload limits, physical order,
graph-tool reconstruction, exact full transfer equality including dependency
order, optional executed CSV byte equality and execution fingerprint. Source and
target, expert/group/chunk membership and coverage follow from this independent
reconstruction and exact full-list comparison; none is replaced by count-only
checks. The graph tool remains the same accepted native graph generator.

## Baselines and tests

Adapter defaults to indexed; select `dependency_mode='scan'` or environment
`RELAY_DEPENDENCY_MODE=scan`. Preflight defaults to indexed; use
`--dependency-mode scan` or the corresponding `check` keyword. Its production
scan branch retains the old transfer scan verbatim. `profile-python.py` runs
preparation and preflight serially, under the accepted 300-second, 6-GiB RSS,
7-GiB address space, 1.5-GiB available memory and 8-GiB free disk guards.

`test-python-indexes.py` includes 160 seeded randomized graphs (80 deliberately
valid with all arrival combinations), empty graphs, mixed scopes, shuffled
ordering, repeated edges, multiple experts, same offsets with different lengths,
missing keys, nonmonotonic adapter task IDs and separate dependency-list ownership.
The two implementations and their scan oracles must agree on every list or on
missing-dependency rejection. Small integration fixtures cover no balancing,
direct, chunk, multiple chunks/TAs and slow-relay settings. Thirteen tamper cases
exercise missing, duplicate and reordered dependencies, wrong barrier membership,
wrong chunk offset/length, source/target, missing/reordered transfers, physical
expert/kind and relay grouping parameters. Existing eight tamper checks also run.

`compare-python-graphs.py` compares the complete accepted fixed256 configuration,
all transfers and ordered dependencies, input bytes, transfer CSV and weight-edge
CSV. It checks the full plan after removing only the existing nonsemantic
`cpu_wall_ns` diagnostic, whose values are reported. It does not remove planner,
routing, physical, quota or order fields. Published equality JSON includes the
complete graph hash, count and unchanged 459-MiB logical weight bytes.

## Final fresh measurements

All four serial profiled processes completed with no guard violation.

| Stage | Scan wall / CPU (s) | Indexed wall / CPU (s) | Dependency scan → index (s) | RSS scan → index (KiB) |
|---|---:|---:|---:|---:|
| preparation | 204.325 / 204.508 | 5.769 / 5.836 | 198.341463 → 0.107977 | 197952 → 197436 |
| preflight | 198.041 / 197.906 | 1.505 / 1.327 | 196.743416 → 0.149680 | 106368 → 111184 |

These are cProfile diagnostic timings with the same statement instrumentation; no claim of unprofiled speedup is made. Whole-process wall speedups are 35.42× preparation and 131.56× preflight. The independent preflight retains complete checks and uses about 4.7 MiB additional peak RSS. Raw profiles/configurations remain local; `python-timings.csv`, `python-statements.csv`, `python-profile-top.csv` and `python-profile-sources.json` provide compact attribution and source provenance.

Fresh scan and indexed preparation both exactly reproduce the accepted fixed256 input, configuration and complete executed graph: 62,232 weight WQEs, 78,336 dependencies, 470,016 weight TAs and 481,296,384 bytes (459 MiB). Canonical graph SHA-256: `0361b47ac43fae9bc05ecd20ba0cc9f7cd2e08d3a01bf6d4d354000933e7322f`; FNV-1a64: `6ada88bf8945a70f`. Both preflight modes independently reproduced the same hashes.
