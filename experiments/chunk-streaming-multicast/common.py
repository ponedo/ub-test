"""Small APP-only orchestration helpers; no planner or native transport replacement."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
sys.dont_write_bytecode = True
H = Path(__file__).resolve().parent
E = H.parent
BASE = '3a33cc6a249667fc46bf02ac0fed4e1127d7c1ab'
HYBRID = 'chunk-streaming-multicast'
STRATEGIES = ('no-balancing', 'direct', 'chunk-streaming', 'multicast-v2', HYBRID)
GRAPH_FILES = ('input.txt', 'graph-input.txt', 'weight-edges.csv', 'transfers.csv', 'plan.json', 'assignments.csv')
INPUTS = ('config.json',) + GRAPH_FILES
RELAY = dict(chunk_bytes=4096, relay_min_replicas=4, relay_max_relays=8, relay_min_fanout_gain=2,
             force_relay=False, reorder_ns=0, slow_relay_rank=4294967295, slow_relay_ns=0)
FIELDS = ['task', 'stage', 'id', 'source', 'target', 'physical', 'bytes', 'source_physical', 'offset', 'dependencies']

def require(value, message):
    if not value:
        raise ValueError(message)

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)

def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(data)
    return digest.hexdigest()

def semantic(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def freeze(paths):
    return {str(Path(path).resolve()): sha(path) for path in sorted(set(map(Path, paths)))}

def check(identity):
    require(isinstance(identity, dict) and bool(identity), 'Empty identity manifest')
    for path, digest in identity.items():
        require(sha(path) == digest, 'Immutable file changed: ' + path)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def canonical_graph(transfers):
    return '\n'.join([','.join(FIELDS)] + [','.join(';'.join(map(str, x[key])) if key == 'dependencies' else str(x[key]) for key in FIELDS) for x in transfers]) + '\n'

def simulator(binary, directory, strategy, extra=()):
    directory = Path(directory)
    command = [str(binary), '--input=' + str(directory / 'input.txt'), '--out=' + str(directory),
               '--computeModel=roofline', '--compute-tflops=100', '--hbm-bandwidth-gbps=2692',
               '--jettyMode=pair', '--logLevel=summary',
               '--capacityMetrics=' + str(directory / 'simulator-metrics.json'),
               '--jetty-ta-window=512', '--diagnostic=1',
               '--diagnosticSource=4294967294', '--diagnosticGroup=4294967294',
               '--payloadBudgetBytes=8589934592', '--weightTaskLimit=1000000']
    if strategy == HYBRID:
        command.append('--weight-transport=cs-mc')
    return command + list(extra)


def stage(command, out, identity, wall=4800):
    """Reuse accepted guard/heartbeat, never retry or adopt unrelated processes."""
    import os
    import types
    out = Path(out)
    require(not out.exists(), 'No implicit restart: ' + str(out))
    require(0 < wall <= 4800, 'Stage wall limit cannot exceed 4800 seconds')
    check(identity)
    guard = load('cs_mc_accepted_guard', E / 'cloudmatrix-bandwidth/guard.py')
    heartbeat_class = load('cs_mc_accepted_heartbeat', E / 'multicast-token-screening/heartbeat.py').Heartbeat
    heartbeat = heartbeat_class(out, command)
    heartbeat.start()
    original_time = guard.m.time
    def sampled_sleep(seconds):
        original_time.sleep(seconds)
        heartbeat.tick()
    guard.m.time = types.SimpleNamespace(monotonic=original_time.monotonic, sleep=sampled_sleep)
    result = None
    try:
        result = guard.run(command, out, wall=wall, case=out.parent,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    finally:
        guard.m.time = original_time
        heartbeat.stop(result['status'] if result else 'STOPPED_OR_UNCERTAIN')
    require(heartbeat.error is None, 'Durable heartbeat failed: ' + str(heartbeat.error))
    require(result['status'] == 'PASS' and result['guard'] is None, 'Guarded stage failed: ' + str(out))
    check(identity)
    return result


def resource_admission(root, simulation=False):
    import os
    import shutil
    import psutil
    root = Path(root)
    require(psutil.virtual_memory().available >= 7 * 1024**3, 'Need 6 GiB allowance plus 1 GiB host reserve')
    require(shutil.disk_usage(root).free >= 8 * 1024**3 and shutil.disk_usage('/tmp').free >= 2 * 1024**3, 'Disk reserve unavailable')
    if simulation:
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                argv = process.info['cmdline'] or []
                simulator_process = process.info['name'] in ('layer', 'parent-layer', 'pair-layer', 'cs-mc-layer') or any(arg.startswith('--jettyMode=') for arg in argv[1:])
                require(process.pid == os.getpid() or not simulator_process, 'Another simulator is visible; do not overlap')
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
