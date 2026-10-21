"""Private controlled-ablation identity, parity, and correctness contracts."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

H = Path(__file__).resolve().parent
ROOT = H.parents[2]
ACCEPTED = ROOT / 'diagnosis-private'
ORIGINAL = ROOT / 'bandwidth-private'
OLD = H.parent / 'ultraep-multicast-integration'
ROOF = H.parent / 'qwen-roofline-compute'
INPUTS = ['config.json', 'input.txt', 'plan.json', 'assignments.csv', 'transfers.csv', 'weight-edges.csv', 'graph-input.txt']
EXACT = ['expert-compute.csv', 'expert-ready.csv', 'replica-ready.csv']
STRATEGIES = ['no-balancing', 'direct', 'chunk-streaming', 'multicast-v2']
REAL_STRATEGIES = ['chunk-streaming', 'multicast-v2']
FIXTURES = ['no-replicas', 'singleton', 'multi-target', 'multi-expert']
WINDOWS = [512, 1024, 2048]
MODES = ['accepted', 'off', 'on']
if not __debug__ or os.environ.get('PYTHONOPTIMIZE', '') not in ('', '0'):
    raise RuntimeError('Assertions must execute')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


run = load('accepted_ablation_resource_guard', ROOT / 'bandwidth-work/experiments/cloudmatrix-bandwidth/guard.py').run


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def check(identity):
    for path, digest in identity.items():
        assert sha(path) == digest, 'Identity changed: ' + path


def freeze(paths):
    return {str(path.resolve()): sha(path) for path in sorted(set(map(Path, paths))) if path.is_file()}


def source_identity(native):
    paths = []
    for project in [H.parents[1], ROOT / 'diagnosis-work', ROOT / 'bandwidth-work']:
        for base in [project / 'experiments', project / 'planner']:
            paths += [p for p in base.rglob('*') if p.is_file() and p.suffix in ('.cc', '.cpp', '.c', '.h', '.hpp', '.inc', '.py', '.cmake') and 'results' not in p.parts]
        paths += list(project.rglob('CMakeLists.txt'))
    for base in [native, ROOT / 'diagnosis-native', ROOT / 'bandwidth-native']:
        paths += [p for p in (base / 'src').rglob('*') if p.is_file() and p.suffix in ('.cc', '.cpp', '.c', '.h', '.hpp', '.inc', '.py', '.cmake', '.txt')]
        paths += [p for p in (base / 'build-support').rglob('*') if p.is_file()]
        paths += [base / name for name in ['CMakeLists.txt', 'ns3', '.ns3rc', '.lock-ns3_linux_build', 'cmake-cache/CMakeCache.txt', 'cmake-cache/build.ninja', 'cmake-cache/compile_commands.json', 'cmake-cache/ns3config.txt', 'cmake-cache/ns3Config.cmake', 'cmake-cache/ns3ConfigVersion.cmake']]
    paths += [H / name for name in ['experiment-plan.md', 'preregistered-analysis.md', 'matrix.yaml', 'command-manifest.yaml', 'audit-a/decision.json']]
    paths += list((H / 'cases').glob('*/experiment-spec.md'))
    return freeze(paths)


def binaries(build, native):
    paths = [build / name for name in ['layer', 'observer-fifo-test', 'jetty-window-test', 'jetty-observer-test', 'graph-tool']]
    paths += [ACCEPTED / 'build' / name for name in ['layer', 'graph-tool', 'observer-fifo-test']]
    paths += [ORIGINAL / 'build' / name for name in ['layer', 'graph-tool', 'parent-layer', 'model-probe']]
    for base in [native, ROOT / 'diagnosis-native', ROOT / 'bandwidth-native']:
        libs = [p for p in (base / 'build/lib').glob('libns3.44-*.so') if '-test.so' not in p.name]
        assert libs, 'Missing native libraries: ' + str(base)
        paths += libs
    return freeze(paths)


def copy_inputs(source, target):
    target.mkdir(parents=True, exist_ok=False)
    for name in INPUTS:
        shutil.copyfile(source / name, target / name)


def summary(directory):
    result = json.loads((directory / 'online-summary.json').read_text())
    result.pop('verification_wall_ns', None)
    return result


def parity(first, second, events=False):
    assert summary(first) == summary(second), 'Full summary mismatch: ' + str(second)
    for name in EXACT + (['events.csv'] if events else []):
        assert (first / name).read_bytes() == (second / name).read_bytes(), 'Exact output/order mismatch: ' + name + ' ' + str(second)


def semantic_parity(first, second):
    """Window interventions may change timing, packet order, and event count only."""
    a, b = summary(first), summary(second)
    fields = ['remote_WQEs', 'TA_count', 'target_segments', 'sender_completions', 'completed_tokens', 'assignments', 'replicas', 'jettys', 'combine_fnv1a64', 'executed_graph_fnv1a64', 'max_npu_load', 'per_npu_load', 'verified_bytes', 'remote_bytes', 'local_bytes']
    for field in fields:
        assert a[field] == b[field], 'Non-timing semantic mismatch: ' + field
    return fields


def diagnostic_args(strategy=None):
    args = ['--diagnostic=1']
    if strategy:
        args += ['--diagnosticNodes=3,5,13,17,27,36,50,52,59,64']
        if strategy == 'multicast-v2':
            args += ['--diagnosticSource=3', '--diagnosticGroup=8']
    return args


def simulator(build, directory, mode, window=512, events=False, extra=(), formal_strategy=None, explicit_window=True):
    assert mode in MODES and window in WINDOWS
    assert mode != 'accepted' or window == 512, 'Accepted control cannot run a changed window'
    binary = ACCEPTED / 'build/layer' if mode == 'accepted' else build / 'layer'
    cmd = [binary, '--input=' + str(directory / 'input.txt'), '--out=' + str(directory), '--computeModel=roofline', '--compute-tflops=100', '--hbm-bandwidth-gbps=2692', '--jettyMode=pair', '--logLevel=' + ('events' if events else 'summary'), '--capacityMetrics=' + str(directory / 'simulator-metrics.json')]
    if mode != 'accepted' and explicit_window:
        cmd += ['--jetty-ta-window=' + str(window)]
    if mode == 'on':
        cmd += diagnostic_args(formal_strategy)
    return cmd + list(extra)


def validate(stage, build, directory, fault=None, model='roofline'):
    stage([sys.executable, OLD / 'preflight.py', directory, '--graph-tool', build / 'graph-tool', '--execution-summary', directory / 'online-summary.json'], directory / 'postflight-host')
    extra = (['--grant'] if fault == 'invalidate-grant' else ['--fault=' + fault]) if fault else []
    stage([sys.executable, OLD / 'verify.py', directory, *extra], directory / 'independent-host')
    stage([sys.executable, ROOF / 'verify-compute.py', directory, '--expected-model=' + model], directory / 'compute-host')
    metrics = json.loads((directory / 'simulator-metrics.json').read_text())
    s = summary(directory)
    for key in ['simulator_events', 'assignments', 'remote_WQEs', 'jettys', 'TA_count', 'sender_completions', 'completed_tokens']:
        assert metrics[key] == s[key], 'Capacity metric mismatch: ' + key


def validate_diagnostics(directory, measurements=True):
    status = json.loads((directory / 'diagnostic-status.json').read_text())
    assert status['enabled'] is True and status['incomplete'] is False, 'Incomplete recorder: ' + str(directory)
    for key in ['queue_observations_open', 'queue_unmatched', 'queue_order_errors', 'queue_depth_errors', 'grant_outcomes_unmatched', 'grant_start_overwrites', 'grant_starts_open']:
        assert status[key] == 0, 'Queue observer invariant ' + key + ' failed: ' + str(directory)
    if measurements:
        jetty = json.loads((directory / 'diagnostic-jetty-status.json').read_text())
        assert jetty['incomplete'] is False, 'Incomplete Jetty recorder'
        for key in ['pending_ta_observations', 'pending_source_frames', 'pending_ack_marks', 'terminal_nonzero_jetties', 'occupancy_errors', 'unmatched_accepted_taacks']:
            assert jetty[key] == 0, 'Jetty recorder invariant ' + key
        for name in ['diagnostic-jetty-aggregates.csv', 'diagnostic-jetty-occupancy.csv', 'diagnostic-jetty-tail.csv', 'diagnostic-jetty-weight-tail.csv', 'diagnostic-ta-rtt-tail.csv']:
            assert (directory / name).is_file(), 'Missing Jetty artifact: ' + name
        for name in ['diagnostic-jetty-tail.csv', 'diagnostic-jetty-weight-tail.csv', 'diagnostic-ta-rtt-tail.csv']:
            bounded_rows = list(csv.DictReader((directory / name).open()))
            assert len(bounded_rows) <= jetty['max_tail'], 'Bounded tail exceeded cap'
            if name == 'diagnostic-ta-rtt-tail.csv':
                for row in bounded_rows:
                    assert 0 <= int(row['admission_ps']) <= int(row['first_native_pop_ps']) <= int(row['first_source_tx_ps']) <= int(row['accepted_taack_ps']), 'Invalid measured RTT ordering'
        rows = list(csv.DictReader((directory / 'diagnostic-jetty-aggregates.csv').open()))
        assert len(rows) == jetty['tracked_jetties']
        occupancy = list(csv.DictReader((directory / 'diagnostic-jetty-occupancy.csv').open()))
        assert len(occupancy) == 6 * len(rows), 'Missing occupancy bins'
        histograms = {}
        for row in occupancy:
            key = (row['source'], row['target'], row['jetty'])
            histogram = histograms.setdefault(key, {})
            assert row['bin'] not in histogram, 'Duplicate occupancy bin'
            histogram[row['bin']] = row
        for row in rows:
            assert int(row['terminal_outstanding']) == 0 and row['ssn_next'] == row['ssn_una']
            assert 0 <= int(row['max_outstanding']) <= int(row['window'])
            assert int(row['cleanup_events']) == 0, 'Successful run must not use cancellation cleanup'
            assert 0 <= int(row['max_window_full_interval_ps']) <= int(row['window_saturated_ps'])
            if int(row['window_full_intervals']) == 0:
                assert int(row['max_window_full_interval_ps']) == int(row['window_saturated_ps']) == 0
            assert int(row['admissions']) == int(row['ssn_progress']), 'Incomplete SSN progress'
            assert int(row['weight_ack_without_source_tx']) == int(row['weight_ack_without_native_pop']) == 0
            assert int(row['weight_admission_to_ack_count']) == int(row['weight_native_pop_to_ack_count']) == int(row['weight_source_tx_to_ack_count'])
            assert int(row['weight_admission_to_ack_count']) <= int(row['accepted_taacks'])
            histogram = histograms[(row['source'], row['target'], row['jetty'])]
            assert set(histogram) == set(map(str, range(6)))
            assert sum(int(item['all_observed_ps']) for item in histogram.values()) == int(row['observed_ps'])
            assert sum(int(item['weight_phase_ps']) for item in histogram.values()) == int(row['weight_phase_observed_ps'])
            assert int(histogram['5']['all_observed_ps']) == int(row['window_saturated_ps'])
            assert int(histogram['5']['weight_phase_ps']) == int(row['weight_phase_window_saturated_ps'])
    return status


def validate_config(directory, window, enabled):
    cfg = json.loads((directory / 'ablation-config.json').read_text())
    assert cfg['jetty_ta_window'] == window
    assert cfg['jetty_ooo_ack_window'] == 2048
    assert cfg['tp_packet_window'] == 1000
    assert cfg['logical_ssn_uint32_no_wrap_bound'] is True
    assert 0 <= cfg['predicted_total_tas_upper_bound'] <= 4294967295
    assert cfg['measurement_enabled'] is enabled
    assert cfg['allocator_policy'] == 'original', 'A+B or allocator intervention is forbidden'
    return cfg


def build_identities(build):
    identities = {name: json.loads((build / (name + '.json')).read_text()) for name in ['source-identity', 'accepted-identity', 'binary-identity']}
    for identity in identities.values():
        check(identity)
    return identities


def native_delta(native):
    """Prove B's native delta is passive hooks only; original allocator byte-identical."""
    accepted = ROOT / 'diagnosis-native'
    allowed = {'src/unified-bus/model/protocol/ub-function.cc', 'src/unified-bus/model/protocol/ub-function.h', 'src/unified-bus/model/ub-reversal-diagnostic.h'}
    relative = {str(path.relative_to(base)) for base in [accepted, native] for path in (base / 'src').rglob('*') if path.is_file()}
    changed = []
    for name in sorted(relative):
        first, second = accepted / name, native / name
        a, b = sha(first) if first.is_file() else None, sha(second) if second.is_file() else None
        if a != b:
            changed.append(dict(path=name, accepted_sha256=a, ablation_sha256=b))
    assert {row['path'] for row in changed} == allowed, 'Unexpected native delta, or incomplete passive hooks: ' + str(changed)
    allocator = 'src/unified-bus/model/ub-switch-allocator.cc'
    assert sha(accepted / allocator) == sha(native / allocator)
    return dict(status='PASS', changed=changed, allocator_sha256=sha(native / allocator), original_allocator_byte_identical=True)
