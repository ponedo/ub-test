#!/usr/bin/env python3
"""Fresh old-mode executions against the same native library; compare semantic outputs."""
import argparse,json,hashlib,sys,subprocess,resource
from pathlib import Path
H=Path(__file__).resolve().parent;E=H.parent
sys.path.insert(0,str(E/'wqe-completion-fix'));from guard import run
p=argparse.ArgumentParser()
for k in ['stage-a','native','legacy-build','v2-build','retx-build','out']:p.add_argument('--'+k,type=Path,required=True)
a=p.parse_args();o=a.out.resolve();o.mkdir(parents=True,exist_ok=False);resource.setrlimit(resource.RLIMIT_CORE,(0,0));rows=[]
def stage(cmd,path):
 r=run(cmd,path,3600,case=o);assert r['status']=='PASS',str(path);return r
for binary in [a.legacy_build/'pair-layer',a.v2_build/'micro',a.retx_build/'micro']:
 dynamic=subprocess.check_output(['readelf','-d',binary],text=True);assert str(a.native.resolve()/'build/lib') in dynamic,'wrong native library RPATH'
fields=['layer_latency_ps','remote_WQEs','TA_count','target_segments','sender_completions','completed_tokens','assignments','replicas','jettys','combine_fnv1a64','executed_graph_fnv1a64','max_npu_load','per_npu_load','verified_bytes','remote_bytes','local_bytes','packet_tx_per_node','packet_rx_per_node','byte_tx_per_node','byte_rx_per_node','timeline','stage_intervals','compute_intervals']
for case in json.loads((a.stage_a/'stage-a-status.json').read_text())['cases']:
 for mode in ['no-balancing','direct','chunk-streaming']:
  source=a.stage_a/case/mode;dest=o/'application'/case/mode
  host=stage([a.legacy_build.resolve()/'pair-layer','--input='+str(source.resolve()/'input.txt'),'--out='+str(dest),'--jettyMode=pair','--logLevel=summary'],dest/'host')
  old=json.loads((dest/'online-summary.json').read_text());new=json.loads((source/'online-summary.json').read_text())
  for k in fields:assert old[k]==new[k],(case,mode,k)
  rows.append(dict(case=case,mode=mode,status='EXACT_MATCH',fields=fields,wall_seconds=host['wall_seconds']));(o/'application-parity.json').write_text(json.dumps(rows,indent=2)+'\n')
stage([sys.executable,E/'ub-multicast-v2/run.py','--build',a.v2_build.resolve(),'--out',o/'v2'],o/'v2-host')
x=json.loads((E/'ub-multicast-v2/results/microbench.json').read_text());y=json.loads((o/'v2/results.json').read_text());fields=['case','mode','bytes','source_data_bytes','switch_data_bytes','source_packets','branches','group_complete_ps','receiver_ready_ps','sender_complete_ps','blocked_queries','peak_egress_bytes'];assert len(x)==len(y)==14
for a0,b0 in zip(x,y):
 for k in fields:assert a0[k]==b0[k],(a0['case'],k)
for case in ['normal','data-once','ack-once','response-once']:
 stage([sys.executable,E/'ub-multicast-retransmission/run.py','--build',a.retx_build.resolve(),'--out',o/('retx-'+case),'--case',case],o/('retx-'+case+'-host'))
(o/'status.json').write_text(json.dumps(dict(status='PASS',application_cases=len(rows),v2_cases=14,retransmission_cases=4,native_sha256=hashlib.sha256((a.native/'build/lib/libns3.44-unified-bus.so').read_bytes()).hexdigest()),indent=2)+'\n')
