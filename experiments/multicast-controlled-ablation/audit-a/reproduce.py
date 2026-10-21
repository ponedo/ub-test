#!/usr/bin/env python3
"""Build/run only a bounded scheduler unit witness; never modify native sources."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import signal
import subprocess
import time

HERE = Path(__file__).resolve().parent
DIAG = HERE.parent.parent / 'multicast-reversal-diagnosis'
ADAPTER_SHA256 = '447f7e296bab4af1d3f97482161d4f7e35f82bb89785bf63a64fc779951bd44c'
EXPECTED = {
    'native': 'native fc=CBFC link_gbps=3136 allocation_ps=5000 callbacks=3 suppressed=0 commits=A@10000ps,B@25000ps',
    'suppress': 'suppress fc=CBFC link_gbps=3136 allocation_ps=5000 callbacks=2 suppressed=2 commits=B@6000ps,A@11000ps',
}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()

def limits():
    resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3,) * 2)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (128 * 1024**2,) * 2)

def run(cmd, log, timeout):
    start = time.monotonic()
    with log.open('w') as f:
        p = subprocess.Popen([str(x) for x in cmd], stdout=f, stderr=subprocess.STDOUT,
                             preexec_fn=limits, start_new_session=True)
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            raise RuntimeError(f'{log.name} exceeded {timeout} seconds; process group terminated')
    if p.returncode:
        raise RuntimeError(f'{log.name} returned {p.returncode}; inspect the retained log')
    return {'returncode': p.returncode, 'wall_seconds': time.monotonic() - start}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', type=Path, required=True,
                   help='Unmodified accepted diagnostic native tree, already built')
    p.add_argument('--out', type=Path, required=True, help='New private output directory')
    a = p.parse_args()
    native, out = a.native.resolve(), a.out.resolve()
    if out.exists():
        raise RuntimeError('Output must not already exist; no overwrites')
    if out == native or native in out.parents:
        raise RuntimeError('Outputs must be outside the protected native tree')
    manifest = json.loads((DIAG / 'native-diagnostic-manifest.json').read_text())
    files = {row['path']: row['diagnostic_sha256'] for row in manifest['files']}
    for rel, expected in files.items():
        if sha(native / rel) != expected:
            raise RuntimeError(f'Accepted native source mismatch: {rel}')
    if sha(DIAG / 'pair-multicast-v2.h') != ADAPTER_SHA256:
        raise RuntimeError('Accepted PairV2Proxy source identity mismatch')
    lib = native / 'build/lib'
    libs = {f.name: sha(f) for f in sorted(lib.glob('*.so'))}
    for needed in ('unified-bus', 'internet', 'network', 'core'):
        if f'libns3.44-{needed}.so' not in libs:
            raise RuntimeError(f'Missing existing native library {needed}; this script never rebuilds native')
    out.mkdir(parents=True)
    binary = out / 'null-callback-order'
    cmd = ['c++', '-std=c++20', '-O0', '-g', HERE / 'null-callback-order.cc',
           '-I' + str(DIAG), '-I' + str(native / 'build/include'),
           '-L' + str(lib), '-Wl,--disable-new-dtags', '-Wl,-rpath,' + str(lib),
           '-lns3.44-unified-bus', '-lns3.44-internet', '-lns3.44-network',
           '-lns3.44-core', '-o', binary]
    execution = {'build': run(cmd, out / 'build.log', 120)}
    outputs = {}
    for mode, expected in EXPECTED.items():
        execution[mode] = run([binary, mode], out / (mode + '.log'), 15)
        outputs[mode] = (out / (mode + '.log')).read_text().strip()
        if outputs[mode] != expected:
            raise RuntimeError(f'Unexpected {mode} witness; do not treat this as reproduction')
    for rel, expected in files.items():
        if sha(native / rel) != expected:
            raise RuntimeError(f'Native source changed during audit: {rel}')
    if {f.name: sha(f) for f in sorted(lib.glob('*.so'))} != libs:
        raise RuntimeError('Native libraries changed during audit')
    result = {
        'audit_status': 'COUNTEREXAMPLE_CONFIRMED',
        'experiment_A_status': 'UNSUPPORTED_SEMANTIC_PRESERVATION',
        'scope': 'Scheduler/ACK-queue unit witness, not physical WRITE or real LayerLatency',
        'allocation_ps': 5000, 'flow_control': 'CBFC', 'configured_link_gbps': 3136,
        'native_sources_unchanged': True, 'native_libraries_unchanged': True,
        'native_source_sha256': files, 'native_library_sha256': libs,
        'accepted_pair_proxy_sha256': ADAPTER_SHA256,
        'counterexample_sha256': sha(HERE / 'null-callback-order.cc'),
        'binary_sha256': sha(binary), 'outputs': outputs, 'execution': execution,
    }
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'audit_status': result['audit_status'],
                      'experiment_A_status': result['experiment_A_status'],
                      'outputs': outputs}, indent=2))

if __name__ == '__main__':
    main()
