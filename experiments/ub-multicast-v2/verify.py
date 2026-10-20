#!/usr/bin/env python3
"""Independent bounded checks on actual bytes, events and physical credit evidence."""
import argparse,csv,json,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('case',type=Path);a=p.parse_args();r=a.case
if not __debug__:raise RuntimeError('Assertions must remain enabled')
summary=json.loads((r/'summary.json').read_text());assert summary['status']=='PASS'
events=list(csv.DictReader((r/'events.csv').open()));wire=list(csv.DictReader((r/'wire.csv').open()));ports=list(csv.DictReader((r/'ports.csv').open()))
objects={}
for row in csv.DictReader((r/'payloads.csv').open()):
 task,rank,n=map(int,[row['task'],row['rank'],row['bytes']]);objects[task]=n;actual=(r/f'payload-{task}-{rank}.bin').read_bytes();expected=bytes((task*73+i*131+(i>>8)*17)%251 for i in range(n));assert actual==expected
 times={kind:[int(e['time_ps']) for e in events if e['event']==kind and int(e['task'])==task and int(e['rank'])==rank] for kind in ['receiver_ready','sender_complete']}
 assert len(times['receiver_ready'])==len(times['sender_complete'])==1;assert times['sender_complete'][0]>=times['receiver_ready'][0]
 group=[int(e['time_ps']) for e in events if e['event']=='group_complete' and int(e['task'])==task];assert len(group)==1 and group[0]>=times['sender_complete'][0]
 cover=sorted((int(e['offset']),int(e['bytes'])) for e in events if e['event']=='target_complete' and int(e['task'])==task and int(e['rank'])==rank)
 off=0
 for start,size in cover:assert start==off;off+=size
 assert off==n
assert summary['source_payload_bytes']==sum(objects.values())
if summary['association_restored']:
 assert summary['association_restored']==summary['branches']==summary['native_header_checks']
for row in ports:
 n,port=int(row['node']),int(row['port']);peer=(5,n) if n!=5 else (port,0)
 other=next(q for q in ports if (int(q['node']),int(q['port']))==peer)
 assert int(row['consumed'])==int(other['returned'])
 assert int(row['consumed'])==int(row['restored'])+int(other['pending'])
data=[w for w in wire if w['event']=='tx' and w['packet_class']=='multicast_data' and int(w['node'])==0]
assert sum(int(w['bytes']) for w in data)==summary['source_data_wire_bytes'];assert len(data)==summary['envelopes'];assert summary['input_release_bytes']==summary['source_data_wire_bytes']
print(json.dumps({'status':'PASS','payload_files':len(list(r.glob('payload-*.bin'))),'source_wire':summary['source_data_wire_bytes'],'source_packets':len(data),'switch_data_wire':sum(int(w['bytes']) for w in wire if w['event']=='tx' and int(w['node'])==5 and w['packet_class'] in ['multicast_data','write'] and w['task']!='9001')}))
