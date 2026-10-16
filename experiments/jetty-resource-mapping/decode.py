#!/usr/bin/env python3
"""Reuse the established official-perf decoder; retain exact MMAP ELF files as copies."""
import argparse
import json
from pathlib import Path
import shutil
import struct
import sys
from harness import PROFILING, sha

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--attempt',type=Path,required=True)
p.add_argument('--perf',type=Path,help='Required for sampled runs; unused for instrumented timing.tsv')
p.add_argument('--out',type=Path,required=True)
a = p.parse_args()
r = json.loads((a.attempt / 'attempt.json').read_text())
if r['status'] != 'success' or r['phase'] not in ('sampled','instrumented'):
    p.error('Only decode a successful sampled or instrumented attempt')
if r['phase'] == 'sampled' and not a.perf:
    p.error('Sampled decoding requires --perf')
if a.out.exists():
    p.error('Refuse existing output directory')
a.out.mkdir(parents=True)
sys.path.insert(0,str(PROFILING))
if r['phase'] == 'instrumented':
    from analyze import analyze_timing
    result = analyze_timing(a.attempt / 'timing.tsv',a.out)
    print(json.dumps({'out':str(a.out),'counters':result['counters']}))
    raise SystemExit(0)
paths = set()
data = a.attempt / 'perf.data'
with data.open('rb') as f:
    h = f.read(56)
    if h[:8] != b'PERFILE2':
        raise ValueError('Expected standard perf.data')
    _,_,_,_,_,off,length = struct.unpack('<7Q',h)
    end = off + length
    while off < end:
        f.seek(off)
        typ,misc,size = struct.unpack('<IHH',f.read(8))
        if size < 8 or off+size > end:
            raise ValueError('Malformed perf record')
        if typ == 10:
            f.seek(off+72)
            name = f.read(size-72).split(b'\0',1)[0].decode(errors='strict')
            if name.startswith('/'):
                paths.add(Path(name))
        off += size
manifest = {}
symfs = a.out / 'symfs'
for path in sorted(paths):
    if not path.is_file():
        manifest[str(path)] = {'missing':True}
        continue
    dest = symfs / str(path).lstrip('/')
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path,dest)
    manifest[str(path)] = {'sha256':sha(dest),'bytes':dest.stat().st_size}
(a.out / 'symbol-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
sys.path.insert(0,str(PROFILING))
from analyze import analyze_perf
result = analyze_perf(data,a.out / 'analysis',a.perf.resolve(),symfs.resolve())
print(json.dumps({'samples':result['sample_count'],'out':str(a.out),'missing_elfs':[k for k,v in manifest.items() if v.get('missing')]}))
