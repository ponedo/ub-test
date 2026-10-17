#!/usr/bin/env python3
"""Independent strict application oracle plus Pair Jetty completion/identity checks."""
import csv,importlib.util,json,sys
from pathlib import Path
H=Path(__file__).resolve().parent

def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def verify(path, mode=None):
 path=Path(path)
 v=load('forward_verify',H.parent/'multi-npu-relay/verify.py')
 summary=v.verify(path)
 (path/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 target={};sender={};admitted={};task_jetties={};active={};peak={}
 config=json.loads((path/'config.json').read_text());transfers=config['transfers']
 with (path/'events.csv').open() as f:
  for x in csv.DictReader(f):
   task=int(x['task']);t=int(x['time_ps'])
   if task>=0 and transfers[task]['source']!=transfers[task]['target']:
    pair=(transfers[task]['source'],transfers[task]['target'])
    if x['event']=='send':active[pair]=active.get(pair,0)+1;peak[pair]=max(peak.get(pair,0),active[pair])
    if x['event']=='sender_complete':active[pair]-=1
   if x['event']=='target_complete':target[task]=max(target.get(task,-1),t)
   if x['event']=='sender_complete':
    if task in sender:raise ValueError('duplicate sender completion')
    sender[task]=t
 with (path/'ta-identity.csv').open() as f:
  for x in csv.DictReader(f):
   task=int(x['task']);ssn=int(x['logical_ssn']);off=int(x['offset']);length=int(x['bytes'])
   jetty=int(x['jetty']);task_jetties.setdefault(task,jetty)
   if task_jetties[task]!=jetty:raise ValueError('task changed Jetty')
   key=(task,ssn)
   if key in admitted:raise ValueError('duplicate task/SSN admission')
   admitted[key]=(off,length)
 if target.keys()!=sender.keys():raise ValueError('target/sender task mismatch')
 if any(sender[k]<t for k,t in target.items()):raise ValueError('early sender success')
 metrics=json.loads((path/'simulator-metrics.json').read_text())
 if len(admitted)!=metrics['TA_count']:raise ValueError('TA count mismatch')
 pairs={};stages={}
 for task,jetty in task_jetties.items():
  x=transfers[task];pair=(x['source'],x['target']);pairs.setdefault(pair,set()).add(jetty);stages.setdefault(pair,set()).add(x['stage'])
  if mode=='pair' and jetty!=x['source']*config['planner_input']['npus']+x['target']+1:raise ValueError('pair Jetty identity')
  if mode=='per-wqe' and jetty!=task:raise ValueError('legacy Jetty identity')
 if mode=='pair' and (any(len(v)!=1 for v in pairs.values()) or metrics['jettys']!=len(pairs)):raise ValueError('pair Jetty resource count')
 if mode=='per-wqe' and metrics['jettys']!=len(sender):raise ValueError('legacy Jetty resource count')
 if any(active.values()):raise ValueError('pending application WQE')
 logical=load('logical',H.parent/'jetty-resource-mapping/harness.py').logical(path)
 (path/'pair-validation.json').write_text(json.dumps({'status':'PASS','checked_sender_completions':len(sender),'checked_TAs':len(admitted),'mapping_mode':mode,'directed_pairs':len(pairs),'pairs_sharing_communication_stages':sum(len(v)>1 for v in stages.values()),'pairs_sharing_weight_and_tokens':sum(2 in v and bool(v&{0,1}) for v in stages.values()),'max_submitted_incomplete_WQEs_per_pair':max(peak.values(),default=0),'logical':logical},indent=2)+'\n')
 return summary
if __name__=='__main__':print(json.dumps(verify(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None),indent=2))
