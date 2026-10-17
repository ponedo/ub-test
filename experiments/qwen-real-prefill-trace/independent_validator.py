#!/usr/bin/env python3
"""Independent raw/CSV validator. No imports from extraction or statistics code.

Input routing data and exported per-token CSVs must stay private. This script
prints only aggregate validation results. Token IDs in the CSV are row ordinals.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
import random
from pathlib import Path


def reject_duplicates(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError('duplicate JSON object key')
        result[key] = value
    return result


def read_source(path):
    raw = Path(path).read_bytes()
    source = json.loads(raw, object_pairs_hook=reject_duplicates)
    if not isinstance(source, list) or not source:
        raise ValueError('expected nonempty list of records')
    for record_index, record in enumerate(source):
        if not isinstance(record, dict) or set(record) != set(map(str, range(94))):
            raise ValueError('expected exactly layer keys 0..93')
        if list(record) != list(map(str, range(94))):
            raise ValueError('unexpected serialized layer key order')
        lengths = set()
        for rows in record.values():
            if not isinstance(rows, list) or not rows:
                raise ValueError('expected nonempty layer rows')
            lengths.add(len(rows))
            for ids in rows:
                if not isinstance(ids, list) or len(ids) != 8:
                    raise ValueError('expected eight experts')
                if any(type(e) is not int or not 0 <= e < 128 for e in ids):
                    raise ValueError('expert ID must be integer in 0..127')
                if len(set(ids)) != 8:
                    raise ValueError('experts within a row must be distinct')
        if len(lengths) != 1:
            raise ValueError('inconsistent row count across layers')
        # Check shape against the documented convention, not semantic phase proof.
        row_count = next(iter(lengths))
        if (record_index == 0 and row_count <= 1) or (record_index > 0 and row_count != 1):
            raise ValueError('record shape differs from documented prefill/decode convention')
    return raw, source


def independent_metrics(rows):
    frequencies = collections.Counter(e for row in rows for e in row)
    loads = [frequencies[e] for e in range(128)]
    total = sum(loads)
    assert total == len(rows) * 8
    mean = total / 128
    return {
        'assignments': total,
        'active_experts': sum(v > 0 for v in loads),
        'max_load': max(loads),
        'hot1_share': max(loads) / total,
        'hot8_share': sum(sorted(loads, reverse=True)[:8]) / total,
        'jain': total ** 2 / (128 * sum(v ** 2 for v in loads)),
        # Pairwise definition independent of sorted-rank implementation.
        'gini': sum(abs(a-b) for a in loads for b in loads) / (2*128*total),
        'cv': math.sqrt(sum((v-mean)**2 for v in loads)/128)/mean,
    }, loads


def check_exports(source, directory):
    count = 0
    for layer in range(94):
        with (Path(directory) / f'layer_{layer}.csv').open(newline='') as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != ['token_id'] + [f'expert_{i}' for i in range(8)]:
                raise ValueError('unexpected CSV columns')
            exported = list(reader)
        original = source[0][str(layer)]
        if len(exported) != len(original):
            raise ValueError('export row count mismatch')
        for ordinal, (got, expected) in enumerate(zip(exported, original)):
            if int(got['token_id']) != ordinal:
                raise ValueError('row ordinal mismatch')
            if [int(got[f'expert_{i}']) for i in range(8)] != expected:
                raise ValueError('export differs from original expert ordering')
        count += len(exported) * 8
    return count


def check_statistics(source, directory):
    directory = Path(directory)
    # Reproduce the documented existing generator independently of analysis code.
    rng = random.Random(20261016)
    weights = [(e+1)**-1.1 for e in range(128)]
    synthetic = []
    for _ in range(len(source[0]['0'])):
        selected = []
        while len(selected) < 8:
            expert = rng.choices(range(128), weights=weights, k=1)[0]
            if expert not in selected:
                selected.append(expert)
        synthetic.append(selected)
    expected = {}
    for dataset in ('real', 'zipf'):
        for layer in range(94):
            rows = source[0][str(layer)] if dataset == 'real' else synthetic
            metrics, counts = independent_metrics(rows)
            metrics.update(tokens=len(rows), mean=len(rows)*8/128,
                           max=metrics.pop('max_load'))
            metrics['max_mean'] = metrics['max']/metrics['mean']
            expected[dataset,layer] = metrics, counts
    seen = set()
    with (directory/'layer-statistics.csv').open(newline='') as handle:
        for row in csv.DictReader(handle):
            key = row['dataset'], int(row['layer'])
            if key in seen or key not in expected:
                raise ValueError('duplicate or unexpected statistics key')
            seen.add(key)
            for field, value in expected[key][0].items():
                if not math.isclose(float(row[field]), value, rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError(f'statistics mismatch {key}: {field}')
    if seen != set(expected):
        raise ValueError('missing statistics rows')
    seen_counts = set()
    with (directory/'expert-counts.csv').open(newline='') as handle:
        for row in csv.DictReader(handle):
            key = row['dataset'], int(row['layer'])
            expert = int(row['expert'])
            triple = (*key, expert)
            if triple in seen_counts or key not in expected or not 0 <= expert < 128:
                raise ValueError('invalid expert-count key')
            seen_counts.add(triple)
            if int(row['count']) != expected[key][1][expert]:
                raise ValueError('expert-count mismatch')
    if len(seen_counts) != 188*128:
        raise ValueError('missing expert-count rows')
    histograms = {}
    with (directory/'count-histograms.csv').open(newline='') as handle:
        for row in csv.DictReader(handle):
            key = row['dataset'], int(row['layer'])
            value = int(row['assignment_count'])
            if key not in expected or value in histograms.setdefault(key, {}):
                raise ValueError('invalid histogram key')
            histograms[key][value] = int(row['expert_count'])
    if set(histograms) != set(expected):
        raise ValueError('missing histograms')
    for key, histogram in histograms.items():
        if histogram != dict(collections.Counter(expected[key][1])):
            raise ValueError('histogram mismatch')
    return {'metric_rows': len(seen), 'expert_count_rows': len(seen_counts),
            'histograms': len(histograms), 'zipf_seed': 20261016, 'zipf_alpha': 1.1}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--exports', type=Path)
    parser.add_argument('--stats', type=Path)
    args = parser.parse_args()
    raw, source = read_source(args.input)
    summary = {
        'sha256': hashlib.sha256(raw).hexdigest(),
        'git_blob_sha1': hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest(),
        'bytes': len(raw), 'records': len(source), 'layers_per_record': 94,
        'first_record_rows_per_layer': len(source[0]['0']),
        'remaining_record_row_count_set': sorted({len(r['0']) for r in source[1:]}),
        'first_record_assignments': sum(len(rows)*8 for rows in source[0].values()),
        'prefix_compatibility': {str(n): len(source[0]['0']) >= n for n in (256,512,1024)},
    }
    if args.exports:
        summary['export_assignments_exactly_verified'] = check_exports(source, args.exports)
    if args.stats:
        summary['independent_statistics_verified'] = check_statistics(source, args.stats)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
