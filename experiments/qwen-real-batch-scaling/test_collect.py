"""Aggregate collector regression checks; these do not run a simulator."""
import importlib.util,json,pathlib,subprocess,sys,tempfile,unittest
ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('collector',ROOT/'collect.py');collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
class CollectorTests(unittest.TestCase):
 def test_planning_reroute_event_deltas(self):
  self.assertEqual(collector.planning_times_ms({'layer_start':1000,'planning_end':201000,'reroute_end':301000}),{'planning_ms':0.0002,'reroute_ms':0.0001})
  self.assertEqual(collector.planning_times_ms({'layer_start':1000,'planning_end':1000,'reroute_end':1000}),{'planning_ms':0.0,'reroute_ms':0.0})
  self.assertEqual(collector.planning_times_ms({'layer_start':20,'planning_end':50,'reroute_end':90}),{'planning_ms':30/1e9,'reroute_ms':40/1e9})
  with self.assertRaises(KeyError):collector.planning_times_ms({'layer_start':1000})
  with self.assertRaises(AssertionError):collector.planning_times_ms({'layer_start':1000,'planning_end':999,'reroute_end':1001})
 def test_failure_inventory_and_empty_performance(self):
  with tempfile.TemporaryDirectory() as td:
   p=pathlib.Path(td);private=p/'private';hist=p/'historical';out=p/'out';case=private/'tokens-512/layer-0/direct/simulator-host';case.mkdir(parents=True);hist.mkdir()
   (hist/'performance.csv').write_text('tokens,layer,strategy,status,validation\n')
   (p/'skew.json').write_text(json.dumps({'measured_skew':[]}))
   (private/'scaling-status.json').write_text(json.dumps({'status':'STOPPED','completed_sizes':[],'current_size':512,'secret_path':'do not publish'}))
   (case/'resource.json').write_text(json.dumps({'status':'STOPPED','guard':'tree rss limit at /private/secret','command':['secret']}))
   (private/'tokens-512/status.json').write_text(json.dumps({'status':'STOPPED','failure_resource':str(case/'resource.json')}))
   (private/'tokens-512/runs.json').write_text(json.dumps([{'tokens':512,'layer':0,'strategy':'direct','status':'RUNNING'}]))
   subprocess.run([sys.executable,str(ROOT/'collect.py'),'--private-root',str(private),'--historical',str(hist),'--skew',str(p/'skew.json'),'--out',str(out)],check=True,capture_output=True)
   inv=json.loads((out/'case-status.json').read_text());self.assertEqual(len(inv),27);r=next(x for x in inv if x['tokens']==512 and x['layer']==0 and x['strategy']=='direct');self.assertEqual(r['status'],'STOPPED');self.assertEqual(r['guard_categories'],{'simulator':'rss'});self.assertFalse(r['performance_eligible']);self.assertEqual(json.loads((out/'aggregate.json').read_text()),[])
   self.assertNotIn('/private/', ''.join(x.read_text() for x in out.iterdir()));self.assertNotIn('secret', ''.join(x.read_text() for x in out.iterdir()))
if __name__=='__main__':unittest.main()
