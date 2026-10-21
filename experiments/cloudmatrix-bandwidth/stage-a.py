#!/usr/bin/env python3
"""Bounded correctness gate on unchanged accepted roofline/native executables.

Only the emitted network link bandwidth differs between paired fixtures. The
accepted independent graph, network, exact payload/WQE/readiness/drain, CBFC and
compute validators remain authoritative. This script never builds executables.
"""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOF = HERE.parent / 'qwen-roofline-compute'
OLD = HERE.parent / 'ultraep-multicast-integration'

STRATEGIES = ['no-balancing', 'direct', 'chunk-streaming', 'multicast-v2']
RATES = [100, 3136]
INPUT_FILES = ['config.json', 'input.txt', 'plan.json', 'assignments.csv',
               'transfers.csv', 'weight-edges.csv', 'graph-input.txt']

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

# Explicit local wrapper retains accepted numerical limits and owns cleanup.
run = load('bandwidth_stage_guard', HERE / 'guard.py').run

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def identity(build, native):
    files = [build / 'layer', build / 'parent-layer', build / 'graph-tool']
    libs = [p for p in sorted((native / 'build/lib').glob('libns3.44-*.so'))
            if '-test.so' not in p.name]
    assert libs, 'No native ns3 libraries found'
    return {str(p.resolve()): sha(p) for p in files + libs}

def comparable_summary(directory):
    summary = json.loads((directory / 'online-summary.json').read_text())
    summary.pop('verification_wall_ns', None)
    return summary

def assert_only_bandwidth_changed(low, high):
    for name in INPUT_FILES:
        x, y = (low / name).read_text(), (high / name).read_text()
        if name == 'config.json':
            x, y = json.loads(x), json.loads(y)
            for section in ['runtime', 'parameters']:
                assert x[section]['link_gbps'] == 100 and y[section]['link_gbps'] == 3136
                y[section]['link_gbps'] = 100
        elif name == 'plan.json':
            x, y = json.loads(x), json.loads(y)
            # Only planner host measurement varies. Every decision stays exact.
            x.pop('cpu_wall_ns', None)
            y.pop('cpu_wall_ns', None)
        elif name == 'input.txt':
            x, y = x.split(), y.split()
            assert x[12] == '100' and y[12] == '3136'
            y[12] = '100'
        assert x == y, 'Unexpected non-bandwidth input difference: ' + name

