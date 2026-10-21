#!/usr/bin/env python3
"""Fresh Phase B reproduction with the reviewed F03 cumulative-ACK correction.

Reuse the original prepared matrix, approval gates, resource guards, execution
loop, negative oracles and parity checks. No archival evidence is imported and
no simulator execution is skipped. Existing frozen files remain untouched.
"""
import ack_oracle
import phase_b
from common import Path, require, write

_ORIGINAL_FAULT_WITNESS=phase_b.fault_witness


def fault_witness(directory,row,config,physical,lifecycle):
    if row['fault']!='ack-once':
        return _ORIGINAL_FAULT_WITNESS(directory,row,config,physical,lifecycle)
    # The additive oracle is intentionally fixture-bound: original PSNs 0..11,
    # lost task128/PSN9/TP9->2. Do not silently generalize to arbitrary ACK modes.
    require(row['id']=='F03' and row['fault_role']=='stage1' and row['required_witnesses']==['fault_tpack'],
            'Cumulative ACK correction is scoped to declared F03 only')
    wire=phase_b.csv_rows(directory,'weight-packets.csv')
    injected=[r for r in wire if r['kind']=='drop']
    require(len(injected)==1,'Fault selector did not inject exactly once')
    task=int(injected[0]['task'])
    group=next(g for g in config['hybrid_groups'] if any(m['task']==task for m in g['members']))
    require(group['graph_role']==row['fault_role'],'Fault injected on wrong graph hop')
    require(len(group['members'])>1,'Fault requires real multi-target operation')
    proof=ack_oracle.check_directory(directory)
    require(proof['status']=='PASS' and proof['coverage']=={'fault_tpack':True},'Incomplete cumulative ACK proof')
    write(Path(directory)/'f03-cumulative-ack-witness.json',dict(proof,kind='FRESH_RUNTIME_CUMULATIVE_ACK_WITNESS'))
    return proof['coverage']


def main():
    original=phase_b.fault_witness
    phase_b.fault_witness=fault_witness
    try:
        phase_b.main()
    finally:
        phase_b.fault_witness=original


if __name__=='__main__':main()
