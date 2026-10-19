#!/usr/bin/env python3
"""Aggregate measured completed cases only; stopped points are never fabricated."""
import argparse,csv,json
from pathlib import Path

def readcsv(p):
 with p.open() as f:return list(csv.DictReader(f))
def writecsv(p,rows,fields=None):
 fields=fields or list(rows[0]) if rows else (fields or ['status'])
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader();w.writerows(rows)
def main():
 p=argparse.ArgumentParser();p.add_argument('private',type=Path);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True);perf=[];states=[];resources=[];targetrows=[];portrows=[];packetrows=[];queuerows=[];headerrows=[]
 for phase in ['small','main','ideal']:
  lp=a.private/(phase+'-ledger.json')
  if not lp.exists():continue
  for r in json.loads(lp.read_text()):
   states.append({k:r.get(k,'') for k in ['case_id','block','fanout','mode','bytes','status','failure']})
   for stage in ['simulator','postflight']:
    h=r.get(stage+'_host')
    if h:resources.append(dict(case_id=r['case_id'],stage=stage,status=h['status'],started_utc=h['start'],returncode=h['returncode'],wall_seconds=h['wall_seconds'],cpu_seconds=h['user_cpu_seconds']+h['system_cpu_seconds'],peak_rss_kib=h['peak_rss_kib'],guard=h['guard']))
   if r['status']!='PASS':continue
   d=a.private/r['case_id'];s=json.loads((d/'fanout-summary.json').read_text());v=json.loads((d/'postflight.json').read_text());assert v['status']=='PASS'
   packets=readcsv(d/'packet-counts.csv');queues=readcsv(d/'queue-stats.csv');ports=readcsv(d/'ports.csv')
   if phase!='small':
    for source,destrows in [(ports,portrows),(packets,packetrows),(queues,queuerows),(readcsv(d/'header-accounting.csv'),headerrows)]:
     destrows.extend(dict(case_id=r['case_id'],**x) for x in source)
   def num(kind,field):return sum(int(x[field]) for x in packets if x['kind']==kind)
   h=r['simulator_host'];row=dict(case_id=r['case_id'],block=phase,fanout=r['fanout'],mode=r['mode'],weight_bytes=r['bytes'],weight_duration_ps=s['all_receivers_ready_duration_ps'],weight_duration_ms=s['all_receivers_ready_duration_ps']/1e9,sender_complete_ps=s['all_senders_complete_ps'],weight_wqes=s['weight_wqes'],weight_tas=s['weight_tas'],relay_enabled=s['relay_enabled'],main_logical_payload_bytes=s['main_logical_send_bytes'],relay_logical_payload_bytes=s['relay_logical_send_bytes'],source_wire_payload_bytes=s['source_wire_payload_bytes'],source_data_wire_bytes=s['source_data_wire_bytes'],source_header_bytes=s['source_data_wire_bytes']-s['source_wire_payload_bytes'],all_network_wire_bytes=sum(int(x['wire_bytes']) for x in packets),all_network_weight_wire_bytes=num('weight_write','wire_bytes')+num('multicast_data','wire_bytes'),all_network_ack_packets=num('transport_ack','packets'),all_network_response_packets=num('transaction_response','packets'),all_network_credit_packets=num('credit','packets'),egress_residence_ps=sum(int(x['total_egress_residence_ps']) for x in queues),egress_peak_bytes=max(int(x['peak_egress_bytes']) for x in queues),cbfc_blocked_queries=sum(int(x['blocked_queries']) for x in ports),multicast_window_wait_queries=s['multicast_window_wait_queries'],host_wall_seconds=h['wall_seconds'],host_cpu_seconds=h['user_cpu_seconds']+h['system_cpu_seconds'],peak_rss_kib=h['peak_rss_kib'],validation='PASS');perf.append(row)
   for target in readcsv(d/'targets.csv'):targetrows.append(dict(case_id=r['case_id'],**target))
 for row in perf:
  base=next((x for x in perf if x['fanout']==row['fanout'] and x['mode']=='direct' and x['block']==('main' if row['block']=='ideal' else row['block'])),None)
  chunk=next((x for x in perf if x['fanout']==row['fanout'] and x['mode']=='chunk' and x['block']==('main' if row['block']=='ideal' else row['block'])),None)
  row['speedup_vs_direct']=base['weight_duration_ps']/row['weight_duration_ps'] if base else ''
  row['speedup_vs_chunk']=chunk['weight_duration_ps']/row['weight_duration_ps'] if chunk else ''
 writecsv(a.out/'performance.csv',perf);writecsv(a.out/'run-status.csv',states);writecsv(a.out/'host-resources.csv',resources);writecsv(a.out/'targets.csv',targetrows)
 for phase in ['small','main','ideal']:writecsv(a.out/(phase+'-performance.csv'),[r for r in perf if r['block']==phase],list(perf[0]) if perf else ['status'])
 writecsv(a.out/'port-counters.csv',portrows);writecsv(a.out/'packet-kinds.csv',packetrows);writecsv(a.out/'queue-counters.csv',queuerows);writecsv(a.out/'header-accounting.csv',headerrows)
 (a.out/'collection.json').write_text(json.dumps(dict(completed=len(perf),states=len(states),scope='weights-only; actual completed ns-3 events'),indent=2)+'\n')
if __name__=='__main__':main()
