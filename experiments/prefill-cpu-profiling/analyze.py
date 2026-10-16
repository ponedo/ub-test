#!/usr/bin/env python3
"""Read-only analysis of completed dot CPU runs; never launches a simulator.

All sample tables, folded stacks, and SVGs count records (one sample = one),
NOT cpu-clock period nanoseconds. Inclusive counts deduplicate recursive frames
within each sample and are limited by captured/unwound stack coverage.
"""
import argparse
import collections
import csv
import html
import json
from pathlib import Path
import re
import struct
import subprocess

HERE = Path(__file__).resolve().parent
DEFAULT_RAW = HERE.parents[2] / 'prefill-cpu-raw'
HEADER = re.compile(r'^\s*(.*?)\s+(\d+)/(\d+)\s+(\d+\.\d+):\s+(\S+):\s*(.*)$')
FRAME = re.compile(r'^\s*([0-9a-fA-F]+)\s+(.*?)\s+\((.*)\)\s*$')
RECORD_NAMES = {1: 'MMAP', 2: 'LOST', 3: 'COMM', 4: 'EXIT', 5: 'THROTTLE',
                6: 'UNTHROTTLE', 7: 'FORK', 8: 'READ', 9: 'SAMPLE', 10: 'MMAP2',
                13: 'LOST_SAMPLES'}


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def write_csv(path, rows, fields):
    with path.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def raw_records(path):
    """Walk standard perf file record headers, without dumping payload bytes."""
    with path.open('rb') as f:
        h = f.read(72)
        if h[:8] != b'PERFILE2':
            raise ValueError('Expected little-endian standard perf.data (PERFILE2)')
        _, header_size, attr_size, attr_off, attr_len, off, length = struct.unpack('<7Q', h[:56])
        if header_size < 72 or off + length > path.stat().st_size:
            raise ValueError('Truncated or malformed perf.data header')
        sample_types = []
        if attr_size >= 32:
            for p in range(attr_off, attr_off + attr_len, attr_size):
                f.seek(p + 24)
                sample_types.append(struct.unpack('<Q', f.read(8))[0])
        counts = collections.Counter()
        lost = 0
        p = off
        while p < off + length:
            f.seek(p)
            hdr = f.read(8)
            if len(hdr) != 8:
                raise ValueError('Truncated record header')
            typ, misc, size = struct.unpack('<IHH', hdr)
            if size < 8 or p + size > off + length:
                raise ValueError(f'Malformed perf record at offset {p}')
            counts[RECORD_NAMES.get(typ, f'TYPE_{typ}')] += 1
            if typ == 2 and size >= 24:
                _, n = struct.unpack('<QQ', f.read(16))
                lost += n
            elif typ == 13 and size >= 16:
                lost += struct.unpack('<Q', f.read(8))[0]
            p += size
    for k in ('SAMPLE', 'LOST', 'LOST_SAMPLES', 'THROTTLE', 'UNTHROTTLE'):
        counts.setdefault(k, 0)
    return {'records': dict(counts), 'lost_samples_reported': lost,
            'sample_type_masks': sample_types,
            'callchain_requested': any(t & (1 << 5) for t in sample_types),
            'user_stack_requested': any(t & (1 << 13) for t in sample_types)}


def parse_frame(text):
    m = FRAME.match(text)
    if not m:
        return None
    ip, sym, dso = m.groups()
    sym = re.sub(r'\+0x[0-9a-fA-F]+(?:/0x[0-9a-fA-F]+)?$', '', sym)
    unknown = sym in ('[unknown]', 'unknown', '') or bool(re.fullmatch(r'(?:0x)?[0-9a-fA-F]+', sym))
    if unknown:
        sym = '[unknown]'
    return {'label': f'{sym} ({dso})', 'unknown': unknown, 'ip': ip}


