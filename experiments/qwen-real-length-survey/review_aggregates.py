#!/usr/bin/env python3
"""Independent authentic-data readback; emits aggregate proof only, never raw rows.

No imports from the producer or its validator. Inputs must be explicit local paths.
Reads one raw request at a time; generates no routing exports or network requests.
"""
import argparse
import collections
import csv
import hashlib
import gzip
import json
import math
import random
from pathlib import Path

PREFIXES = (256, 512, 1024, 2048, 4096)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_bytes(), object_pairs_hook=unique_object)


def histogram(rows):
    c = collections.Counter(e for row in rows for e in row)
    return [c[e] for e in range(128)]


def metrics(load):
    total = sum(load)
    mean = total / 128
    return dict(tokens=total//8, assignments=total, mean=mean, max=max(load),
                max_mean=max(load)/mean, active_experts=sum(x > 0 for x in load),
                hot1_share=max(load)/total, hot8_share=sum(sorted(load)[-8:])/total,
                jain=total**2/(128*sum(x*x for x in load)),
                gini=sum(abs(a-b) for a in load for b in load)/(256*total),
                cv=math.sqrt(sum((x-mean)**2 for x in load)/128)/mean)


def open_aggregate(directory, name):
    path = directory/name
    if path.exists():
        return path.open(newline='')
    return gzip.open(str(path)+'.gz', 'rt', newline='')


