#!/usr/bin/env python3
"""Tiny isolated orchestration tests; no planner or simulator work is launched."""
import json,runpy,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
H=Path(__file__).resolve().parent

class HarnessTests(unittest.TestCase):
 def execute(self,fail_at=None):
  calls=[]
  with tempfile.TemporaryDirectory(prefix='qwen-harness-',dir=H.parents[2]) as tmp:
   root=Path(tmp);raw=root/'raw';binary=root/'binary';binary.write_text('fixture');graph=root/'graph';graph.write_text('fixture');lib=root/'lib';lib.mkdir();tok=512
   def run(command,where,wall,**kwargs):
    nonlocal tok
    self.assertEqual(wall,3600);calls.append(str(where));where.mkdir(parents=True,exist_ok=True)
    if fail_at==len(calls):return dict(status='FAIL',guard='injected_guard',wall_seconds=0)
    if where.name=='preparation-host':
     tok=int(command[command.index('--tokens')+1]);prep=Path(command[command.index('--out')+1]);prep.mkdir();(prep/'preparation-metrics.json').write_text(json.dumps(dict(shared_routing_sha256='same',planner_cpu_wall_seconds={'no-balancing':0,'ultraep':0})));(prep/'expert-load.json').write_text('{}');(prep/'routing.csv').write_text('same')
    elif where.name=='simulator-host':
     dest=where.parent/'run';(dest/'validation.json').write_text('{"status":"PASS"}');s=dict(timeline=dict(weights_end=0,planning_end=0,dispatch_gate=0),event_spans={},stage_intervals=[[0,0],[0,0]],compute_intervals=[],verified_bytes=[0,0,0],layer_latency_ps=1)
     (dest/'online-summary.json').write_text(json.dumps(s));(dest/'simulator-metrics.json').write_text('{}')
    elif where.name in ('preflight-host','postflight-host'):
     Path(command[command.index('--out')+1]).write_text('{"status":"PASS"}')
    return dict(status='PASS',guard=None,wall_seconds=0)
   def restore(source,dest,prefix=None):
    dest.mkdir(parents=True);c=dict(runtime=dict(segment_bytes=1024),planner_input=dict(npus=64,mapping=[{}]*tok),mode='no-balancing' if prefix=='no-balancing' else 'ultraep',weight_strategy=prefix,readiness='fixture',transfers=[],assignments=[{}]*(tok*8));plan=dict(physical=[dict(rank=0,quota=tok*8,kind='main')]);(dest/'config.json').write_text(json.dumps(c));(dest/'plan.json').write_text(json.dumps(plan));(dest/'input.txt').write_text('fixture')
   guard=types.ModuleType('guard');guard.run=run;guard.snapshot=lambda:{}
   compact=types.ModuleType('compact');compact.compact=lambda *args:{};compact.sha=lambda p:'same'
   restoremod=types.ModuleType('restore');restoremod.restore=restore
   cap=types.ModuleType('capacity');cap.actual=lambda *args:{}
   argv=['run.py','--raw',str(raw),'--binary',str(binary),'--lib',str(lib),'--graph-tool',str(graph),'--tokens','512','1024']
   with patch.dict(sys.modules,{'guard':guard,'compact':compact,'restore':restoremod,'capacity':cap}),patch.object(sys,'argv',argv):
    try:runpy.run_path(str(H/'run.py'),run_name='__main__')
    except SystemExit as ex:self.assertEqual(ex.code,2)
   status=json.loads((raw/'status.json').read_text());records=json.loads((raw/'runs.json').read_text())
   return calls,status,records
 def test_each_failure_stops(self):
  # Preparation and every arm's independent preflight/simulator/postflight.
  for failed in range(1,11):
   with self.subTest(stage=failed):
    calls,status,records=self.execute(failed);self.assertEqual(len(calls),failed);self.assertEqual(status['status'],'STOPPED');self.assertEqual(status['completed_token_points'],[])
    self.assertFalse(any(r.get('status')=='PASS' and r['tokens']!=512 for r in records))
 def test_complete_level_before_next(self):
  calls,status,records=self.execute();self.assertEqual(status['status'],'PASS');self.assertEqual(status['completed_token_points'],[512,1024]);self.assertEqual(len(calls),20)
  self.assertEqual([r['strategy'] for r in records],['no-balancing','direct','chunk-streaming']*2);self.assertTrue(all(r['status']=='PASS' for r in records))
 def test_second_preparation_failure_retains_first(self):
  calls,status,records=self.execute(11);self.assertEqual(status['completed_token_points'],[512]);self.assertEqual(len(calls),11);self.assertEqual(len(records),3)


class CapacityTests(unittest.TestCase):
 def test_valid_and_boundary_rejections(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('scaling_capacity_test',H/'capacity.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  fixed=json.loads((H/'fixed-config.json').read_text());params=fixed['application_parameters'];relay=fixed['relay_parameters']
  with tempfile.TemporaryDirectory(prefix='qwen-capacity-') as tmp:
   out=Path(tmp)/'prediction.json';plan={'physical':[{'kind':'main','expert':0}]}
   d=m.predicted({'mapping':[{}]*512},plan,params,relay,out);self.assertEqual(d['expert_weight_bytes'],9437184);self.assertEqual(d['logical_payload_bytes'],512*8*8192);self.assertEqual(d['pointer_bits'],64)
   with self.assertRaises(AssertionError):m.predicted({'mapping':[{}]*12501},plan,params,relay,out)
   too_many={'physical':[{'kind':'replica','expert':0} for _ in range(1000)]}
   with self.assertRaises(AssertionError):m.predicted({'mapping':[{}]*512},too_many,params,relay,out)
   with patch.object(m.struct,'calcsize',return_value=4):
    with self.assertRaises(AssertionError):m.predicted({'mapping':[{}]*512},plan,params,relay,out)

if __name__=='__main__':unittest.main()
