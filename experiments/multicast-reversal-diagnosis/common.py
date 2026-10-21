"""Private-only parity, immutable identities, and accepted validators."""
import hashlib, importlib.util, json, os, shutil, sys
from pathlib import Path
H=Path(__file__).resolve().parent
ROOT=H.parents[2]
ACCEPTED=ROOT/'bandwidth-private'
OLD=H.parent/'ultraep-multicast-integration'
ROOF=H.parent/'qwen-roofline-compute'
INPUTS=['config.json','input.txt','plan.json','assignments.csv','transfers.csv','weight-edges.csv','graph-input.txt']
STRATEGIES=['no-balancing','direct','chunk-streaming','multicast-v2']
MODES=['accepted','off','on']
if not __debug__ or os.environ.get('PYTHONOPTIMIZE','') not in ('','0'):raise RuntimeError('Assertions must execute')
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
run=load('accepted_bandwidth_guard',ROOT/'bandwidth-work/experiments/cloudmatrix-bandwidth/guard.py').run
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):Path(p).write_text(json.dumps(value,indent=2)+'\n')
def check(identity):
 for p,h in identity.items():assert sha(p)==h,'Identity changed: '+p
def freeze(paths):return {str(p.resolve()):sha(p) for p in sorted(set(paths)) if p.is_file()}
def source_identity(native):
 # Freeze entire experiment and Planner source trees, plus both native full src
 # trees (including core/network/internet), not merely patched unified-bus files.
 paths=[]
 projects=[H.parents[1],ROOT/'bandwidth-work']
 for project in projects:
  for base in [project/'experiments',project/'planner']:
   paths += [p for p in base.rglob('*') if p.is_file() and p.suffix in ('.cc','.cpp','.c','.h','.hpp','.py','.cmake') and 'results' not in p.parts]
  paths += [p for p in project.rglob('CMakeLists.txt') if p.is_file()]
 for base in [native,ROOT/'bandwidth-native']:
  paths += [p for p in (base/'src').rglob('*') if p.is_file() and p.suffix in ('.cc','.cpp','.c','.h','.hpp','.py','.cmake','.txt')]
  paths += [p for p in (base/'build-support').rglob('*') if p.is_file()]
  paths += [base/name for name in ['CMakeLists.txt','ns3','.ns3rc','.lock-ns3_linux_build','cmake-cache/CMakeCache.txt','cmake-cache/build.ninja','cmake-cache/compile_commands.json','cmake-cache/ns3config.txt','cmake-cache/ns3Config.cmake','cmake-cache/ns3ConfigVersion.cmake']]
 return freeze(paths)
def binaries(build,native):
 paths=[build/'layer',build/'observer-fifo-test',build/'graph-tool',ACCEPTED/'build/layer',ACCEPTED/'build/graph-tool',ACCEPTED/'build/parent-layer',ACCEPTED/'build/model-probe']
 for base in [native,ROOT/'bandwidth-native']:
  libs=[p for p in (base/'build/lib').glob('libns3.44-*.so') if '-test.so' not in p.name];assert libs;paths+=libs
 return freeze(paths)
def copy_inputs(source,target):
 target.mkdir(parents=True,exist_ok=False)
 for name in INPUTS:shutil.copyfile(source/name,target/name)
def summary(d):
 x=json.loads((d/'online-summary.json').read_text());x.pop('verification_wall_ns',None);return x
def parity(a,b,events=False):
 assert summary(a)==summary(b),'Full summary mismatch: '+str(b)
 names=['expert-compute.csv','expert-ready.csv','replica-ready.csv']+(['events.csv'] if events else [])
 for n in names:assert (a/n).read_bytes()==(b/n).read_bytes(),'Exact output/order mismatch: '+n+' '+str(b)
def simulator(build,d,mode,events=False,extra=()):
 binary=ACCEPTED/'build/layer' if mode=='accepted' else build/'layer'
 cmd=[binary,'--input='+str(d/'input.txt'),'--out='+str(d),'--computeModel=roofline','--compute-tflops=100','--hbm-bandwidth-gbps=2692','--jettyMode=pair','--logLevel='+('events' if events else 'summary'),'--capacityMetrics='+str(d/'simulator-metrics.json')]
 if mode=='on':cmd+=diagnostic_args(d)
 return cmd+list(extra)
def diagnostic_args(d):
 # Kept centralized to match the passive recorder's public CLI.
 args=['--diagnostic=1']
 # Formal-only, pre-registered symmetric physical-resource filter. Small gate
 # keeps every diagnostic selector empty to test the full observer surface.
 if d.parent.name=='real-3136' and d.name in ['chunk-streaming','multicast-v2']:
  args+=['--diagnosticNodes=3,5,13,17,27,36,50,52,59,64']
  if d.name=='multicast-v2':args+=['--diagnosticSource=3','--diagnosticGroup=8']
 return args
def validate(stage,build,d,fault=None,model='roofline'):
 stage([sys.executable,OLD/'preflight.py',d,'--graph-tool',build/'graph-tool','--execution-summary',d/'online-summary.json'],d/'postflight-host')
 extra=(['--grant'] if fault=='invalidate-grant' else ['--fault='+fault]) if fault else []
 stage([sys.executable,OLD/'verify.py',d,*extra],d/'independent-host')
 stage([sys.executable,ROOF/'verify-compute.py',d,'--expected-model='+model],d/'compute-host')

def validate_diagnostics(d):
 status=json.loads((d/'diagnostic-status.json').read_text())
 assert status['enabled'] is True and status['incomplete'] is False,'Incomplete recorder: '+str(d)
 for key in ['queue_observations_open','queue_unmatched','queue_order_errors','queue_depth_errors','grant_outcomes_unmatched','grant_start_overwrites','grant_starts_open']:
  assert status[key]==0,'Queue observer invariant '+key+' failed: '+str(d)
 return status