def parse_samples(lines):
    """Accept perf script's leaf-inline and multi-line callchain layouts."""
    current = None
    for line in lines:
        m = HEADER.match(line)
        if m:
            if current is not None:
                yield current
            comm, pid, tid, timestamp, event, tail = m.groups()
            current = {'comm': comm.strip(), 'pid': int(pid), 'tid': int(tid),
                       'time': timestamp, 'event': event, 'frames': []}
            frame = parse_frame(tail)
            if frame:
                current['frames'].append(frame)
        elif current is not None and line.strip():
            frame = parse_frame(line)
            if frame:
                current['frames'].append(frame)
            elif not line.lstrip().startswith('#'):
                raise ValueError(f'Unexpected perf script frame: {line[:180]!r}')
    if current is not None:
        yield current


def bars(path, rows, title, denominator):
    """Dependency-free, labeled equivalent to a Top20 self/inclusive bar plot."""
    width, left, barwidth, rowheight = 1600, 1060, 390, 30
    height = 110 + max(1, len(rows)) * rowheight
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<g font-family="monospace" font-size="12" fill="#172554">',
           f'<text x="20" y="27" font-size="18">{html.escape(title)}</text>',
           f'<text x="20" y="51">Unit: sample records; denominator: {denominator}; inclusive membership counted once per symbol per sample.</text>']
    maximum = max((r['samples'] for r in rows), default=1) or 1
    for i, row in enumerate(rows):
        y = 80 + i * rowheight
        label = row['symbol']
        short = label if len(label) <= 137 else label[:134] + '...'
        out += [f'<text x="20" y="{y+14}"><title>{html.escape(label)}</title>{html.escape(short)}</text>',
                f'<rect x="{left}" y="{y}" width="{barwidth * row["samples"] / maximum:.2f}" height="20" fill="#2563eb"/>',
                f'<text x="{left+barwidth+10}" y="{y+14}">{row["samples"]} ({row["percent"]:.2f}%)</text>']
    out.append('</g></svg>')
    path.write_text('\n'.join(out) + '\n')


