"""Strict CSV WR trace v1.0. Standard library only."""
import csv
import json
import re
from pathlib import Path

VERSION = '1.0'
MAX_INT = 2**63 - 1
FIELDS = ('schema_version', 'wr_id', 'src_node', 'jetty_id', 'dst_node', 'opcode',
          'payload_bytes', 'ready_ns', 'sequence', 'depends_on', 'phase')
INT_FIELDS = ('wr_id', 'src_node', 'jetty_id', 'dst_node', 'payload_bytes', 'ready_ns', 'sequence')


def integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= MAX_INT:
        raise ValueError(f'{name}: expected integer in [{minimum}, {MAX_INT}]')
    return value


def validate(rows):
    seen, sequences, readiness = set(), {}, {}
    previous_time = -1
    payload = 0
    for line, row in enumerate(rows, 2):
        if set(row) != set(FIELDS):
            raise ValueError(f'row {line}: unexpected/missing fields')
        if row['schema_version'] != VERSION or row['opcode'] != 'WRITE':
            raise ValueError(f'row {line}: unsupported version/opcode')
        for field in INT_FIELDS:
            integer(row[field], field, 1 if field == 'payload_bytes' else 0)
        if row['wr_id'] in seen:
            raise ValueError(f'row {line}: duplicate wr_id')
        if row['src_node'] == row['dst_node']:
            raise ValueError('v1 network trace excludes local copies')
        key = row['src_node'], row['jetty_id']
        if row['sequence'] != sequences.get(key, 0):
            raise ValueError(f'{key}: sequence must start at zero and be contiguous in file order')
        if row['ready_ns'] < max(previous_time, readiness.get(key, 0)):
            raise ValueError('ready_ns must be globally nondecreasing')
        deps = row['depends_on']
        if not isinstance(deps, list) or any(type(d) is not int for d in deps):
            raise ValueError('depends_on must be integer IDs')
        if len(set(deps)) != len(deps) or any(d not in seen for d in deps):
            raise ValueError('dependencies must be distinct earlier rows (no forward/missing/cyclic edges)')
        if not isinstance(row['phase'], str) or not re.fullmatch(r'[A-Za-z0-9_.-]{0,64}', row['phase']):
            raise ValueError('phase must be an optional ASCII label up to 64 characters')
        seen.add(row['wr_id'])
        sequences[key] = row['sequence'] + 1
        readiness[key] = previous_time = row['ready_ns']
        payload += row['payload_bytes']
    return {'wr_count': len(seen), 'active_jetties': len(sequences), 'payload_bytes': payload}


def make_wr(wr_id, src, jetty, dst, size, ready, sequence, phase=''):
    return dict(zip(FIELDS, (VERSION, wr_id, src, jetty, dst, 'WRITE', size, ready,
                            sequence, [], phase)))


def write_trace(path, rows):
    validate(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, 'depends_on': ';'.join(map(str, row['depends_on']))})


def read_trace(path):
    with Path(path).open(newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != list(FIELDS):
            raise ValueError('exact v1 CSV header required (unknown fields are rejected)')
        rows = []
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError('malformed CSV row')
            for field in INT_FIELDS:
                if not re.fullmatch(r'0|[1-9][0-9]*', row[field]):
                    raise ValueError(f'{field}: canonical unsigned decimal required')
                row[field] = int(row[field])
            raw = row['depends_on']
            if raw and not re.fullmatch(r'(0|[1-9][0-9]*)(;(0|[1-9][0-9]*))*', raw):
                raise ValueError('invalid dependency encoding')
            row['depends_on'] = [] if not raw else list(map(int, raw.split(';')))
            rows.append(row)
    validate(rows)
    return rows


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False) + '\n', encoding='utf-8')


def canonicalize(pairs):
    """Stable time merge; retain generator's tie order, assign global IDs."""
    pairs.sort(key=lambda item: item[0]['ready_ns'])
    for wr_id, (row, metadata) in enumerate(pairs):
        row['wr_id'] = wr_id
        if metadata is not None:
            metadata['wr_id'] = wr_id
    return [x[0] for x in pairs], [x[1] for x in pairs if x[1] is not None]
