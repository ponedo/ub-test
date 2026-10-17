#!/usr/bin/env python3
"""Bounded, private, same-serialized-layer offline composition; not joint routing.

Manifest: {phase_documentation: <dataset-card URL/reference>, requests: [
 {request_id, dataset_path, revision, expected_blob_sha, file_path}, ...]}.
Request IDs are declared filename identities, never embedded identity claims.
Only explicitly supplied files are opened. No download, simulation, or publication.
"""
import argparse
import collections
import csv
import hashlib
import gzip
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'experiments/qwen-real-prefill-trace'
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
validator = module('baseline_independent', BASE / 'independent_validator.py')
extract = module('baseline_extract', BASE / 'extract.py')
PREFIXES = (256, 512, 1024, 2048, 4096)
FIELDS = ['request_id', 'token_ordinal'] + [f'expert_{i}' for i in range(8)]


def manifest_read(path):
    manifest = json.loads(Path(path).read_text(), object_pairs_hook=validator.reject_duplicates)
    if not isinstance(manifest.get('phase_documentation'), str) or not manifest['phase_documentation'].strip():
        raise ValueError('phase_documentation reference is required; shape alone is not phase proof')
    requests = manifest.get('requests')
    if not isinstance(requests, list) or not requests:
        raise ValueError('nonempty explicit requests required')
    ids, paths, blobs, datasets = set(), set(), set(), set()
    for req in requests:
        for field in ('request_id', 'dataset_path', 'revision', 'expected_blob_sha', 'file_path'):
            if not isinstance(req.get(field), str) or not req[field].strip():
                raise ValueError(f'missing manifest field {field}')
        for field, size in [('revision', 40), ('expected_blob_sha', 40)]:
            if len(req[field]) != size or any(c not in '0123456789abcdef' for c in req[field]):
                raise ValueError(f'{field} must be exact lowercase 40-character Git SHA')
        path = str(Path(req['file_path']).resolve())
        identity = (req['dataset_path'], req['revision'])
        for value, seen in [(req['request_id'], ids), (path, paths), (req['expected_blob_sha'], blobs), (identity, datasets)]:
            if value in seen:
                raise ValueError('duplicate request/source identity; token repetition forbidden')
            seen.add(value)
    return manifest


def check_private(path):
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        raise ValueError('private paths must be outside the experiment Git working tree')
    return path


def guard(directory, additional, cap, reserve):
    used = sum(p.stat().st_size for p in directory.rglob('*') if p.is_file()) if directory.exists() else 0
    parent = directory
    while not parent.exists():
        parent = parent.parent
    if used + additional > cap or shutil.disk_usage(parent).free - additional < reserve:
        raise ValueError('private-byte/disk guard exceeded before creation')


