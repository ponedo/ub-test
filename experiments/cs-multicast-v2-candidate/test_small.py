#!/usr/bin/env python3
"""Pure matrix and contract tests only; no fixture generation or subprocesses."""
import ast, unittest, tempfile, csv
from candidate_verify import check_candidate
from evidence import native_accounting
from support import *
class SmallContract(unittest.TestCase):
    def test_scope(self):
        d=declaration();self.assertEqual(d['executions'],37)
        self.assertEqual([r['retained_id'] for r in d['rows'][:14]],['B01','B02','B03','B04','B05','B06','B09','B10','B12','F01','F02','F03','F04','F05'])
        self.assertEqual(d['fixtures']['reuse-window']['relay']['chunk_bytes'],4096)
        self.assertNotIn('lifetime_groups_gt1024',d['rows'][7]['required_witnesses'])
        self.assertEqual(d['fixtures']['reuse-window']['model']['weight_bytes'],1082369)
        self.assertEqual(sum(len(r['arms']) for r in d['rows']),37)
    def test_syntax(self):
        for p in HERE.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
    def test_no_legacy_mutation(self):
        self.assertEqual(fixtures.definitions()['reuse-window']['relay']['chunk_bytes'],1024)
        self.assertEqual(declaration()['rows'][11]['retained_id'],'F03')
class HoldOracle(unittest.TestCase):
    def fixture(self, directory, mutate=None):
        group=dict(group=1,graph_role='stage1',members=[dict(target=1,task=10),dict(target=2,task=11)])
        write(directory/'config.json',dict(hybrid_groups=[group]))
        summary=dict(status='PASS',enabled=True,hold_ps=5000,scope='stage1-stage2-only',priority_data_eligibility='unknown-speculative-no-CC-probe',identical_realized_grants_claimed=False,
            active_holds=0,armed=1,released=1,evidence_cap=32768,hold_ledger_complete=True,pull_snapshot_limit_per_role_reason=32,
            pull_decisions=0,pull_decisions_sampled=0,pull_decisions_omitted=0,evidence_rows=6,held_heads_consumed=1,max_release_to_consume_ps=400,max_app_hold_ps=5000,expired=1,early_releases=0,head_change_releases=0)
        rows=[]
        for event,time in [('arm',100),('release',5100),('consumed',5500)]:
            for rank,task in [(1,10),(2,11)]:
                rows.append(dict(time_ps=time,event=event,reason='submitted_aligned_absent_data_eligibility_unknown' if event=='arm' else 'deadline',source=0,target=1,tp=3,
                    group=1,selected_task=10,selected_ssn=123456,selected_offset=0,selected_length=1024,hold_generation=1,
                    hold_active=int(event=='arm'),hold_spent=int(event!='arm'),armed_ps=100,deadline_ps=5100,released_ps=0 if event=='arm' else 5100,
                    member_rank=rank,expected_task=task,submitted=1,consumed_bytes=0,native_limited=-1))
        if mutate:mutate(summary,rows)
        write(directory/'candidate-summary.json',summary)
        with (directory/'candidate-holds.csv').open('w') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    def test_valid_and_mutations(self):
        mutations=[lambda s,r:s.update(active_holds=1),lambda s,r:s.update(evidence_cap=131072),
            lambda s,r:s.update(hold_ledger_complete=False),lambda s,r:s.update(pull_decisions_omitted=1),
            lambda s,r:r[2].update(released_ps=5101),lambda s,r:r[0].update(submitted=0),
            lambda s,r:r[1].update(expected_task=99),lambda s,r:r[0].update(native_limited=0)]
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);self.assertEqual(check_candidate(root,True)['status'],'PASS')
            for mutation in mutations:
                self.fixture(root,mutation)
                with self.assertRaises(ValueError):check_candidate(root,True)
    def test_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:self.assertFalse(check_candidate(Path(tmp),False)['enabled'])

class NativeAggregateOracle(unittest.TestCase):
    def test_sample_eviction_and_true_errors(self):
        zero_keys=['open_interval_keys','queue_observations_open','queue_unmatched','queue_order_errors','queue_depth_errors','grant_outcomes_unmatched','grant_start_overwrites','grant_starts_open']
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);status=dict(enabled=True,incomplete=False,tail_overwrites=138555,**{k:0 for k in zero_keys})
            write(p/'diagnostic-status.json',status)
            (p/'diagnostic-native-aggregates.csv').write_text('metric,node,port,class,count,sum,max\n2,0,0,0,3,15000,5000\n10,0,0,0,1,5000,5000\n8,0,0,0,1,5000,5000\n9,0,0,0,1,5000,5000\n4,0,0,0,1,1000,1000\n')
            result=native_accounting(p);self.assertEqual(result['status'],'PASS');self.assertFalse(result['rolling_tail_complete'])
            for key in zero_keys+['incomplete']:
                write(p/'diagnostic-status.json',dict(status,**{key:1}))
                with self.assertRaises(ValueError):native_accounting(p)
            write(p/'diagnostic-status.json',status)
            with (p/'diagnostic-native-aggregates.csv').open('a') as stream:stream.write('2,0,0,0,1,5000,5000\n')
            with self.assertRaises(ValueError):native_accounting(p)

if __name__=='__main__':unittest.main()
