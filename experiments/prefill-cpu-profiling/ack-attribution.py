#!/usr/bin/env python3
import csv,json
from pathlib import Path
H=Path(__file__).resolve().parent
rows=[]
for a in [5000,10000,20000,50000]:
 d=json.loads((H/f'evidence/analysis/{a}-timed/summary.json').read_text());t={x['name']:x for x in d['timers']};c=d['counters']
 nested=lambda name:t[name]['inclusive_thread_cpu_ns']-t[name]['exclusive_thread_cpu_ns']
 jets=t['CreateJettyBound']['calls_or_count'];pairs=t['AppPair']['calls_or_count'];windows=jets+2*pairs
 assert c['AckCapacityGrowthRequests']==windows
 assert t['AckResize']['calls_or_count']==3*windows and t['AckReset']['calls_or_count']==windows
 assert c['AckResizeSlots']==2*windows*2048 and c['AckResetSlots']==windows*2048
 ack=nested('CreateObjectJetty')+nested('JettyInit');tp=nested('AppPair');dispose=nested('AppSimulatorDestroy')
 assert ack+tp+dispose==t['AckResize']['inclusive_thread_cpu_ns']+t['AckReset']['inclusive_thread_cpu_ns']
 rows.append(dict(assignments=a,jetty_windows=jets,tp_windows=2*pairs,jetty_slot_payload_bytes=jets*2048*8,tp_slot_payload_bytes=2*pairs*2048*8,jetty_logical_initialization_write_bytes=jets*3*2048*8,jetty_ack_initialization_cpu_seconds=ack/1e9,tp_window_initialization_cpu_seconds=tp/1e9,all_window_disposal_resize_cpu_seconds=dispose/1e9,jetty_creation_cpu_seconds=t['CreateJettyBound']['inclusive_thread_cpu_ns']/1e9,jetty_register_cpu_seconds=t['RegisterJetty']['inclusive_thread_cpu_ns']/1e9))
with (H/'evidence/analysis/ack-attribution.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print('ACK owner partition and timer totals reconcile at all scales')
