#!/usr/bin/env python3
"""Tiny synthetic fixture tests only: no builds, native execution, or profiling."""
import json
from pathlib import Path
import shutil
import tempfile
from harness import HERE, freeze, hashes, parity

with tempfile.TemporaryDirectory(prefix='harness-selftest-',dir=HERE / 'evidence') as temp:
    root = Path(temp)
    a = root / 'a'; b = root / 'b'
    (a / 'run').mkdir(parents=True)
    summary = dict.fromkeys(['npus','tokens','assignments','weight_WQEs','weight_TAs','weight_send_bytes_per_npu',
        'combine_sha256','replicas','max_npu_load','per_npu_load','weight_bytes','verified_bytes',
        'remote_bytes','local_bytes','target_segments','remote_WQEs'],1)
    summary['layer_latency_ps']=10
    (a / 'run/summary.json').write_text(json.dumps(summary))
    (a / 'run/simulator-metrics.json').write_text(json.dumps(dict.fromkeys(['assignments','tasks','remote_WQEs','sender_completions','completed_tokens'],1)))
    (a / 'run/events.csv').write_text('time_ps,event,stage,id,node,offset,bytes,task\n1,send,0,0,0,0,1,0\n2,target_complete,0,0,1,0,1,0\n')
    for name in ('executed-transfers.csv','received-payloads.bin','payload-index.csv'):
        (a / 'run' / name).write_bytes(b'synthetic')
    for i in range(398-len(hashes(a / 'run'))):
        (a / 'run' / f'fixture-{i}').write_text('same')
    shutil.copytree(a,b)
    assert parity(a,b,'bytewise')['pass']
    summary['layer_latency_ps']=20
    (b / 'run/summary.json').write_text(json.dumps(summary))
    (b / 'run/events.csv').write_text('time_ps,event,stage,id,node,offset,bytes,task\n9,target_complete,0,0,1,0,1,0\n4,send,0,0,0,0,1,0\n')
    assert not parity(a,b,'bytewise')['pass']
    assert parity(a,b,'logical')['pass']
    with (b / 'run/events.csv').open('a') as f:
        f.write('5,send,0,0,0,0,1,0\n')
    assert not parity(a,b,'logical')['pass']
    shutil.copy2(a / 'run/events.csv',b / 'run/events.csv')
    (b / 'run/received-payloads.bin').write_bytes(b'changed')
    assert not parity(a,b,'logical')['pass']
    source = root / 'source'; source.mkdir(); (source / 'lib').mkdir()
    binary = source / 'app'; binary.write_bytes(b'original fixture executable bytes')
    (source / 'lib/libfixture.so').write_bytes(b'original fixture DSO bytes')
    frozen,lib,_ = freeze(binary,source / 'lib',root,'B')
    freeze(binary,source / 'lib',root,'B')
    binary.write_bytes(b'instrumented fixture executable bytes')
    (source / 'lib/libfixture.so').write_bytes(b'instrumented fixture DSO bytes')
    instrumented,_,_ = freeze(binary,source / 'lib',root,'B-instrumented')
    assert frozen.read_bytes() != instrumented.read_bytes()
    assert (lib / 'libfixture.so').read_bytes() == b'original fixture DSO bytes'
    try:
        freeze(binary,source / 'lib',root,'B')
    except ValueError:
        pass
    else:
        raise AssertionError('Source mutation was not rejected')
    binary.write_bytes(b'original fixture executable bytes')
    (source / 'lib/libfixture.so').write_bytes(b'original fixture DSO bytes')
    frozen.write_bytes(b'tampered frozen fixture')
    try:
        freeze(binary,source / 'lib',root,'B')
    except ValueError:
        pass
    else:
        raise AssertionError('Frozen ELF mutation was not rejected')
print('PASS: 398-file parity; latency/order tolerance; duplicate and payload rejection; isolated instrumented freeze; source/frozen mutation rejection. Synthetic fixtures only, removed afterward.')
