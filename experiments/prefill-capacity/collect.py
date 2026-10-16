#!/usr/bin/env python3
"""Stream raw evidence into trace-derived counters; never promote partial runs."""
import collections,csv,hashlib,json,shutil,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'evidence';RAW=Path('/workspace/prefill-capacity-raw')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
ledger=json.loads((OUT/'run-ledger.json').read_text());table=[]
for entry in ledger:
 case=Path(entry['raw_dir']);folder=case/'run';metrics=dict(case_id=entry['case_id'],status=entry['status'],reason=entry.get('reason',''),requested_tokens=entry['tokens'],requested_assignments=entry['assignments'],mode=entry['mode'])
 for stage in ['generate','planner','adapter','ns3','verify']:
  result=entry.get('stages',{}).get(stage,{});metrics[stage+'_wall_s']=result.get('wall_seconds');metrics[stage+'_peak_rss_kib']=result.get('peak_rss_kib');metrics[stage+'_tree_rss_bytes']=result.get('sampled_peak_tree_rss_bytes');metrics[stage+'_status']=result.get('status','not_run');metrics[stage+'_user_cpu_s']=result.get('user_cpu_seconds');metrics[stage+'_system_cpu_s']=result.get('system_cpu_seconds')
  source=case/'stages'/stage
  if source.exists():shutil.copytree(source,OUT/'runs'/entry['case_id']/stage,dirs_exist_ok=True)
 counts=collections.Counter();tokens_done=set();eventrows=0;truncated=0;end=None;start=None
 if (folder/'events.csv').exists():
  with (folder/'events.csv').open() as f:
   for row in csv.DictReader(f):
    if None in row.values() or None in row:truncated+=1;continue
    try:t=int(row['time_ps']);int(row['task'])
    except (TypeError,ValueError):truncated+=1;continue
    counts[row['event']]+=1;eventrows+=1
    if row['event']=='layer_start':start=t
    if row['event']=='layer_end':end=t
    if row['event']=='token_complete':tokens_done.add(int(row['id']))
 tasks=remote=expected_ta=actual_assignments=0;max_task=None;input_tokens=None;input_k=None
 if (folder/'input.txt').exists():
  with (folder/'input.txt').open() as f:header=f.readline().split();input_tokens=int(header[3]);input_k=int(header[2])
 if (folder/'transfers.csv').exists():
  with (folder/'transfers.csv').open() as f:
   for row in csv.DictReader(f):
    tasks+=1;max_task=int(row['task']);actual_assignments+=int(row['stage']=='0')
    if row['source']!=row['target']:remote+=1;expected_ta+=(int(row['bytes'])+1023)//1024
 sim=json.loads((folder/'simulator-metrics.json').read_text()) if (folder/'simulator-metrics.json').exists() else {}
 metrics.update(input_tokens=input_tokens,input_top_k=input_k,actual_generated_assignments=actual_assignments if tasks else None,generated_tasks=tasks or None,generated_remote_WQEs=remote or None,expected_request_TAs=expected_ta or None,max_task_id=max_task,actual_target_received_TAs=counts.get('target_received') if eventrows else None,actual_sender_completed_WQEs=counts.get('sender_complete') if eventrows else None,application_event_rows=eventrows or None,partial_csv_rows_ignored=truncated,ns3_executed_events=sim.get('simulator_events'),unique_completed_tokens=len(tokens_done) if eventrows else None,layer_latency_ps=end-start if end is not None and start is not None else None,raw_native_log_bytes=sum(p.stat().st_size for p in (folder/'native').rglob('*') if p.is_file()) if (folder/'native').exists() else 0,application_log_bytes=(folder/'events.csv').stat().st_size if (folder/'events.csv').exists() else 0,raw_case_bytes=sum(p.stat().st_size for p in case.rglob('*') if p.is_file()) if case.exists() else 0)
 metrics['strictly_verified']=entry['status']=='success' and (folder/'summary.json').exists();table.append(metrics)
 if folder.exists():
  dest=OUT/'runs'/entry['case_id'];dest.mkdir(parents=True,exist_ok=True)
  inventory={str(p.relative_to(case)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in case.rglob('*') if p.is_file()}
  (dest/'raw-artifacts.json').write_text(json.dumps(inventory,indent=2)+'\n');(dest/'observed-counters.json').write_text(json.dumps(dict(metrics=metrics,application_event_types=counts),indent=2)+'\n')
  for name in ['summary.json','simulator-metrics.json']:
   if (folder/name).exists():shutil.copyfile(folder/name,dest/name)
  # Full synthetic raw artifacts, losslessly compressed; do not silently drop failed evidence.
  archive=OUT/(entry['case_id']+'-raw.tar.gz')
  with tarfile.open(archive,'w:gz',compresslevel=3) as tar:tar.add(case,arcname=entry['case_id'])
  if archive.stat().st_size>=90*1024**2:raise RuntimeError('archive exceeds public-file budget; split losslessly before publishing')
with (OUT/'capacity.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(table[0]),lineterminator='\n');w.writeheader();w.writerows(table)
(OUT/'capacity.json').write_text(json.dumps(table,indent=2)+'\n')
print('collected',len(table),'matrix rows; fully verified',sum(x['strictly_verified'] for x in table))
