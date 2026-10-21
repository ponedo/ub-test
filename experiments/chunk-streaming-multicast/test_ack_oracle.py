#!/usr/bin/env python3
"""Pure synthetic checker regression; these tests are not native runtime evidence."""
import copy
import unittest
import ack_oracle as oracle


def evidence():
    drop=dict(kind='drop',node='0',port='0',task='128',src_tpn='9',dst_tpn='2',psn='9',payload_bytes='0',time_ps='100')
    originals=[dict(kind='first_native',task=str(task),src_tpn='2',dst_tpn='9',psn=str(psn),time_ps=str(psn)) for task,psn in [(128,9),(130,10),(132,11)]]
    state=dict(source='0',target='1',tpn='2',send_una='12',send_nxt='12',unacked='0',descriptors='0',timer='0',active_wqes='0',ta_una='12',ta_nxt='12')
    reverse=dict(state,source='1',target='0',tpn='9')
    physical=[dict(kind='tpack',task='130',source='1',target='0',psn='10',offset=str(2**32-1),uid='275',event=event,node=str(node),port=str(port),time_ps=str(time)) for event,node,port,time in [('tx_start',1,0,110),('rx',8,1,120),('tx_start',8,0,130),('rx',0,0,140)]]
    physical += [dict(kind='tpack',task='128',source='1',target='0',psn='9',offset=str(2**32-1),uid='239',event=event,node=str(node),port=str(port),time_ps=str(time)) for event,node,port,time in [('tx_start',1,0,70),('rx',8,1,80),('tx_start',8,0,90),('rx',0,0,100)]]
    return drop,originals,physical,[state,reverse],8


class AckOracleContracts(unittest.TestCase):
    def test_allows_cross_task_same_tp_covering_ack(self):
        result=oracle.check_cumulative_ack(*evidence())
        self.assertEqual(result['lost_task'],128);self.assertEqual(result['covering_acks'][0]['task'],130)
        self.assertEqual(result['covering_acks'][0]['covered_original_tasks'],[128,130])
        self.assertEqual(result['terminal_send_una'],12)

    def test_rejects_unrelated_tp_even_with_larger_ack(self):
        args=list(evidence())
        for row in args[2]:row['source']='2'
        with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)

    def test_rejects_unobserved_psn_and_old_ack(self):
        for psn in ('8','13'):
            args=list(evidence())
            for row in args[2]:row['psn']=psn
            with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)

    def test_rejects_unrelated_task_tag(self):
        args=list(evidence())
        for row in args[2]:
            if row['uid']=='275':row['task']='132'
        with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)

    def test_rejects_incomplete_route_and_uid_mix(self):
        args=list(evidence());args[2].pop()
        with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)
        args=list(evidence());args[2][3]['uid']='different'
        with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)

    def test_requires_window_advancement_and_safe_native_state(self):
        for key,value in [('send_una','9'),('timer','1'),('unacked','1'),('descriptors','1'),('active_wqes','1')]:
            args=list(evidence());args[3][0][key]=value
            with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)

    def test_modular_coverage_wrap_math_is_pure_not_live_wrap(self):
        mod=oracle.PSN_MOD
        self.assertEqual(oracle.lift_before(mod-1,mod+2),mod-1)
        self.assertEqual(oracle.lift_before(0,mod+2),mod)
        self.assertEqual(oracle.lift_before(1,mod+2),mod+1)
        with self.assertRaises(ValueError):oracle.lift_before(2,mod+2)

    def test_exact_lost_ack_ingress_and_uid_path(self):
        for key,value in [('time_ps','101'),('node','1'),('port','1')]:
            args=list(evidence());args[0][key]=value
            with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)
        args=list(evidence());args[2][-1]['uid']='different'
        with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)

    def test_no_generic_retry_flag_or_completion_substitute(self):
        args=list(evidence());args[2].clear()
        args[1].append(dict(kind='native_retry',task='999',src_tpn='3',dst_tpn='17',psn='7',time_ps='200'))
        with self.assertRaises(ValueError):oracle.check_cumulative_ack(*args)

if __name__=='__main__':unittest.main(verbosity=2)
