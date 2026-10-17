#!/usr/bin/env python3
"""Cheap static generator tests; native compilation/parity remain separate gates."""
import contextlib,importlib.util,io,json,pathlib,tempfile,unittest
H=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('relay_instrument',H/'generate-instrumented.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class InstrumentationTests(unittest.TestCase):
 def test_generate_and_proof(self):
  with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()):
   out=pathlib.Path(d)/'out';m.generate(H.parent/'pair-jetty',out)
   p=json.loads((out/'instrumentation-source-proof.json').read_text())
   self.assertTrue(p['observer_erasure_roundtrip_byte_exact']);self.assertEqual(p['simulator_control_calls_checked'],11)
   self.assertEqual(p['all_simulator_expressions_checked'],18)
   app=(out/'pair-layer.cc').read_text();audit=(out/'online-validation.inc').read_text()
   self.assertIn('qprof::Phase::DependencyIndexBuild',app);self.assertIn('qprof::Phase::OnlineIndexBuild',audit)
   self.assertIn('qprof::SetModes(dependencyMode,onlineMembershipMode)',app)
 def test_changed_source_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   source=pathlib.Path(d)/'source';source.mkdir()
   for name in m.EXPECTED:(source/name).write_bytes((H.parent/'pair-jetty'/name).read_bytes())
   with (source/'pair-layer.cc').open('a') as f:f.write('// unreviewed change\n')
   with self.assertRaisesRegex(RuntimeError,'Baseline source changed'):m.generate(source,pathlib.Path(d)/'out')
 def test_balanced_lambda_calls(self):
  src='Simulator::Schedule(t,[&](){f(")"); /* ) */ g();}); Simulator::Stop(t);'
  self.assertEqual(m.simulator_calls(src),['Simulator::Schedule(t,[&](){f(")"); /* ) */ g();})','Simulator::Stop(t)'])
if __name__=='__main__':unittest.main()
