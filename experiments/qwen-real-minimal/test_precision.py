import importlib.util,json,tempfile,unittest
from pathlib import Path
H=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('adapter',H.parent/'direct-weight-forward/adapter.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class Precision(unittest.TestCase):
 def case(self,params):
  c=dict(schema_version=1,npus=2,experts=2,top_k=1,main_placement=[0,1],slots=[1,1],mapping=[dict(source=0,experts=[0])],beta='1.01',min_replica_quota=1)
  with tempfile.TemporaryDirectory() as tmp:return m.emit(c,params,'no-balancing',tmp)[0]
 def test_default_unchanged(self):
  c=self.case({});self.assertEqual(c['runtime']['weight_bytes'],3*64*128*2);self.assertNotIn('weight_dtype_bytes',c['runtime'])
 def test_qwen_fp8_bf16(self):
  c=self.case(dict(model_dim=4096,ff_dim=1536,dtype_bytes=2,weight_dtype_bytes=1));self.assertEqual(c['runtime']['weight_bytes'],18874368);self.assertEqual(c['runtime']['weight_size_kind'],'matrix_exact');self.assertEqual(c['transfers'][0]['bytes'],8192)
 def test_invalid(self):
  for x in [0,-1,1.5,True,9]:
   with self.assertRaises(ValueError):self.case(dict(weight_dtype_bytes=x))
if __name__=='__main__':unittest.main()
