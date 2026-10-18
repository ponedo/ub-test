#!/usr/bin/env python3
"""Independent receiver-byte and native port/credit evidence verification."""
import csv,hashlib,json
from pathlib import Path

def rows(path):
 return list(csv.DictReader(Path(path).open()))
def verify(root):
 root=Path(root); s=rows(root/'summary.csv')[0];scenario=s['scenario'];direct=int(s['direct'])
 targets=rows(root/'targets.csv'); ports=rows(root/'ports.csv')
 expected={0:{1,2,3}}
 if scenario=='dynamic':expected={0:{1,2},1:{2,3}}
 if scenario in ['competition','pressure']:expected[1]={1}
 actual={(int(t['object']),int(t['rank'])) for t in targets}
 assert len(actual)==len(targets) and actual=={(o,r) for o,rs in expected.items() for r in rs},'membership/duplicate target'
 hashes=[]
 for t in targets:
  o=int(t['object']);r=int(t['rank']);source=(root/f'source-object{o}.bin').read_bytes();recv=(root/f'rank{r}-object{o}.bin').read_bytes()
  assert recv==source,'payload mismatch'
  assert len(recv)==int(t['payload_bytes']) and (len(recv)+1023)//1024==int(t['packets']),'size/count'
  assert int(t['complete_ns'])>100,'premature completion'
  hashes.append(dict(rank=r,object=o,payload_bytes=len(recv),sha256=hashlib.sha256(recv).hexdigest(),source_sha256=hashlib.sha256(source).hexdigest()))
  assert len(recv)>0
 assert len(ports)==10
 p={(int(x['rank']),int(x['port'])):{k:int(v) for k,v in x.items()} for x in ports}
 assert len(p)==len(ports),'duplicate port'
 for n in range(5):
  a=p[n,0];b=p[5,n]
  assert a['data_tx_bytes']==b['data_rx_bytes'] and a['data_rx_bytes']==b['data_tx_bytes'],'link byte conservation'
  assert a['credit_consumed']==b['credit_returned'] and b['credit_consumed']==a['credit_returned'],'link credit conservation'
 for x in p.values():
  assert x['credit_consumed']==x['credit_restored'],'credit not restored'
  assert x['credit_free']==int(s['initial_credit_cells']) and x['credit_pending']==0,'credit final'
  assert x['egress_peak']<=int(s['egress_bytes']),'egress capacity'
 main=(root/'source-object0.bin').stat().st_size
 src_payload=sum((root/f'source-object{o}.bin').stat().st_size*(len(rs) if direct else 1) for o,rs in expected.items() if not(scenario in ['competition','pressure'] and o==1))
 src_packets=sum(((root/f'source-object{o}.bin').stat().st_size+1023)//1024*(len(rs) if direct else 1) for o,rs in expected.items() if not(scenario in ['competition','pressure'] and o==1))
 assert p[0,0]['data_tx_bytes']==src_payload+4*src_packets,'source copy count'
 total_parents=sum(p[n,0]['data_tx_packets'] for n in range(5));total_branches=sum(p[5,n]['data_tx_packets'] for n in range(5))
 assert total_parents==int(s['parents']) and total_branches==int(s['branches']),'parent/branch count'
 assert int(s['upstream_return_bytes'])==sum(p[5,n]['data_rx_bytes'] for n in range(5)),'upstream returned once'
 assert int(s['ingress_peak'])<=int(s['reserve_bytes']),'ingress capacity'
 if scenario=='pressure':assert int(s['blocked_queries'])>0,'no actual backpressure'
 return dict(status='PASS',scenario=scenario,direct=bool(direct),source_payload_bytes=src_payload,source_data_wire_bytes=p[0,0]['data_tx_bytes'],source_all_wire_bytes=p[0,0]['wire_tx_bytes'],completion_ns=max(int(x['complete_ns']) for x in targets),primary_object_completion_ns=max(int(x['complete_ns']) for x in targets if int(x['object'])==0),primary_object_completion_ps=max(int(x['complete_ps']) for x in targets if int(x['object'])==0),hashes=hashes)
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);ap.add_argument('--out',type=Path);a=ap.parse_args();v=verify(a.directory)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps(v))