def review(manifest_path, stats_path, private_path):
    manifest = read_json(manifest_path)
    stats_path, private_path = Path(stats_path), Path(private_path)
    provenance = read_json(stats_path/'provenance.json')
    assert manifest['phase_documentation'] == provenance['phase_documentation']
    assert provenance['aggregate_serialized_layers'] == list(range(94))
    exported_layers = provenance['exported_serialized_layers']
    assert exported_layers and len(set(exported_layers)) == len(exported_layers)
    assert all(type(x) is int and 0 <= x < 94 for x in exported_layers)
    assert len(manifest['requests']) == len(provenance['requests'])
    expected = {}
    batch = {layer: [] for layer in range(94)}
    expected_export = {layer: [] for layer in exported_layers}
    ids, hashes, identities = set(), set(), set()
    lengths = []
    for index, (request, bound) in enumerate(zip(manifest['requests'], provenance['requests'])):
        raw = Path(request['file_path']).read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        blob = hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest()
        pointer = f'version https://git-lfs.github.com/spec/v1\noid sha256:{sha}\nsize {len(raw)}\n'.encode()
        pointer_blob = hashlib.sha1(f'blob {len(pointer)}\0'.encode()+pointer).hexdigest()
        assert request['expected_blob_sha'] in (blob, pointer_blob)
        assert sha == bound['source_sha256'] and blob == bound['actual_content_git_blob']
        assert len(raw) == bound['source_bytes']
        for field in ('request_id', 'dataset_path', 'revision', 'expected_blob_sha'):
            assert request[field] == bound[field]
        identity = (request['dataset_path'], request['revision'])
        assert request['request_id'] not in ids and sha not in hashes and identity not in identities
        ids.add(request['request_id']); hashes.add(sha); identities.add(identity)
        data = json.loads(raw, object_pairs_hook=unique_object)
        assert isinstance(data, list) and data
        for ri, record in enumerate(data):
            assert isinstance(record, dict) and list(record) == list(map(str, range(94)))
            ns = set()
            for rows in record.values():
                assert isinstance(rows, list) and rows
                ns.add(len(rows))
                for row in rows:
                    assert isinstance(row, list) and len(row) == 8
                    assert all(type(e) is int and 0 <= e < 128 for e in row)
                    assert len(set(row)) == 8
            assert len(ns) == 1
            assert (ri == 0 and next(iter(ns)) > 1) or (ri > 0 and ns == {1})
        n = len(data[0]['0']); lengths.append(n)
        start = len(batch[0]); take = min(n, max(0,4096-start))
        assert (bound['first_record_tokens'],bound['batch_start'],bound['batch_stop'],bound['selected_tokens']) == (n,start,start+take,take)
        assert bound['source_ordinal_start'] == 0 and bound['remaining_single_token_records'] == len(data)-1
        assert bound['truncated'] == (0 < take < n)
        assert bound['prefix_availability'] == {str(p):n >= p for p in PREFIXES}
        for layer in range(94):
            rows = data[0][str(layer)]
            label = f'request_{index:04d}'
            expected[label,'real',layer] = histogram(rows)
            for prefix in PREFIXES:
                if n >= prefix:
                    expected[f'{label}_prefix_{prefix}','real',layer] = histogram(rows[:prefix])
            batch[layer].extend(rows[:take])
            if layer in exported_layers:
                target = [[request['request_id'], str(t), *map(str,row)] for t,row in enumerate(rows)]
                with (private_path/f'request_{index:04d}'/f'layer_{layer}.csv').open(newline='') as f:
                    read = list(csv.reader(f))
                assert read[0] == ['request_id','token_ordinal'] + [f'expert_{i}' for i in range(8)]
                assert read[1:] == target
                expected_export[layer].extend(target[:take])
        del data, raw
    total = len(batch[0])
    assert total == provenance['batch_tokens'] == min(sum(lengths),4096)
    for layer in exported_layers:
        with (private_path/'batch'/f'layer_{layer}.csv').open(newline='') as f:
            rows = list(csv.reader(f))
        assert rows[0] == ['request_id','token_ordinal'] + [f'expert_{i}' for i in range(8)]
        assert rows[1:] == expected_export[layer]
        assert len(set(tuple(row[:2]) for row in rows[1:])) == total
    for prefix in PREFIXES:
        p = provenance['prefixes'][str(prefix)]
        assert p['available'] == (total >= prefix)
        assert p['selected_tokens'] == (prefix if total >= prefix else None)
        boundaries = []; offset = 0
        if total >= prefix:
            for req,n in zip(manifest['requests'], lengths):
                take = min(n, max(0,prefix-offset))
                if take: boundaries.append(dict(request_id=req['request_id'],source_ordinal_start=0,selected_tokens=take))
                offset += n
        assert p['boundaries'] == boundaries
        if total >= prefix:
            for layer in range(94):
                expected[f'batch_prefix_{prefix}','real',layer] = histogram(batch[layer][:prefix])
    del batch
    controls = {}
    for n in sorted({sum(v)//8 for v in expected.values()}):
        rng = random.Random(20261016)
        weights = [(e+1)**-1.1 for e in range(128)]
        rows=[]
        for _ in range(n):
            row=[]
            while len(row)<8:
                e=rng.choices(range(128),weights=weights,k=1)[0]
                if e not in row: row.append(e)
            rows.append(row)
        controls[n] = histogram(rows)
    for (label,_,layer),load in list(expected.items()):
        expected[label,'zipf',layer] = controls[sum(load)//8]
    def key(row): return row['selection'],row['dataset'],int(row['layer'])
    seen=set()
    with open_aggregate(stats_path, 'layer-statistics.csv') as f:
        for row in csv.DictReader(f):
            k=key(row); assert k in expected and k not in seen; seen.add(k)
            for field,value in metrics(expected[k]).items():
                assert math.isclose(float(row[field]),value,rel_tol=1e-12,abs_tol=1e-12), (k,field)
    assert seen == set(expected)
    seen=set()
    with open_aggregate(stats_path, 'expert-counts.csv') as f:
        for row in csv.DictReader(f):
            k=key(row); e=int(row['expert']); triple=(*k,e)
            assert k in expected and 0<=e<128 and triple not in seen; seen.add(triple)
            assert int(row['count']) == expected[k][e]
    assert len(seen)==len(expected)*128
    got={}
    with open_aggregate(stats_path, 'count-histograms.csv') as f:
        for row in csv.DictReader(f):
            k=key(row); load=int(row['assignment_count'])
            assert k in expected and load not in got.setdefault(k,{})
            got[k][load]=int(row['expert_count'])
    assert set(got)==set(expected)
    assert all(got[k]==dict(collections.Counter(load)) for k,load in expected.items())
    return dict(status='PASS', distinct_sources=len(lengths), source_token_lengths=lengths,
                total_source_tokens=sum(lengths), batch_tokens=total, serialized_layers=94,
                exported_serialized_layers=exported_layers, statistics_rows=len(expected),
                expert_count_rows=len(seen), selections_per_dataset=len(expected)//188,
                checks='independent raw shape, duplicate content, hashes, layer-specific counts, all metrics, histograms, seeded Zipf, exact selected-layer exports, boundaries and row uniqueness',
                provenance_sha256=hashlib.sha256((stats_path/'provenance.json').read_bytes()).hexdigest(),
                reviewer_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--stats',required=True);p.add_argument('--private',required=True)
    a=p.parse_args();print(json.dumps(review(a.manifest,a.stats,a.private),indent=2))