def main():
    if not __debug__ or os.environ.get('PYTHONOPTIMIZE', '') not in ('', '0'):
        raise RuntimeError('Assertions must remain enabled')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--source-identity', type=Path, required=True,
                        help='JSON map of absolute immutable source paths to SHA-256')
    parser.add_argument('--reference', type=Path,
                        help='Previously accepted roofline stage-A output for exact 100-Gbps comparison')
    parser.add_argument('--rate-probe', type=Path, help='Defaults to BUILD/rate-probe')
    args = parser.parse_args()
    build, native, out = args.build.resolve(), args.native.resolve(), args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    os.environ['RELAY_GRAPH_TOOL'] = str(build / 'graph-tool')
    sources = json.loads(args.source_identity.read_text())
    assert isinstance(sources, dict) and sources, 'Empty source identity'
    for path, digest in sources.items():
        assert Path(path).is_absolute() and sha(path) == digest, 'Source identity mismatch: ' + path
    before = identity(build, native)
    (out / 'identity-before.json').write_text(json.dumps(dict(binary_identity=before, source_identity=sources), indent=2)+'\n')
    rows = []
    def stage(command, directory):
        result = run(command, directory, 1800, case=out)
        assert result['status'] == 'PASS', 'Stage failed: ' + str(directory)
        return result
    stage([args.rate_probe.resolve() if args.rate_probe else build / 'rate-probe'], out / 'native-rate-probe')
    probe = json.loads((out / 'native-rate-probe/console.txt').read_text())
    assert probe['status'] == 'PASS' and probe['rate_bps'] == 3136000000000
    assert probe['resolution'] == 'PS'
    assert [r['bytes'] for r in probe['serialization']] == [1,40,64,159,160,161,1024,4096]
    assert all(r['actual_ps'] > 0 and abs(r['actual_ps']-r['rounded_ideal_ps']) <= 1 for r in probe['serialization'])
    assert [r['consumed_cells'] for r in probe['cell_boundaries']] == [1,1,2]
    cases = load('bandwidth_accepted_cases', HERE.parent / 'multi-npu-relay/cases.py')
    adapter = load('bandwidth_accepted_adapter', OLD / 'adapter.py')
    matrix = {
        'no-replicas': cases.loads(4,1,[32,0,0,0],slots=0),
        'singleton': cases.loads(4,1,[8,0,4,4]),
        'multi-target': cases.loads(4,1,[32,0,0,0]),
        'multi-expert': cases.loads(8,2,[128,128]+[0]*14,slots=3),
    }
    comparisons = 0
    reference_kind = 'NOT_PROVIDED'
    reference_csv = {}
    if args.reference:
        reference_root = args.reference.resolve()
        csv_path = reference_root if reference_root.is_file() else reference_root.parent/'stage-a.csv'
        if csv_path.is_file():
            with csv_path.open() as handle:
                reference_csv = {(r['case'],r['strategy']):r for r in csv.DictReader(handle) if r['model']=='roofline'}
            assert len(reference_csv) == 16, 'Incomplete accepted CSV reference'
    def validate(directory, fault=None):
        stage([sys.executable, OLD/'preflight.py', directory, '--graph-tool', build/'graph-tool'], directory/'preflight-host')
        cmd = [build/'layer', '--input='+str(directory/'input.txt'), '--out='+str(directory),
               '--computeModel=roofline', '--compute-tflops=100', '--hbm-bandwidth-gbps=2692',
               '--logLevel='+('events' if fault else 'summary'), '--jettyMode=pair',
               '--capacityMetrics='+str(directory/'simulator-metrics.json')]
        if fault:
            cmd += ['--invalidateGrant=1'] if fault == 'invalidate-grant' else ['--nativeRetrans=1', '--networkFault='+fault]
        stage(cmd, directory/'simulator-host')
        stage([sys.executable, OLD/'preflight.py', directory, '--graph-tool', build/'graph-tool',
               '--execution-summary', directory/'online-summary.json'], directory/'postflight-host')
        verify = [sys.executable, OLD/'verify.py', directory]
        if fault:
            verify += ['--grant'] if fault == 'invalidate-grant' else ['--fault='+fault]
        stage(verify, directory/'independent-host')
        stage([sys.executable, ROOF/'verify-compute.py', directory, '--expected-model=roofline'], directory/'compute-host')
    for name, config in matrix.items():
        for rate in RATES:
            base = out/name/str(rate)/'base'
            baseline = out/name/str(rate)/'no-bal-base'
            parameters = dict(weight_bytes=12288, link_gbps=rate)
            cases.base.emit(config, parameters, 'ultraep', base)
            cases.base.emit(config, parameters, 'no-balancing', baseline)
            for strategy in STRATEGIES:
                directory = out/name/str(rate)/strategy
                adapter.emit(baseline if strategy == 'no-balancing' else base,
                             dict(force_relay=True), 'direct' if strategy == 'no-balancing' else strategy, directory)
                if rate == 3136:
                    assert_only_bandwidth_changed(out/name/'100'/strategy, directory)
                validate(directory)
                summary = comparable_summary(directory)
                if rate == 100 and args.reference:
                    reference = args.reference.resolve()/name/strategy/'roofline'
                    if (reference/'online-summary.json').is_file():
                        assert summary == comparable_summary(reference), 'Accepted 100-Gbps semantics changed: ' + str(reference)
                        reference_kind = 'EXACT_SUMMARY'
                    else:
                        assert reference_csv, 'No accepted summaries or stage-a.csv available'
                        expected = reference_csv[name,strategy]
                        assert expected['status'] == 'PASS'
                        assert summary['layer_latency_ps'] == int(expected['layer_latency_ps']), 'Accepted latency changed'
                        assert summary['combine_fnv1a64'] == expected['output_hash'], 'Accepted output payload hash changed'
                        reference_kind = 'EXACT_PUBLISHED_LATENCY_AND_OUTPUT_HASH'
                    comparisons += 1
                rows.append(dict(case=name, strategy=strategy, link_gbps=rate, model='roofline', status='PASS', summary=summary))
                (out/'results.json').write_text(json.dumps(rows, indent=2)+'\n')
    source = out/'multi-target'/'3136'/'multicast-v2'
    for fault in ['data-once', 'ack-once', 'invalidate-grant']:
        directory = out/'network'/'3136'/fault
        directory.mkdir(parents=True)
        for name in INPUT_FILES:
            shutil.copyfile(source/name, directory/name)
        validate(directory, fault)
    assert identity(build, native) == before, 'Accepted binary identity changed during tests'
    for path, digest in sources.items():
        assert sha(path) == digest, 'Immutable source changed during tests: ' + path
    status = dict(status='PASS', link_gbps=RATES, strategies=STRATEGIES,
                  small_cases_pass=True, native_rate_probe_pass=True, fault_smoke_pass=True,
                  small_case_runs=len(rows), native_fault_smoke_runs=3,
                  reference_100_comparisons=comparisons,
                  reference_100_status='PASS' if comparisons == 16 else 'NOT_PROVIDED',
                  reference_100_comparison_kind=reference_kind,
                  binary_identity=before, source_identity=sources)
    (out/'status.json').write_text(json.dumps(status, indent=2)+'\n')
    print('PASS stage A: 32 small cases, native rate probe, 3 fault smokes', flush=True)

if __name__ == '__main__':
    main()
