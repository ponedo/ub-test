#!/usr/bin/env python3
"""Pure contracts only: no compiler, graph executable, simulator, or web access."""
import ast
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import adapter
import common
import fixtures
import phase_b
import preflight


def accepted_fixture(name='multi8'):
    root=common.E/'multi-npu-relay/evidence'/name/'chunk-streaming'
    c=common.read(root/'config.json');p=common.read(root/'plan.json')
    with tempfile.TemporaryDirectory() as temporary:
        c,p=adapter.decorate_cs(c,p,Path(temporary))
    return c,p


def tiny_group():
    return [dict(group=1,source=0,source_physical=0,expert=0,offset=0,bytes=2053,
                 graph_role='direct-fallback',dependencies=[],members=[dict(task=0,target=1,physical=1),dict(task=1,target=2,physical=2)])]


def trace(pattern):
    rows=[];seq=0
    for ordinal,mode in enumerate(pattern):
        off=ordinal*1024;length=min(1024,2053-off)
        for task in ([0] if mode=='E' else [0,1]):
            rows.append(dict(kind='envelope' if mode=='E' else 'native_first',group='1',task=str(task),offset=str(off),bytes=str(length),sequence=str(seq if mode=='E' else 2**32-1)))
        if mode=='E':seq+=1
    return rows


