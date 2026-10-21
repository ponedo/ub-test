"""Small orchestration helpers, not a new execution or instrumentation path."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

# Loading accepted helpers must not leave generated files in their source tree.
sys.dont_write_bytecode = True

H = Path(__file__).resolve().parent
E = H.parent
BASE = '3521a64fd300938af3af4573a9793c4cde8d9649'
STRATEGIES = ('chunk-streaming', 'multicast-v2')
INPUTS = ('config.json', 'input.txt', 'plan.json', 'assignments.csv',
          'transfers.csv', 'weight-edges.csv', 'graph-input.txt')
SOURCE_SHA = {
    'config.json': '78bc57d0316db6ce89cce227012c19d805c28bd2c3525bc8eba9972dc5bd09da',
    'input.txt': '7bf625729d2652657ea083fa2ac39c9a02c4a40ec977db414720c709242a4f1b',
    'plan.json': '7cf755cade55ef2d8497a91a7f710d3ce263f98e5ec175d0231c8e157b51633a',
    'assignments.csv': 'b5878b60eab1eba0db3aa321f461d6f1f1c92d43f278e33e878ee4fc9558d3b5',
    'transfers.csv': '4260248706d33e80c8e7a81c9fa57cac000773fc1cc7ed05757f4e1d18b8c9f6',
}
PLAN_SEMANTIC = '5df5e9b331e487985f0b53a8e0485e9acc477bd71d756430029f8b7427bed06d'
MAPPING_SHA = '17c7c0a71bfd4062650f2d952f0fb9e451641d1c4680f28aecafe5060e71f959'
ROUTING_SHA = '6e74b9ff210f53a40c86cb12b83c6a5ea417922f902d4a474e3dc4427005da4e'
RELAY = dict(chunk_bytes=4096, relay_min_replicas=4, relay_max_relays=8,
             relay_min_fanout_gain=2, force_relay=False, reorder_ns=0,
             slow_relay_rank=4294967295, slow_relay_ns=0)

def require(condition, why):
    if not condition:
        raise ValueError(why)

def read(path):
    return json.loads(Path(path).read_text())

def write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    temporary.replace(path)

def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(part)
    return value.hexdigest()

def semantic(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def semantic_plan(path):
    value = read(path)
    value.pop('cpu_wall_ns', None)
    return semantic(value)

def freeze(paths):
    return {str(Path(p).resolve()): sha(p) for p in sorted(set(map(Path, paths)))}

def check(identity):
    require(isinstance(identity, dict) and bool(identity), 'Empty identity manifest')
    for name, digest in identity.items():
        require(sha(name) == digest, 'Immutable file changed: ' + name)

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def simulator(binary, directory):
    return [str(binary), '--input=' + str(directory / 'input.txt'), '--out=' + str(directory),
            '--computeModel=roofline', '--compute-tflops=100', '--hbm-bandwidth-gbps=2692',
            '--jettyMode=pair', '--logLevel=summary',
            '--capacityMetrics=' + str(directory / 'simulator-metrics.json'),
            '--jetty-ta-window=512', '--diagnostic=1',
            '--diagnosticSource=4294967294', '--diagnosticGroup=4294967294',
            '--payloadBudgetBytes=8589934592', '--weightTaskLimit=1000000']
