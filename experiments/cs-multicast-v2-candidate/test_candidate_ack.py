#!/usr/bin/env python3
"""Retained evidence and adversarial pure tests, no simulation."""
import copy, unittest
from candidate_ack_oracle import *
ROOT=HERE.parents[2]/'cs-mc-v2-private/high-bandwidth-remaining-validation/runs/V12/v1'
class Ack(unittest.TestCase):
    def test_inflight_and_refusals(self):
        wire=csv_rows(ROOT,'weight-packets.csv');drop=next(r for r in wire if r['kind']=='drop');physical=csv_rows(ROOT,'hybrid-physical.csv');states=csv_rows(ROOT,'pair-state.csv')
        result=check_cumulative_ack(drop,wire,physical,states,8)
        self.assertEqual([r['wire_psn'] for r in result['covering_acks']],[10,11])
        self.assertTrue(all(r['physical_path_ps'][0]<int(drop['time_ps'])<r['physical_path_ps'][-1] for r in result['covering_acks']))
        for mode in ['early_rx','unrelated_tp','missing_hop']:
            ph=copy.deepcopy(physical);st=copy.deepcopy(states)
            if mode=='early_rx':
                for r in ph:
                    if r['uid'] in ['219','227'] and r['event']=='rx' and r['node']=='0':r['time_ps']=str(int(drop['time_ps'])-1)
            elif mode=='unrelated_tp':
                for r in st:
                    if r['tpn']=='2':r['target']='2'
            else:ph=[r for r in ph if not (r['uid'] in ['219','227'] and r['event']=='tx_start' and r['node']=='8')]
            with self.assertRaises(ValueError):check_cumulative_ack(drop,wire,ph,st,8)
if __name__=='__main__':unittest.main()