def analyze_perf(data, out, perf, symfs=None):
    out.mkdir(parents=True, exist_ok=True)
    raw = raw_records(data)
    cmd = [str(perf), 'script', '-i', str(data), '--max-stack', '1024',
           '-F', 'comm,pid,tid,time,event,ip,sym,dso']
    if symfs is not None:
        cmd += ['--symfs', str(symfs)]
    decoded = out / 'perf-script.txt'
    with decoded.open('w') as stdout, (out / 'perf-script.stderr.txt').open('w') as stderr:
        subprocess.run(cmd, stdout=stdout, stderr=stderr, check=True)
    self_counts, inclusive, folded, scopes, depths, events = (collections.Counter() for _ in range(6))
    total = unknown_self = unknown_any = missing_frames = 0
    hotspot_counts = collections.Counter()
    hotspot_patterns = {'GetJettiesUsingTpn': 'ns3::UbTransaction::GetJettiesUsingTpn(', 'ResolveWqeLifecycleLocalId': 'ns3::UbJettyManager::ResolveWqeLifecycleLocalId(', 'CreateJetty': 'ns3::UbFunction::CreateJetty(', 'SubmitWqe': 'ns3::UbFunction::SubmitWqe('}
    unknown_ips = collections.Counter()
    with decoded.open() as lines:
        for sample in parse_samples(lines):
            total += 1
            scopes[(sample['pid'], sample['tid'], sample['comm'])] += 1
            events[sample['event']] += 1
            frames = sample['frames']
            if not frames:
                missing_frames += 1
                frames = [{'label': '[unknown] ([missing-frame])', 'unknown': True, 'ip': ''}]
            depths[len(frames)] += 1
            unknown_self += int(frames[0]['unknown'])
            unknown_any += int(any(f['unknown'] for f in frames))
            for frame in frames:
                if frame['unknown']:
                    unknown_ips[(frame['label'], frame['ip'])] += 1
            for name, pattern in hotspot_patterns.items():
                if any(pattern in f['label'] for f in frames):
                    hotspot_counts[name] += 1
            self_counts[frames[0]['label']] += 1
            inclusive.update(set(f['label'] for f in frames))
            # perf script lists leaf first; folded stacks list root first.
            stack = ';'.join(f['label'].replace(';', ':') for f in reversed(frames))
            folded[stack] += 1
    if total != raw['records']['SAMPLE']:
        raise ValueError(f'Decoded sample count {total} != raw SAMPLE count {raw["records"]["SAMPLE"]}')
    tables = {}
    for name, counter in [('self', self_counts), ('inclusive', inclusive)]:
        rows = [{'symbol': s, 'samples': n, 'percent': 100*n/total if total else 0}
                for s, n in sorted(counter.items(), key=lambda x: (-x[1], x[0]))]
        write_csv(out / f'{name}-all.csv', rows, ['symbol', 'samples', 'percent'])
        write_csv(out / f'{name}-top20.csv', rows[:20], ['symbol', 'samples', 'percent'])
        bars(out / f'{name}-top20.svg', rows[:20], f'{data.parent.name}: {name} Top20', total)
        tables[name + '_top20'] = rows[:20]
    (out / 'stacks-count.folded').write_text(''.join(f'{s} {n}\n' for s,n in sorted(folded.items())))
    write_csv(out / 'unknown-ips.csv', [{'symbol': s, 'ip': ip, 'frame_occurrences': n}
        for (s, ip), n in unknown_ips.most_common()], ['symbol','ip','frame_occurrences'])
    recorder = {}
    console = data.parent / 'stages' / 'ns3' / 'console.txt'
    if console.exists():
        for line in console.read_text().splitlines():
            if line.startswith('CPU samples='):
                recorder = {k: (float(v) if '.' in v else int(v))
                            for k, v in re.findall(r'(\w+)=(-?[\d.]+)', line)}
        if recorder and recorder.get('samples') != total:
            raise ValueError('Recorder console sample count differs from decoded sample count')
    result = dict(raw, recorder=recorder, sample_count=total, weighting='one per SAMPLE record; never period weighted',
                  hotspot_subtrees={k: {'samples': hotspot_counts[k], 'percent': 100*hotspot_counts[k]/total if total else 0, 'stack_pattern': v} for k,v in hotspot_patterns.items()},
                  unknown_self_samples=unknown_self, unknown_any_frame_samples=unknown_any,
                  samples_without_frames=missing_frames, stack_depth_histogram=dict(depths), events=dict(events),
                  pid_tid_scope=[{'pid': p, 'tid': t, 'comm': c, 'samples': n} for (p,t,c),n in sorted(scopes.items())],
                  inclusive_caveat='Observed stack membership, not complete attribution when unwinding is truncated. Recursion deduplicated per sample.',
                  leaf_only_observed=not any(d > 1 for d in depths), decode_command=cmd, **tables)
    write_json(out / 'summary.json', result)
    return result


