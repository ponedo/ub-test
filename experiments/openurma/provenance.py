# SPDX-License-Identifier: Apache-2.0
"""Capture the exact sources and generated elements used by this build."""
import hashlib,json,os,re,subprocess,sys
from pathlib import Path

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def command(*args):return subprocess.check_output(args,text=True).strip()
root=Path(__file__).resolve().parents[2]
version_header=Path(os.environ['SYSTEMC_PREFIX'])/'include/sysc/kernel/sc_ver.h'
version='.'.join(re.search(r'#define SC_VERSION_'+part+r'\s+(\d+)',version_header.read_text())[1] for part in ['MAJOR','MINOR','PATCH'])
out=Path(sys.argv[1]);data={'upstream':json.loads((root/'third_party/openurma/UPSTREAM.json').read_text()),
    'compiler':command('g++','--version').splitlines()[0],
    'cmake':command(os.environ.get('CMAKE_BIN','cmake'),'--version').splitlines()[0],
    'systemc_header_sha256':digest(Path(os.environ['SYSTEMC_PREFIX'])/'include/sysc/kernel/sc_ver.h'),
    'systemc_version':version,
    'files':{},'builds':{}}
for name in ['openurma/elements/protocols/ub/UB_Jetty_Sched.clnp','patches/openurma/0001-jetty-rr-drr.patch','experiments/openurma/component.cpp','experiments/openurma/analyze.py','experiments/openurma/run.py']:
    data['files'][name]=digest(root/name)
for variant,env in [('native','OPENURMA_NATIVE_ROOT'),('patched','OPENURMA_PATCHED_ROOT')]:
    p=Path(os.environ[env]);data['builds'][variant]={'commit':command('git','-C',str(p),'rev-parse','HEAD'),
        'scheduler_sha256':digest(p/'elements/protocols/ub/UB_Jetty_Sched.clnp'),
        'generated_systemc_sha256':digest(p/'build/openurma_gen/systemc/topology_no_main.cpp'),
        'component_binary_sha256':digest(p/'build/component')}
(out/'provenance.json').write_text(json.dumps(data,indent=2,sort_keys=True)+'\n')