def compress_aggregate(path):
    """Deterministic lossless packaging, verified before replacing plaintext."""
    path = Path(path)
    raw = path.read_bytes()
    target = path.with_suffix(path.suffix+'.gz')
    if target.exists():
        raise ValueError('refusing to overwrite existing compressed aggregate')
    with target.open('wb') as output:
        with gzip.GzipFile(filename='', mode='wb', fileobj=output, mtime=0) as zipped:
            zipped.write(raw)
    with gzip.open(target, 'rb') as handle:
        if handle.read() != raw:
            raise ValueError('gzip decompression readback mismatch')
    proof = dict(file=target.name, uncompressed_bytes=len(raw),
                 uncompressed_sha256=hashlib.sha256(raw).hexdigest(),
                 compressed_bytes=target.stat().st_size,
                 compressed_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    path.unlink()
    return proof


def verify_batch_rows(exported, expected, total):
    if exported != expected or len(exported) != total:
        raise ValueError('batch readback cross-layer/order/boundary mismatch')
    if len({(row[0], row[1]) for row in exported}) != total:
        raise ValueError('duplicate request/token in batch')


def counts(rows):
    c = collections.Counter(e for row in rows for e in row)
    return [c[e] for e in range(128)]


def independent_counts_metrics(loads):
    total = sum(loads)
    mean = total / 128
    import math
    return dict(assignments=total, mean=mean, max=max(loads), max_mean=max(loads)/mean,
                jain=total*total/(128*sum(v*v for v in loads)),
                gini=sum(abs(a-b) for a in loads for b in loads)/(256*total),
                cv=math.sqrt(sum((v-mean)**2 for v in loads)/128)/mean,
                hot1_share=max(loads)/total, hot8_share=sum(sorted(loads)[-8:])/total,
                active_experts=sum(v>0 for v in loads))


def run(manifest_path, private, stats, max_input_bytes=256*1024**2, private_cap=8*1024**3, reserve=8*1024**3, export_layers=(0,)):
    import math
    if not export_layers or len(set(export_layers)) != len(export_layers) or any(type(x) is not int or not 0 <= x < 94 for x in export_layers):
        raise ValueError('explicit unique serialized export layers in 0..93 required')
    manifest = manifest_read(manifest_path)
    private = check_private(private)
    for req in manifest['requests']:
        check_private(req['file_path'])
        if Path(req['file_path']).stat().st_size > max_input_bytes:
            raise ValueError('input exceeds explicit per-request memory/read bound')
    if private.exists():
        raise ValueError('private output must be new; refusing stale/overwritten exports')
    stats = Path(stats)
    if stats.exists() and any(stats.iterdir()):
        raise ValueError('statistics output must be empty')
    # Conservative source-byte upper bound: each input token costs >= 16 bytes.
    source_bytes = sum(Path(r['file_path']).stat().st_size for r in manifest['requests'])
    max_id = max(len(r['request_id'].encode()) for r in manifest['requests'])
    planned = source_bytes * (max_id + 160) * len(export_layers) // (94*16) + 4096*len(export_layers)*(max_id+160) + 64*1024**2
    guard(private, planned, private_cap, reserve)
    private.mkdir(parents=True)
    stats.mkdir(parents=True, exist_ok=True)
    batch = private/'batch'; batch.mkdir()
    for layer in export_layers:
        with (batch/f'layer_{layer}.csv').open('w', newline='') as f:
            csv.writer(f).writerow(FIELDS)
    aggregates = {}
    boundaries = []
    total = 0
    prefix_counts = {(n,layer): [0]*128 for n in PREFIXES for layer in range(94)}
    def save(label, dataset, layer, rows):
        aggregates[label, dataset, layer] = (len(rows), counts(rows))
    for index, req in enumerate(manifest['requests']):
        guard(private, planned-sum(p.stat().st_size for p in private.rglob('*') if p.is_file()), private_cap, reserve)
        raw, source = validator.read_source(req['file_path'])
        # Two independent parsers; baseline code is unchanged.
        extract.parse(raw)
        blob = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        identity = 'raw Git blob'
        if blob != req['expected_blob_sha']:
            pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{hashlib.sha256(raw).hexdigest()}\nsize {len(raw)}\n'.encode()
            pointer_blob = hashlib.sha1(f'blob {len(pointer)}\0'.encode()+pointer).hexdigest()
            if pointer_blob != req['expected_blob_sha']:
                raise ValueError('source blob mismatch (raw and canonical LFS pointer)')
            identity = 'canonical LFS pointer reconstructed from actual content SHA256 and bytes'
        n = len(source[0]['0'])
        take = min(n, max(0, 4096-total))
        directory = private/f'request_{index:04d}'; directory.mkdir()
        for layer in range(94):
            rows = source[0][str(layer)]
            save(f'request_{index:04d}', 'real', layer, rows)
            for prefix in PREFIXES:
                if n >= prefix:
                    save(f'request_{index:04d}_prefix_{prefix}', 'real', layer, rows[:prefix])
            for prefix in PREFIXES:
                contribution = counts(rows[:min(take, max(0, prefix-total))])
                prefix_counts[prefix,layer] = [a+b for a,b in zip(prefix_counts[prefix,layer], contribution)]
            if layer not in export_layers:
                continue
            dest = directory/f'layer_{layer}.csv'
            with dest.open('w', newline='') as f:
                writer = csv.writer(f); writer.writerow(FIELDS)
                writer.writerows([req['request_id'], t, *row] for t,row in enumerate(rows))
            with dest.open(newline='') as f:
                reader = csv.reader(f)
                if next(reader) != FIELDS: raise ValueError('CSV header mismatch')
                for ordinal, expected in enumerate(rows):
                    if next(reader, None) != [req['request_id'], str(ordinal), *map(str, expected)]:
                        raise ValueError('request readback order/content mismatch')
                if next(reader, None) is not None: raise ValueError('extra exported token')
            with (batch/f'layer_{layer}.csv').open('a', newline='') as f:
                csv.writer(f).writerows([req['request_id'], t, *row] for t,row in enumerate(rows[:take]))
        boundaries.append(dict(request_id=req['request_id'], dataset_path=req['dataset_path'], revision=req['revision'], expected_blob_sha=req['expected_blob_sha'], actual_content_git_blob=blob, identity_verification=identity, source_sha256=hashlib.sha256(raw).hexdigest(), source_bytes=len(raw), first_record_tokens=n, prefix_availability={str(p): n>=p for p in PREFIXES}, remaining_single_token_records=len(source)-1, batch_start=total, batch_stop=total+take, source_ordinal_start=0, selected_tokens=take, truncated=0<take<n))
        total += take
        del source, raw
    for n in PREFIXES:
        if total >= n:
            for layer in range(94):
                aggregates[f'batch_prefix_{n}', 'real', layer] = n, prefix_counts[n,layer]
    # Independently validate batch identity, boundaries and order. Never infer layer.
    for layer in export_layers:
        with (batch/f'layer_{layer}.csv').open(newline='') as f:
            reader = csv.reader(f)
            if next(reader) != FIELDS: raise ValueError('batch header mismatch')
            exported = list(reader)
        expected = []
        for index, bound in enumerate(boundaries):
            with (private/f'request_{index:04d}'/f'layer_{layer}.csv').open(newline='') as f:
                request_rows = csv.reader(f); next(request_rows)
                for ordinal, row in enumerate(request_rows):
                    if ordinal >= bound['selected_tokens']: break
                    expected.append(row)
        verify_batch_rows(exported, expected, total)
        rows = [[int(e) for e in row[2:]] for row in exported]
        for n in PREFIXES:
            if total >= n and counts(rows[:n]) != prefix_counts[n,layer]:
                raise ValueError('batch prefix count readback mismatch')
    # Run existing exact generator once per distinct matched N; erase its private
    # temporary files after aggregate calculation. Zipf never enters real CSVs.
    generator = ROOT/'experiments/prefill-capacity/stage.py'
    controls = {}
    for n in sorted({v[0] for v in aggregates.values()}):
        guard(private, n*128+64*1024**2, private_cap, reserve)
        with tempfile.TemporaryDirectory(dir=private, prefix='zipf_') as tmp:
            subprocess.run([sys.executable, str(generator), 'generate', '--case', tmp, '--assignments', str(n*8)], check=True, stdout=subprocess.DEVNULL)
            control = [r['experts'] for r in json.loads((Path(tmp)/'planner-input.json').read_text())['mapping']]
            # Independent reimplementation checks seeded exact draw ordering.
            import random
            rng = random.Random(20261016)
            weights = [(e+1)**-1.1 for e in range(128)]
            for row in control:
                expected=[]
                while len(expected)<8:
                    expert=rng.choices(range(128), weights=weights, k=1)[0]
                    if expert not in expected: expected.append(expert)
                if row != expected: raise ValueError('seeded Zipf generator mismatch')
            if len(control) != n: raise ValueError('Zipf matched N mismatch')
            controls[n] = counts(control)
    for (label, dataset, layer), (n, values) in list(aggregates.items()):
        aggregates[label, 'zipf', layer] = n, controls[n]
    statrows, countrows, histrows = [], [], []
    for (label, dataset, layer), (n, values) in sorted(aggregates.items()):
        metric = extract.metrics(values)
        independent = independent_counts_metrics(values)
        if sum(values) != n*8 or any(not math.isclose(metric[k], independent[k], rel_tol=1e-12, abs_tol=1e-12) for k in metric):
            raise ValueError('independent aggregate formula mismatch')
        key = dict(selection=label, dataset=dataset, layer=layer)
        statrows.append(dict(**key, tokens=n, **metric))
        countrows.extend(dict(**key, expert=e, count=v) for e,v in enumerate(values))
        histrows.extend(dict(**key, assignment_count=k, expert_count=v) for k,v in sorted(collections.Counter(values).items()))
    outputs = [('layer-statistics.csv', statrows), ('expert-counts.csv', countrows), ('count-histograms.csv', histrows)]
    # These generated aggregate fields contain no quoting characters. Bound all
    # three CSV byte lengths before creating any of them, including final LF.
    stats_bytes = sum(sum(len(str(v).encode()) for v in rows[0]) + len(rows[0]) +
                      sum(sum(len(str(v).encode()) for v in row.values()) + len(row) for row in rows)
                      for _, rows in outputs)
    guard(private, stats_bytes+1024**2, private_cap, reserve)
    packaging = []
    for name, rows in outputs:
        extract.write_csv(stats/name, list(rows[0]), rows)
        with (stats/name).open(newline='') as f:
            got = list(csv.DictReader(f))
        if got != [{k:str(v) for k,v in row.items()} for row in rows]: raise ValueError('aggregate CSV readback mismatch')
        packaging.append(compress_aggregate(stats/name))
    (stats/'aggregate-packaging.json').write_text(json.dumps(packaging, indent=2)+'\n')
    selections = {}
    for n in PREFIXES:
        selections[str(n)] = dict(available=total>=n, selected_tokens=n if total>=n else None, boundaries=[dict(request_id=b['request_id'], source_ordinal_start=0, selected_tokens=min(b['selected_tokens'], max(0,n-b['batch_start']))) for b in boundaries if total>=n and b['batch_start']<n and b['selected_tokens']])
    result = dict(composition='offline concatenation of distinct requests within each identical serialized layer; NOT observed joint-forward routing', phase_status='record 0 interpreted using supplied dataset documentation; no embedded phase proof', phase_documentation=manifest['phase_documentation'], token_identity='zero-based serialized row ordinal; original tokenizer ID unverifiable', layer_identity='exact serialized keys 0..93; model correspondence unverifiable', request_identity='manifest-declared filename identity; embedded identity unverifiable', requests=boundaries, exported_serialized_layers=list(export_layers), aggregate_serialized_layers=list(range(94)), prefixes=selections, batch_tokens=total, bounds=dict(planned_private_bytes_upper_bound=planned, planned_aggregate_csv_bytes=stats_bytes, private_cap_bytes=private_cap, disk_reserve_bytes=reserve, max_input_bytes=max_input_bytes), zipf=dict(alpha=1.1,seed=20261016,generator_sha256=hashlib.sha256(generator.read_bytes()).hexdigest(),matched_N=True), validation='dual raw parsers; source blob; per-request and same-layer batch exact readback; independent metric formulas; aggregate CSV readback', published_data='aggregate counts/statistics only; raw and per-token exports private')
    (private/'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    (stats/'provenance.json').write_text(json.dumps(result, indent=2)+'\n')
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True, type=Path)
    p.add_argument('--private-output', required=True, type=Path)
    p.add_argument('--stats-output', required=True, type=Path)
    p.add_argument('--max-input-bytes', type=int, default=256*1024**2)
    p.add_argument('--private-cap-bytes', type=int, default=8*1024**3)
    p.add_argument('--disk-reserve-bytes', type=int, default=8*1024**3)
    p.add_argument('--export-layers', type=int, nargs='+', default=[0])
    a=p.parse_args()
    result=run(a.manifest,a.private_output,a.stats_output,a.max_input_bytes,a.private_cap_bytes,a.disk_reserve_bytes,tuple(a.export_layers))
    print(json.dumps(dict(batch_tokens=result['batch_tokens'],prefixes=result['prefixes'])))