def analyze_timing(path, out):
    with path.open() as f:
        rows = list(csv.DictReader(f, delimiter='\t'))
    required = ['calls_or_count', 'inclusive_wall_ns', 'inclusive_thread_cpu_ns',
                'exclusive_wall_ns', 'exclusive_thread_cpu_ns']
    for row in rows:
        for k in required:
            row[k] = int(row[k])
        if row['kind'] not in ('timer', 'counter'):
            raise ValueError(f'Unexpected timing kind {row["kind"]}')
    timers = [r for r in rows if r['kind'] == 'timer']
    counters = {r['name']: r['calls_or_count'] for r in rows if r['kind'] == 'counter'}
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / 'timers.csv', timers, ['kind', 'name'] + required)
    write_csv(out / 'counters.csv', [{'name':k,'count':v} for k,v in counters.items()], ['name','count'])
    result = {'timers': timers, 'counters': counters,
              'timing_units': 'integer nanoseconds; CPU is CLOCK_THREAD_CPUTIME_ID',
              'exclusive_definition': 'inclusive minus nested instrumented scopes, not complete function self time',
              'caveat': 'Instrumented timings include measurement overhead. Inclusive scopes overlap; do not sum them.'}
    write_json(out / 'summary.json', result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw', type=Path, default=DEFAULT_RAW)
    p.add_argument('--out', type=Path, default=HERE / 'evidence' / 'analysis')
    p.add_argument('--ledger', type=Path, default=HERE / 'evidence' / 'run-ledger.json')
    p.add_argument('--perf', type=Path, default=Path('/workspace/shared/cpu_sampler/perf'))
    p.add_argument('--symfs', type=Path, help='Extracted matching ELF symbol root')
    p.add_argument('--sizes', type=int, nargs='+', default=[5000,10000,20000,50000])
    p.add_argument('--allow-incomplete', action='store_true')
    args = p.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    ledger = json.loads(args.ledger.read_text())
    entries = {(r['assignments'], r['variant']): r for r in ledger}
    resources, runs, missing, comparisons = [], {}, [], []
    fields = ['assignments','variant','status','returncode','wall_seconds','user_cpu_seconds',
              'system_cpu_seconds','cpu_seconds','peak_rss_kib','sampled_peak_tree_rss_bytes']
    for n in args.sizes:
        base = entries.get((n, 'baseline'))
        for variant in ('baseline','sampled','timed'):
            key = f'{n}-{variant}'
            folder = args.raw / key
            resource = folder / 'stages' / 'ns3' / 'resource.json'
            entry = entries.get((n,variant))
            if not resource.exists() or not entry or entry.get('status') != 'success':
                missing.append(key)
                continue
            r = json.loads(resource.read_text())
            row = {k:r.get(k) for k in fields}
            row.update(assignments=n,variant=variant,cpu_seconds=r['user_cpu_seconds']+r['system_cpu_seconds'])
            resources.append(row)
            run = {'resource': row}
            if base and variant != 'baseline':
                bh, rh = base.get('file_hashes',{}), entry.get('file_hashes',{})
                changed = sorted(k for k in bh.keys() | rh.keys() if bh.get(k) != rh.get(k))
                comparison = {'assignments':n,'variant':variant,
                              'input_hashes_match':base.get('input_hashes') == entry.get('input_hashes'),
                              'all_output_files_byte_identical':bool(bh) and bool(rh) and not changed,
                              'baseline_files':len(bh),'variant_files':len(rh),'differing_files':changed}
                comparisons.append(comparison)
            if variant == 'sampled':
                run['sampling'] = analyze_perf(folder / 'perf.data', args.out / key, args.perf, args.symfs)
            elif variant == 'timed':
                run['timing'] = analyze_timing(folder / 'timing.tsv', args.out / key)
            runs[key] = run
    for row in resources:
        baseline = next((r for r in resources if r['assignments']==row['assignments'] and r['variant']=='baseline'),None)
        for metric in ('wall_seconds','cpu_seconds'):
            row[metric+'_relative_to_baseline'] = row[metric]/baseline[metric] if baseline and baseline[metric] else None
    fields += ['wall_seconds_relative_to_baseline','cpu_seconds_relative_to_baseline']
    write_csv(args.out / 'resources.csv', resources, fields)
    summary = {'raw_root':str(args.raw),'ledger':str(args.ledger),'runs':runs,
               'output_hash_comparisons':comparisons,'missing_or_unsuccessful_runs':missing,
               'complete_matrix':not missing,'measurement_note':'Single runs; ratios are observed overhead, not statistically established regressions.'}
    write_json(args.out / 'summary.json', summary)
    print(json.dumps({'output':str(args.out),'analyzed_runs':len(runs),'missing':missing}))
    if missing and not args.allow_incomplete:
        raise SystemExit('Incomplete matrix. Reports saved; use --allow-incomplete for exploratory analysis.')


if __name__ == '__main__':
    main()
