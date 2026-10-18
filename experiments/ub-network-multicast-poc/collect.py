#!/usr/bin/env python3
"""Collect compact summaries only; never copy raw receiver payloads or full host snapshots."""
import argparse,csv,json
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('collected',type=Path);p.add_argument('out',type=Path);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 data=json.loads((a.collected/'results.json').read_text())
 for name in ['summary','ports','targets','arbitration']:
  result=[]
  for d in data:
   case=d['case']
   for r in csv.DictReader((a.collected/case/(name+'.csv')).open()):result.append({'case':case,**r})
  with (a.out/(name+'.csv')).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=result[0]);w.writeheader();w.writerows(result)
 with (a.out/'performance.csv').open('w',newline='') as f:
  keys=['case','scenario','direct','source_payload_bytes','source_data_wire_bytes','source_all_wire_bytes','completion_ns','primary_object_completion_ns','primary_object_completion_ps','wall_seconds','cpu_seconds','peak_rss_kib','status']
  w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows({k:d[k] for k in keys} for d in data)
 (a.out/'verification.json').write_text(json.dumps(data,indent=2)+'\n')
 (a.out/'negative.json').write_text((a.collected/'negative.json').read_text())
 print('Compact results:',len(data),'positive cases')
if __name__=='__main__':main()
