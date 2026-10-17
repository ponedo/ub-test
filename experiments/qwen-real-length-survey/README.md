# Bounded real-request offline composition

`offline_batch.py` accepts an explicit, private manifest of selected local files;
it does not enumerate or download a dataset. Raw traces and token-level CSVs stay
outside this experiment repository. The dataset redistribution license has not
been established, so only original scripts and aggregate results belong here.

## Interpretation

- Each source is checked by both unchanged baseline parsers: exactly 94 ordered
  serialized layer keys, eight distinct integer experts in 0..127 per token,
  consistent first-record N, and singleton later records.
- Record zero follows the dataset-card prefill convention. There is no embedded
  phase label, tokenizer token identity, or verified original model-layer mapping.
- Request IDs are manifest/filename identities; CSV token ordinals are zero-based
  serialized row positions. Expert-selection order is preserved without sorting.
- Offline batches concatenate different requests **within the same serialized
  layer**. They are not an observed joint forward pass, batching experiment,
  simulator result, or measured performance result. Decode records and synthetic
  Zipf tokens never enter real batches. Duplicate request/source identities fail.
- Requested batch sizes are 256, 512, 1024, 2048, 4096. A prefix is emitted only
  when enough actual tokens exist; provenance records every request boundary and
  a final partial-request prefix, where applicable. Full-request aggregates and
  available per-request prefixes are also included.

## Reproduction

Supply a private JSON manifest with `phase_documentation` and ordered `requests`.
Each request requires `request_id`, `dataset_path`, exact 40-character `revision`,
`expected_blob_sha`, and explicit local `file_path`. Source verification accepts
an exact raw Git blob or the exact canonical Git-LFS pointer blob reconstructed
from actual content SHA256 and byte length. No credential is part of the manifest.

```sh
python experiments/qwen-real-length-survey/offline_batch.py \
  --manifest /PRIVATE/length-survey-manifest.json \
  --private-output /PRIVATE/new-offline-batch \
  --stats-output experiments/qwen-real-length-survey/results \
  --export-layers 0
```

Output directories must be new/empty. The default per-input read bound is 256MiB;
only one request is loaded at a time. A conservative export-space check precedes
creation, the default free-disk reserve is 8GiB, and additional checks precede each
request, temporary generator output, and aggregate writing. Aggregate CSV byte
lengths are bounded before creation. The private-output cap is 8GiB. Inputs are
never copied. Only requested layers get private per-token exports (layer 0 by
default); all 94 layers get aggregate analysis. Use explicit layer choices rather
than exporting every layer unnecessarily.

## Results and validation

`results/layer-statistics.csv.gz` reports assignments, mean/max load, max/mean, Jain,
Gini, population CV, hot1/hot8 shares, and active expert counts. Companion files
contain expert counts and count histograms. `selection` distinguishes complete
requests, single-request prefixes, and offline-batch prefixes. Request indices
follow `provenance.json` order; no request token data is embedded in provenance.

For each distinct N, the existing `prefill-capacity/stage.py generate` path runs
with seed 20261016 and alpha 1.1. Its weighted draws reject repeated experts within
a token and preserve draw order. An independent implementation checks every
synthetic draw sequence. Synthetic controls are temporary/private and never mix
with real composition. The same matched-N control is reused across layers.

Validation includes dual raw parsing, raw/LFS content identity, exact selected-
layer CSV readback, identical-layer request/batch readback, boundary and duplicate
checks, independent pairwise Gini/Jain/CV formulas, and aggregate CSV readback.

```sh
cd experiments/qwen-real-length-survey
python -m unittest -v test_offline_batch
```

Tests are explicitly synthetic fixtures, never evidence of authentic routing
statistics. They cover malformed and missing metadata, duplicate JSON keys,
missing/reordered layers, malformed experts, decode shape, source duplication,
bad hashes, allocation guard, bad selected layers, exact boundaries, cross-layer
and order tampering, duplicate tokens, and independent metric definitions.

## Recorded bounded run

The eight distinct authenticated source files contain first-record lengths
22, 224, 393, 924, 832, 691, 597, and 592 (4,275 total). The largest single
request is N=924: single-request prefixes 256/512 are supported, while 1024,
2048, and 4096 are unavailable for every individual request. All five requested
offline-composition prefixes are supported. The 4096 selection takes the first
413 of the final request's 592 rows after the first seven complete requests.

Private exports comprise only serialized layer 0: each complete request and one
4096-row offline batch. Smaller batch exports are logically represented by the
recorded prefix and boundary selections; they are not duplicated on disk. Public
aggregate analysis covers all 94 serialized layers. Raw files are not copied.
Uncompressed aggregate CSVs total 26,980,992 bytes and match their exact pre-write size bound;
private output totals approximately 0.51MiB including provenance and directories.

For serialized layer 0 at offline N=4096, real max/mean is 3.4570, Jain 0.67688,
Gini 0.36483, CV 0.69092, and hot8 share 17.95%. The matched Zipf control has
max/mean 14.4258, Jain 0.21551, Gini 0.61985, CV 1.90790, and hot8 share 45.00%.
These are measurements of this selected sample and layer, not population claims.
Real max/mean rises from 2.5234 at N=2048 to 3.4570 at N=4096 as the request mix
changes: increasing offline N does not imply monotonic load smoothing.

## Lossless public packaging

The three CSVs are stored as deterministic `.csv.gz` files (2,570,588 bytes
combined), preserving every row, layer, selection, field, and numeric spelling.
`aggregate-packaging.json` records compressed and uncompressed SHA256 and sizes.
Each gzip is decompressed and compared byte-for-byte before plaintext removal.
The pipeline performs this packaging automatically after CSV readback; no raw
source analysis needs to be rerun just to compress existing results.

```python
import csv, gzip
with gzip.open('results/layer-statistics.csv.gz', 'rt', newline='') as f:
    rows = list(csv.DictReader(f))
```

The independent `review_aggregates.py` validator supports either CSV or gzip;
`results/independent-review.json` records its authentic-data verification.
