#!/usr/bin/env python3
"""Scoped post-hoc plain TPACK oracle; no runtime/protocol/old-verdict mutation."""
import argparse
from common import *
from phase_b import csv_rows, ordered_route

PSN_BITS=24
PSN_MOD=1<<PSN_BITS


def lift_before(wire,upper):
    require(type(wire) is int and 0<=wire<PSN_MOD and upper>0,'ACK wire PSN bounds')
    value=(upper//PSN_MOD)*PSN_MOD+wire
    if value>=upper:value-=PSN_MOD
    require(value>=0 and 0<upper-value<PSN_MOD//2,'Ambiguous/out-of-window modular ACK')
    return value


def check_cumulative_ack(drop,originals,physical,states,n):
    """Require same directed TP, real covering originals/path, and final progress.

    The runtime trace has no per-ACK sndUna transition for this selected-detail
    configuration. Therefore this proves observed covering cumulative ACKs plus
    terminal advancement, NOT the exact instant each ACK changed the window.
    """
    task=int(drop['task']);lost_wire=int(drop['psn']);when=int(drop['time_ps'])
    require(drop['kind']=='drop' and int(drop['payload_bytes'])==0,'Not a plain TPACK-loss record')
    reverse_tpn,forward_tpn=int(drop['src_tpn']),int(drop['dst_tpn'])
    forward=[r for r in states if int(r['tpn'])==forward_tpn]
    reverse=[r for r in states if int(r['tpn'])==reverse_tpn]
    require(len(forward)==len(reverse)==1,'Unique native directed TP identity missing')
    state,peer=forward[0],reverse[0];source,target=int(state['source']),int(state['target'])
    require((int(peer['source']),int(peer['target']))==(target,source),'ACK belongs to unrelated directed TP')
    require(forward_tpn==source*n+target+1 and reverse_tpn==target*n+source+1,'Physical recorder TP-rank mapping changed')
    terminal=int(state['send_una'])
    require(terminal==int(state['send_nxt']),'Sender native window not drained')
    require(all(int(state[k])==0 for k in ('unacked','descriptors','timer','active_wqes')) and state['ta_una']==state['ta_nxt'],'Sender native descriptors/timer/WQEs not safe')
    lost=lift_before(lost_wire,terminal)
    sent={}
    for row in originals:
        if row['kind']!='first_native' or int(row['src_tpn'])!=forward_tpn or int(row['dst_tpn'])!=reverse_tpn:continue
        logical=lift_before(int(row['psn']),terminal)
        require(logical not in sent,'Duplicate original native PSN evidence')
        sent[logical]=row
    require(lost in sent and int(sent[lost]['task'])==task and int(sent[lost]['time_ps'])<when,'Lost TPACK does not name an observed original native PSN')
    dropped_rx=[row for row in physical if row['kind']=='tpack' and row['event']=='rx'
                and int(row['time_ps'])==when and int(row['node'])==source
                and int(row['port'])==int(drop['port']) and int(drop['node'])==source
                and (int(row['source']),int(row['target']))==(target,source)
                and int(row['task'])==task and int(row['psn'])==lost_wire]
    require(len(dropped_rx)==1,'Dropped ACK lacks exact ingress identity')
    lost_uid=dropped_rx[0]['uid']
    lost_route=ordered_route([row for row in physical if row['uid']==lost_uid],task,target,source,n,kind='tpack',psn=lost_wire)
    require(lost_route and lost_route[-1]==when,'Dropped ACK lacks UID-matched physical path')
    proofs=[]
    for packet in physical:
        if packet['kind']!='tpack' or packet['event']!='rx' or int(packet['node'])!=source or int(packet['time_ps'])<=when:continue
        if (int(packet['source']),int(packet['target']))!=(target,source):continue
        covering=lift_before(int(packet['psn']),terminal)
        if covering<lost or covering not in sent:continue
        if int(packet['task'])!=int(sent[covering]['task']):continue
        if not all(psn in sent for psn in range(lost,covering+1)):continue
        route=ordered_route([row for row in physical if row['uid']==packet['uid']],int(packet['task']),target,source,n,kind='tpack',after=when,psn=int(packet['psn']))
        if not route:continue
        proofs.append(dict(task=int(packet['task']),wire_psn=int(packet['psn']),logical_psn=covering,uid=packet['uid'],physical_path_ps=route,
                           covered_original_tasks=[int(sent[psn]['task']) for psn in range(lost,covering+1)]))
    require(proofs,'No later same-TP cumulative ACK with observed covering PSNs and complete physical path')
    return dict(status='PASS',source=source,target=target,forward_tpn=forward_tpn,reverse_tpn=reverse_tpn,
        lost_task=task,lost_wire_psn=lost_wire,lost_logical_psn=lost,drop_time_ps=when,drop_uid=lost_uid,drop_physical_path_ps=lost_route,
        covering_acks=proofs,terminal_send_una=terminal,terminal_send_nxt=int(state['send_nxt']),
        native_retry_required=False,coverage={'fault_tpack':True},
        limitation='Per-ACK instantaneous sndUna transitions were not selected. Evidence proves covering same-TP physical ACKs and safe terminal advancement, not the exact advancement timestamp.')


def check_directory(directory):
    directory=Path(directory);c=read(directory/'config.json');life=read(directory/'hybrid-lifecycle.json')
    require(read(directory/'independent.json')['status']=='PASS' and read(directory/'validation.json')['status']=='PASS','Original independent/online runtime checks missing')
    require(life['all_native_pairs_safe'] is True and life['injected_losses']==1 and life['injected_duplicates']==0,'Not one safely-drained native feedback-loss case')
    wire=csv_rows(directory,'weight-packets.csv');drops=[r for r in wire if r['kind']=='drop']
    require(len(drops)==1,'Exactly one loss required')
    # This receipt is deliberately fixture-bound, not a general resumability or
    # PSN-wrap claim. The selected native TP has exactly original PSNs 0..11.
    drop=drops[0];forward=int(drop['dst_tpn']);reverse=int(drop['src_tpn'])
    originals=[r for r in wire if r['kind']=='first_native' and int(r['src_tpn'])==forward and int(r['dst_tpn'])==reverse]
    require(sorted(int(r['psn']) for r in originals)==list(range(12)),'F03 no-wrap original PSN 0..11 bound changed')
    result=check_cumulative_ack(drop,wire,csv_rows(directory,'hybrid-physical.csv'),csv_rows(directory,'pair-state.csv'),c['planner_input']['npus'])
    require(result['terminal_send_nxt']==12,'F03 no-wrap terminal bound changed')
    require(result['lost_wire_psn']==9 and result['lost_task']==128 and (forward,reverse)==(2,9),'F03 selected loss identity changed')
    result['fixture_bound_no_wrap_psns']=list(range(12))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();before=freeze(path for path in args.directory.iterdir() if path.is_file());result=check_directory(args.directory);check(before)
    result.update(kind='POSTHOC_ORACLE_CORRECTION_NO_SIMULATOR_RERUN',source_identity=before);write(args.out,result);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
