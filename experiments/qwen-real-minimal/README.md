# Real Qwen3-235B routing: minimum single-layer experiment

This experiment uses 256 real routing records from one fixed offline request prefix,
separately at serialized layers 0, 37 and 52. It does not execute Qwen weights or a
serving scheduler. See `REPORT.md`, `model-precision.md` and `fixed-config.json`.

## Required private inputs

The restricted source JSON, request manifest and per-token routing files are **not
redistributed**. Obtain authorized copies of the eight files in the accepted
`experiments/qwen-real-length-survey` source manifest. The manifest records local
paths, dataset revision and expected Git blob/canonical LFS-pointer identity. The
independent audit additionally computes raw-file SHA256 checksums. The frozen aggregate `results/expert-counts.csv.gz`
from that experiment is public; it contains counts, not token routing.

Set paths to your authorized inputs and existing native build:

```sh
REPO=/path/to/ub-test
PRIVATE=/path/outside/repository/real-minimal-private
MANIFEST=/path/to/length-survey-manifest.json
COUNTS=$REPO/experiments/qwen-real-length-survey/results/expert-counts.csv.gz
NATIVE=/path/to/accepted/ns-3-ub
GRAPH=/path/to/accepted/graph-tool
X=$REPO/experiments/qwen-real-minimal
mkdir -p "$PRIVATE/routing"
for L in 0 37 52; do
  python3 "$X/extract_routing.py" --manifest "$MANIFEST" --frozen-counts "$COUNTS" \
    --layer "$L" --tokens 256 --out "$PRIVATE/routing/layer_$L.json" \
    --audit-out "$PRIVATE/source-audit-$L"
done
python3 "$X/build.py" --native "$NATIVE" --out "$PRIVATE/build"
python3 "$X/run.py" --private "$PRIVATE" --binary "$PRIVATE/build/pair-layer" \
  --lib "$NATIVE/build/lib" --graph-tool "$GRAPH" \
  --source-manifest "$MANIFEST" --frozen-counts "$COUNTS"
python3 "$X/collect.py" --private "$PRIVATE" --out "$X/results"
python3 "$X/verify_artifacts.py" --private "$PRIVATE" --out "$X/results/finalized-archive-audit.json"
python3 "$X/analyze.py"
```

The native baseline is `2fde39d02920e639f5b200d0c5262a517326deb8`.
Build provenance records the exact source, binary and library hashes used here.
Python dependencies are the existing project dependencies (`psutil`, plus plotting
packages for analysis); no GPU or model weights are required.

The driver creates new case directories and refuses to overwrite them. It is not
a resume tool. Each Preparation, Preflight, Simulator and Postflight stage has its
own 3600-second limit, 6 GiB process-tree RSS and 7 GiB address-space limits.
Minimum free disk, `/tmp` and available host memory are 8 GiB, 2 GiB and 1.5 GiB.
The first failing case stops the run. Final latency is only emitted for completed
cases passing both online and independent validation.

Completed generated inputs are archived privately with SHA256/readback verification;
original source files remain untouched. Public collection emits only summaries,
counts and hashes. Do not add the private directory, config/plan mapping arrays,
per-token CSV/JSON or generated input.txt files to Git.

## Extraction and compatibility

`extract_routing.py --layer L --tokens N` supports serialized layers 0–93 and a
prefix of 1–4275 unique observed tokens. It preserves request boundaries, ordinal
order and all eight expert IDs. It never pads, duplicates or samples routing.
The performance driver deliberately remains fixed at 256 tokens.

The source audit validates all eight raw requests and all 94 layers, then compares
the fixed 256-token counts to the independently accepted frozen aggregates.
Preparation checks the selected layer, manifest hash and every ordered routing
row against those raw sources. Source NPU = batch token ID modulo 64 is a simulation
assumption. Main expert placement stays expert ID divided by two (integer division).

Existing Zipf generators and interfaces remain available. The only shared adapter
addition is optional `weight_dtype_bytes`; absence retains the previous dtype and
output behavior. This experiment sets it to 1 while activation `dtype_bytes` stays 2.

## Tests

```sh
python3 "$X/test_precision.py"
python3 "$X/test_final_inventory.py"
python3 "$X/test_real_integration.py" --repo "$REPO" --manifest "$MANIFEST" \
  --frozen-counts "$COUNTS" --graph-tool "$GRAPH" --routing-dir "$PRIVATE/routing" \
  --legacy-ref 289abb53132171b0028c8b3bb0b95a5c0f5ae172 \
  --out /path/to/aggregate-test-results.json
```

The legacy reference must be present in the local clone. Local import commits used
by the execution host may differ from published commit IDs; publication provenance
records their tree mapping. Regression scripts also accept existing private old
fixtures; inspect their `--help` for paths. Fault injection, graph coverage and
fresh simulation comparisons are recorded in `results/`.

To repeat the guarded legacy runtime checks with existing authorized fixtures:

```sh
python3 "$X/test_runtime_compatibility.py" --binary "$PRIVATE/build/pair-layer" \
  --lib "$NATIVE/build/lib" --fault-inputs /path/to/tiered-logging/inputs \
  --zipf-input /path/to/accepted/qwen30b-256/no-balancing \
  --out "$PRIVATE/final-runtime-compatibility"
```
