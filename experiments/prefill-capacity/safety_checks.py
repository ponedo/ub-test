#!/usr/bin/env python3
"""Cheap negative preflights; no large payloads, cap changes or simulation."""
import hashlib,json,subprocess,sys,os
from pathlib import Path
ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1];NATIVE=Path('/workspace/ns-3-ub');RAW=Path(os.environ.get('CAPACITY_RAW','/workspace/prefill-capacity-raw'));out=ROOT/'evidence'
paths=['src/unified-bus/model/protocol/ub-header.cc','src/unified-bus/model/protocol/ub-header.h','src/unified-bus/model/protocol/ub-function.h','src/unified-bus/model/protocol/ub-function.cc','src/unified-bus/model/ub-sliding-bitmap-window.h','src/core/model/simulator.h']
files={p:hashlib.sha256((NATIVE/p).read_bytes()).hexdigest() for p in paths}
assert 'jettyNum & 0xFFFFF' in (NATIVE/paths[0]).read_text()
assert 'std::vector<uint64_t> m_slots' in (NATIVE/paths[4]).read_text()
cmd=[sys.executable,str(ROOT/'stage.py'),'generate','--case',str(RAW/'negative-wire-1m'),'--assignments','1000000']
r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode!=0 and 'wire Jetty ID limit' in r.stderr
(out/'wire-1m-preflight.txt').write_text('COMMAND '+repr(cmd)+'\nRETURN '+str(r.returncode)+'\n'+r.stdout+r.stderr)
# Original A cap must still reject before parsing/allocating assignment payloads.
path=RAW/'negative-assignment-cap.txt';path.write_text('64 128 8 25000 64 128 2 1024 1000 500 100 20261016 100 20\n3 49152 0 0 0 0 0 128\n')
cmd=['/workspace/ns-3-ub/build/scratch/ns3.44-multi-npu-relay','--input='+str(path),'--out='+str(RAW/'negative-assignment-cap')]
r=subprocess.run(cmd,capture_output=True,text=True);assert r.returncode!=0 and 'payload bound' in r.stderr
(out/'original-cap-rejection.txt').write_text('COMMAND '+repr(cmd)+'\nRETURN '+str(r.returncode)+'\n'+r.stdout+r.stderr)
(out/'native-audit.json').write_text(json.dumps(dict(revision=subprocess.check_output(['git','-C',str(NATIVE),'rev-parse','HEAD'],text=True).strip(),source_sha256=files,wire_jetty_bits=20,wire_task_capacity=2**20,conservative_weight_task_reserve=20000,maximum_assignments_with_reserve=(2**20-20000)//2,ta_ssn_bits=16,tp_psn_bits=24,jetty_ack_window_slots=2048,slot_bytes=8,window_bytes_per_remote_task=16384,negative_preflights_passed=2,old_cap_unchanged=True),indent=2)+'\n')
print('PASS native source assertions and two rejection preflights')
