#!/usr/bin/env python3
"""Shared, read-only comparisons for the tiered logging experiment."""
import csv
import hashlib
import json
from pathlib import Path

INPUTS = ('input.txt', 'config.json', 'plan.json', 'assignments.csv',
          'transfers.csv', 'graph-input.txt', 'weight-edges.csv')
MODES = ('summary', 'events', 'debug')
VOLATILE = frozenset(('log_level', 'verification_wall_ns'))
JSON_OUTPUTS = frozenset(('online-summary.json', 'validation.json', 'simulator-metrics.json', 'input-summary.json'))
RAW_PAYLOADS = frozenset(('received-payloads.bin', 'payload-index.csv'))
TRACE_NAMES = frozenset(('events.csv', 'ta-identity.csv', 'executed-transfers.csv'))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def stable(value):
    """Exclude only documented instrumentation fields, at any nesting level."""
    if isinstance(value, dict):
        return {k: stable(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [stable(x) for x in value]
    return value


def differences(left, right, prefix=''):
    if isinstance(left, dict) and isinstance(right, dict):
        result = []
        for key in sorted(left.keys() | right.keys()):
            path = prefix + '.' + key if prefix else key
            if key not in left or key not in right:
                result.append(path)
            else:
                result.extend(differences(left[key], right[key], path))
        return result
    return [] if left == right else [prefix or '<root>']


def account_files(sizes):
    """Classify measured files; metadata/input copies are separate from logs."""
    buckets = {'inputs': 0, 'input_metadata': 0, 'summary_json': 0,
               'application_events': 0, 'native_traces': 0,
               'raw_payloads': 0, 'other_outputs': 0}
    files = {}
    for relative, size in sorted(sizes.items()):
        item = Path(relative)
        if relative in INPUTS:
            category = 'inputs'
        elif relative == 'input-summary.json':
            category = 'input_metadata'
        elif relative in JSON_OUTPUTS:
            category = 'summary_json'
        elif relative == 'events.csv':
            category = 'application_events'
        elif relative in RAW_PAYLOADS:
            category = 'raw_payloads'
        elif relative in TRACE_NAMES or item.suffix in ('.tr', '.pcap') or 'trace' in relative.lower():
            category = 'native_traces'
        else:
            category = 'other_outputs'
        buckets[category] += size
        files[relative] = {'bytes': size, 'category': category}
    return {'accounting_version': 2, 'total_bytes': sum(buckets.values()),
            'generated_bytes': sum(buckets.values()) - buckets['inputs'] - buckets['input_metadata'],
            'categories': buckets, 'files': files}


def size_breakdown(path):
    path = Path(path)
    return account_files({item.relative_to(path).as_posix(): item.stat().st_size
                          for item in path.rglob('*') if item.is_file()})


def event_evidence(path):
    """Independent event counts and first/last times, streaming the CSV."""
    timeline, stages, count = {}, {}, 0
    with Path(path).open() as handle:
        for row in csv.DictReader(handle):
            count += 1
            time = int(row['time_ps'])
            event, stage = row['event'], int(row['stage'])
            bounds = timeline.setdefault(event, [time, time, 0])
            bounds[0], bounds[1], bounds[2] = min(bounds[0], time), max(bounds[1], time), bounds[2] + 1
            bounds = stages.setdefault((event, stage), [time, time, 0])
            bounds[0], bounds[1], bounds[2] = min(bounds[0], time), max(bounds[1], time), bounds[2] + 1
    spans = {}
    for name, stage, end in [('dispatch', 0, 'data_ready'), ('combine', 1, 'data_ready')]:
        if ('send', stage) in stages:
            start, finish = stages[('send', stage)][0], stages[(end, stage)][1]
            spans[name] = [start, finish, finish - start]
    if 'compute_start' in timeline:
        start, finish = timeline['compute_start'][0], timeline['compute_end'][1]
        spans['compute'] = [start, finish, finish - start]
    return {'row_count': count, 'timeline': timeline, 'stage_spans': spans}


def host_compact(value, resource_path):
    fields = ('status', 'returncode', 'guard', 'wall_seconds', 'user_cpu_seconds',
              'system_cpu_seconds', 'peak_rss_kib', 'sampled_peak_tree_rss_bytes',
              'max_observed_threads_per_process', 'limits')
    result = {key: value[key] for key in fields}
    result['cpu_seconds'] = value['user_cpu_seconds'] + value['system_cpu_seconds']
    result['resource_path'] = str(resource_path)
    return result