class FixtureContracts(unittest.TestCase):
    def test_imports_and_declarations_start_no_process(self):
        with patch('subprocess.run',side_effect=AssertionError('process forbidden')),patch('subprocess.Popen',side_effect=AssertionError('process forbidden')):
            m=fixtures.matrix()
        self.assertEqual(m['maximum_tokens'],200)
        self.assertEqual(m['simulator_executions'],50)
        self.assertEqual(len(m['coverage']),14)
        self.assertEqual(m['native_ta_window'],512)
        self.assertFalse(any(r['log_level']=='debug' for r in m['rows']))

    def test_fixed_native_pressure_not_token_scale(self):
        spec=fixtures.definitions()['reuse-window']
        self.assertEqual(len(spec['planner_input']['mapping']),64)
        self.assertGreater(spec['model']['weight_bytes']//spec['relay']['chunk_bytes'],1024)
        self.assertGreater(spec['topology']['min_pair_tas'],512)
        self.assertFalse(any('window=' in x for r in fixtures.matrix()['rows'] for x in r['options']))

    def test_regression_exact_original_all_four_modes(self):
        rows=[r for r in fixtures.matrix()['rows'] if r['kind']=='regression']
        self.assertEqual(len(rows),12)
        self.assertEqual({r['strategy'] for r in rows},set(fixtures.OLD_MODES))
        self.assertTrue(all(r['executables']==['accepted','candidate'] for r in rows))
        self.assertEqual(fixtures.ACCEPTED_BINARY_SHA256,'27b3eae2b2aa7cd3c932359261c410238ae53beb4a752ca0d1e62e225befc85b')

    def test_resource_limits_exact(self):
        b=fixtures.BUDGET;g=1024**3
        self.assertEqual(b,dict(tree_rss_bytes=6*g,address_space_bytes=7*g,wall_seconds=4800,min_host_available_bytes=g,min_disk_free_bytes=8*g,min_tmp_disk_free_bytes=2*g))

    def test_faults_exact_native_tail_hops_and_feedback(self):
        self.assertEqual([(x['fault'],x['role']) for x in fixtures.FAULTS],
          [('data-once','stage1'),('data-once','stage2'),('ack-once','stage1'),('taack-once','stage2'),('duplicate-once','stage2')])
        self.assertTrue(any('out-of-order' in item for item in fixtures.UNSUPPORTED))

    def test_no_false_coverage_by_row_name(self):
        result=phase_b.aggregate_coverage([{'status':'PASS','id':'F01','coverage':{'fault_data_stage1':False}}],{'native':['fault_data_stage1']})
        self.assertEqual(result['status'],'INCOMPLETE')
        self.assertEqual(result['missing'],{'native':['fault_data_stage1']})

    def test_semantic_declaration_stable(self):
        self.assertEqual(common.semantic(fixtures.matrix()),common.semantic(fixtures.matrix()))


class GraphContracts(unittest.TestCase):
    def test_static_accepted_cs_group_partition(self):
        for name in ('slots_zero4','single4','multi8','tail4','multi_expert8'):
            with self.subTest(name=name):
                c,p=accepted_fixture(name);actual=preflight.check_groups(c,p)
                self.assertEqual(actual['members'],sum(x['stage']==2 for x in c['transfers']))
                self.assertEqual(c['hybrid_groups'],preflight.expected_groups(c,p))

    def test_empty_group_set_valid(self):
        c,p=accepted_fixture('slots_zero4')
        self.assertEqual(preflight.check_groups(c,p)['operations'],0)

    def test_singleton_keeps_one_real_native_task(self):
        c,p=accepted_fixture('single4');g=c['hybrid_groups']
        self.assertEqual(len(g),1);self.assertEqual(len(g[0]['members']),1)
        self.assertEqual(g[0]['graph_role'],'direct-fallback')

    def test_both_hops_and_multirelay_groupchunk(self):
        c,p=accepted_fixture();groups=c['hybrid_groups']
        self.assertTrue(any(g['graph_role']=='stage1' and len(g['members'])==2 for g in groups))
        self.assertTrue(any(g['graph_role']=='stage2' and len(g['members'])==2 and len(g['dependencies'])==2 for g in groups))

    def test_remove_sibling_relay_parent_is_rejected_even_if_metadata_regenerated(self):
        c,p=accepted_fixture();edge=next(x for x in c['transfers'] if x['stage']==2 and len(x['dependencies'])>1)
        edge['dependencies']=edge['dependencies'][:1];c['hybrid_groups']=adapter.group_specs(c,p)
        with self.assertRaisesRegex(ValueError,'GroupChunk'):preflight.check_groups(c,p)

    def test_add_cross_chunk_parent_rejected(self):
        c,p=accepted_fixture();edge=next(x for x in c['transfers'] if x['stage']==2 and x['dependencies'])
        other=next(x['task'] for x in c['transfers'] if x['stage']==2 and not x['dependencies'] and x['offset']!=edge['offset'])
        edge['dependencies']=sorted(edge['dependencies']+[other]);c['hybrid_groups']=adapter.group_specs(c,p)
        with self.assertRaisesRegex(ValueError,'GroupChunk'):preflight.check_groups(c,p)

    def test_duplicate_member_rejected(self):
        c,p=accepted_fixture();c['hybrid_groups'][0]['members'].append(copy.deepcopy(c['hybrid_groups'][0]['members'][0]))
        with self.assertRaisesRegex(ValueError,'partition'):preflight.check_groups(c,p)

    def test_missing_member_rejected(self):
        c,p=accepted_fixture();c['hybrid_groups'][0]['members'].pop()
        with self.assertRaisesRegex(ValueError,'partition'):preflight.check_groups(c,p)

    def test_range_expert_source_and_order_mutations_rejected(self):
        for key in ('offset','bytes','expert','source_physical','source','group'):
            with self.subTest(key=key):
                c,p=accepted_fixture();c['hybrid_groups'][0][key]+=1
                with self.assertRaisesRegex(ValueError,'partition'):preflight.check_groups(c,p)
        c,p=accepted_fixture();c['hybrid_groups'][0]['members'].reverse()
        with self.assertRaisesRegex(ValueError,'partition'):preflight.check_groups(c,p)

    def test_negative_and_overflow_ids_rejected(self):
        for key,value in [('task',-1),('source',2**32),('offset',-1),('bytes',2**32)]:
            c,p=accepted_fixture();next(x for x in c['transfers'] if x['stage']==2)[key]=value
            with self.assertRaises((ValueError,KeyError)):preflight.expected_groups(c,p)

    def test_direct_fallback_cannot_be_rechunked(self):
        c,p=accepted_fixture('single4');next(x for x in c['transfers'] if x['stage']==2)['bytes']-=1
        c['hybrid_groups']=adapter.group_specs(c,p)
        with self.assertRaisesRegex(ValueError,'whole-expert'):preflight.check_groups(c,p)

    def test_tail_and_shard_boundaries_static(self):
        c,p=accepted_fixture('tail4');info=fixtures.inspect_topology(c,p,dict(tail=True,shard_tail=True))
        self.assertGreater(info['groups'],1)

    def test_all_graph_file_bytes_preserved(self):
        source=common.E/'multi-npu-relay/evidence/multi8/chunk-streaming'
        with tempfile.TemporaryDirectory() as temporary:
            out=Path(temporary)/'hybrid';adapter.from_cs_control(source,out)
            preflight.compare_cs_bytes(out,source)
            self.assertEqual((out/'input.txt').read_text().splitlines()[1].split()[6],'2')
            (out/'transfers.csv').write_bytes((out/'transfers.csv').read_bytes()+b'\n')
            with self.assertRaisesRegex(ValueError,'byte/order identity'):preflight.compare_cs_bytes(out,source)

    def test_cannot_overwrite_control(self):
        source=common.E/'multi-npu-relay/evidence/multi8/chunk-streaming'
        with self.assertRaisesRegex(ValueError,'Do not modify'):adapter.from_cs_control(source,source)


class EvidenceContracts(unittest.TestCase):
    def test_native_then_envelope_offset_gap(self):
        result=phase_b.first_send_contract(tiny_group(),trace('UEE'),1024)
        self.assertTrue(result['first_unicast_then_merge']);self.assertFalse(result['envelope_unicast_envelope'])

    def test_envelope_native_envelope_with_tail(self):
        result=phase_b.first_send_contract(tiny_group(),trace('EUE'),1024)
        self.assertTrue(result['envelope_unicast_envelope'])

    def test_all_native_is_correct_but_not_merge_coverage(self):
        result=phase_b.first_send_contract(tiny_group(),trace('UUU'),1024)
        self.assertFalse(any(result.values()))

    def test_false_sequence_offset_equivalence_rejected(self):
        rows=trace('UEE');rows[2]['sequence']='1'
        with self.assertRaisesRegex(ValueError,'sequence'):phase_b.first_send_contract(tiny_group(),rows,1024)

    def test_missing_duplicate_wrong_range_and_expert_rejected(self):
        for mutator in [lambda r:r.pop(),lambda r:r.append(copy.deepcopy(r[-1])),lambda r:r[0].update(bytes='1023'),lambda r:r[0].update(task='9')]:
            rows=trace('EUE');mutator(rows)
            with self.assertRaises(ValueError):phase_b.first_send_contract(tiny_group(),rows,1024)

    def test_retry_never_advances_first_send_coverage(self):
        rows=trace('EUE');rows.append(dict(kind='retry',group='1',task='0',offset='0',bytes='1024',sequence='0'))
        phase_b.first_send_contract(tiny_group(),rows,1024)

    def test_missing_or_wrong_uid_physical_hop_not_proof(self):
        route=[dict(kind='native_write',task='5',psn='7',offset='0',uid='99',event=event,node=str(node),port=str(port),time_ps=str(i+10)) for i,(event,node,port) in enumerate([('tx_start',0,0),('rx',4,0),('tx_start',4,2),('rx',2,0)])]
        self.assertEqual(phase_b.ordered_route(route,5,0,2,4,psn=7),[10,11,12,13])
        self.assertIsNone(phase_b.ordered_route(route[:-1],5,0,2,4,psn=7))
        route[-1]['uid']='100';self.assertIsNone(phase_b.ordered_route(route,5,0,2,4,psn=7))

    def test_exact_abort_only_not_generic_crash(self):
        self.assertEqual(phase_b.accepted_rejection(dict(guard=None,returncode=2),'ERROR: payload byte mismatch','payload byte mismatch'),'payload byte mismatch')
        self.assertEqual(phase_b.accepted_rejection(dict(guard=None,returncode=-6),'hybrid same-range native payload differs','payload byte mismatch',True),'hybrid same-range native payload differs')
        for code,guard,text in [(-9,None,'payload byte mismatch'),(-6,None,'generic crash'),(2,'wall_guard','ERROR: payload byte mismatch')]:
            with self.assertRaises(ValueError):phase_b.accepted_rejection(dict(guard=guard,returncode=code),text,'payload byte mismatch',True)

    def test_false_failure_cannot_leave_pass(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);common.write(root/'validation.json',dict(status='FAIL'))
            phase_b.require_no_success(root)
            common.write(root/'hybrid-summary.json',dict(status='PASS'))
            with self.assertRaisesRegex(ValueError,'false success'):phase_b.require_no_success(root)

    def test_no_runtime_approval_starts_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);common.write(root/'prepared-manifest.json',{})
            common.write(root/'ledger.json',dict(status='PREPARED'))
            common.write(root/'approval.json',dict(status='PASS',approved_to_run=False,phase='B'))
            args=type('Args',(),dict(out=root,approval=root/'approval.json'))()
            with patch.object(phase_b,'stage',side_effect=AssertionError('must not run')):
                with self.assertRaisesRegex(ValueError,'approval missing'):phase_b.run(args)

    def test_stopped_cannot_resume(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);common.write(root/'prepared-manifest.json',{});common.write(root/'ledger.json',dict(status='STOPPED'))
            args=type('Args',(),dict(out=root,approval=root/'missing'))()
            with self.assertRaisesRegex(ValueError,'No implicit resume'):phase_b.run(args)

    def test_default_original_only_hybrid_selects_transport(self):
        old=common.simulator('/never-run',Path('/never-input'),'chunk-streaming')
        new=common.simulator('/never-run',Path('/never-input'),common.HYBRID)
        self.assertFalse(any(x.startswith('--weight-transport') for x in old))
        self.assertEqual(new[:-1],old);self.assertEqual(new[-1],'--weight-transport=cs-mc')

    def test_merge_eligibility_uses_native_tp_vl_not_transaction_priority(self):
        # Source-contract regression only, not a claim that an envelope ran.
        # B03's required physical fanout-3 witness remains the runtime test.
        native=common.E.parent.parent/'token-screen-native/src/unified-bus/model'
        datatype=(native/'ub-datatype.h').read_text()
        function=(native/'protocol/ub-function.cc').read_text()
        transport=(native/'protocol/ub-transport.cc').read_text()
        hybrid=(common.H/'hybrid-multicast.h').read_text()
        self.assertRegex(datatype,r'UB_PRIORITY_DEFAULT\s*=\s*8')
        self.assertIn('m_priority(UB_PRIORITY_DEFAULT)',datatype)
        self.assertIn('m_priority{UB_PRIORITY_DEFAULT}',datatype)
        self.assertIn('segment->SetPriority(wqe->GetPriority());',function)
        # The native data builder uses TP m_priority for both actual DL fields.
        self.assertRegex(transport,r'UbDataLink::AddPacketHeader\(p,\s*false,\s*false,\s*m_priority,\s*m_priority,')
        self.assertIn('m.tx->GetPriority()!=7',hybrid)
        self.assertNotIn('s->GetPriority()!=7',hybrid)
        layer=(common.H/'layer.cc').read_text()
        send=layer[layer.index('    void Send('):layer.index('    uint64_t Duration(',layer.index('    void Send('))] if '    uint64_t Duration(' in layer[layer.index('    void Send('):] else layer[layer.index('    void Send('):layer.index('    void Ready(')]
        self.assertNotIn('wqe->SetPriority',send)
        codec=(common.E/'ub-multicast-v2/adapter-v2.h').read_text()
        self.assertIn('dl.GetPacketVL()!=outer.GetPacketVL()',codec)

    def test_python_syntax_only(self):
        for path in common.H.glob('*.py'):ast.parse(path.read_text(),filename=str(path))


if __name__=='__main__':unittest.main(verbosity=2)
