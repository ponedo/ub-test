#!/usr/bin/env python3
"""CSV adapter for pinned tools' legacy .tr-only parser; no transport changes."""
import csv,json,sys
from pathlib import Path
case=Path(sys.argv[1]); output=Path(sys.argv[2])
tasks=list(csv.DictReader(open(case/'traffic.csv')))
traces={}
for p in (case/'runlog').glob('TaskTrace_node_*.csv'):
    traces[int(p.stem.split('_')[-1])]=list(csv.DictReader(open(p)))
result=[]
for t in tasks:
    tid=t['taskId']; src=int(t['sourceNode']); dst=int(t['destNode'])
    local=[r for r in traces[src] if r['task_id']==tid]
    starts=[int(r['time_ps']) for r in local if r['event']=='WQE Starts']
    ends=[int(r['time_ps']) for r in local if r['event']=='WQE Completes']
    assert len(starts)==len(ends)==1 and ends[0]>starts[0],(tid,'no unique completion')
    target=[r for r in traces[dst] if r['task_id']==tid and r['event']=='WQE Segment Completes']
    ssns={r['ta_ssn'] for r in target}
    assert len(ssns)==7,(tid,'target TA segments missing')
    result.append({'task':int(tid),'start_ps':starts[0],'sender_complete_ps':ends[0],
                   'target_unique_ta_ssns':len(ssns),'target_trace_rows':len(target),
                   'target_last_segment_trace_ps':max(int(r['time_ps']) for r in target)})
ack_files=list((case/'runlog').glob('AllPacketTrace_ACK_*.csv'))
ack_rows=sum(sum(1 for _ in csv.DictReader(open(p))) for p in ack_files)
assert ack_rows>0
report={'cause':'Pinned tools glob *.tr and parse old prose; model emits CSV with integer time_ps.',
        'tasks':result,'raw_ACK_rows_including_duplicates':ack_rows,
        'boundary':'Target segment trace follows HandleInboundTaUnit; it is not an executor-done trace. WQE completion is sender-side evidence; three-node events instrument executor completion explicitly.'}
output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
