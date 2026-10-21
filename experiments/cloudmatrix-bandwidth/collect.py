#!/usr/bin/env python3
"""Strict evidence gate and bounded publication allowlist; raw inputs remain private."""
import argparse
import csv
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
import os
import shutil
from pathlib import Path

H = Path(__file__).resolve().parent
MODES = ['no-balancing', 'direct', 'chunk-streaming', 'multicast-v2']
COMMIT = '3c2275eafea79426a441c819c8b65268492ff08e'

def j(path):
    return json.loads(Path(path).read_text())

def rows(path):
    with Path(path).open() as f:
        return list(csv.DictReader(f))

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')

def host(record):
    keys = ['status', 'guard', 'start', 'wall_seconds', 'user_cpu_seconds',
            'system_cpu_seconds', 'peak_rss_kib', 'sampled_peak_tree_rss_bytes']
    result = {k: record[k] for k in keys}
    result['end_utc'] = (dt.datetime.fromisoformat(record['start']) +
                         dt.timedelta(seconds=record['wall_seconds'])).isoformat()
    return result

def aggregate(directory):
    ex = rows(directory / 'expert-compute.csv')
    active = [x for x in ex if int(x['tokens'])]
    result = {k: sum(int(x[k]) for x in ex) for k in
              ['tokens', 'flops', 'weight_hbm_bytes', 'activation_hbm_bytes', 'total_hbm_bytes', 'duration_ps']}
    result.update(active_experts=len(active), memory_bound_experts=sum(x['bottleneck'] == 'memory' for x in active),
                  compute_bound_experts=sum(x['bottleneck'] == 'compute' for x in active))
    return result

def metrics(summary, directory, rate, origin):
    t, st, ci = summary['timeline'], summary['stage_intervals'], summary['compute_intervals']
    ready = rows(directory / 'expert-ready.csv')
    last = max((int(x['ready_ps']) for x in ready), default=None)
    last_experts = ';'.join(str(x['expert']) for x in ready if int(x['ready_ps']) == last)
    row = dict(link_gbps=rate, evidence_origin=origin,
               planner_ns=(t['planning_end']-t['layer_start'])/1000,
               reroute_ns=(t['reroute_end']-t['planning_end'])/1000,
               weight_ns=(t['weights_end']-t['planning_end'])/1000,
               dispatch_span_ns=(st[0][1]-st[0][0])/1000,
               compute_span_ns=(max(x['end_ps'] for x in ci)-min(x['start_ps'] for x in ci))/1000,
               compute_max_node_ns=max(x['end_ps']-x['start_ps'] for x in ci)/1000,
               combine_span_ns=(st[1][1]-st[1][0])/1000,
               layer_ns=summary['layer_latency_ps']/1000,
               dispatch_gate_ps=t['dispatch_gate'], weights_end_ps=t['weights_end'],
               reroute_end_ps=t['reroute_end'], last_weight_ready_ps=last,
               last_weight_ready_experts=last_experts,
               latest_compute_end_ps=max(x['end_ps'] for x in ci),
               combine_start_ps=st[1][0], combine_end_ps=st[1][1], layer_end_ps=t['layer_end'],
               post_gate_ns=(t['layer_end']-t['dispatch_gate'])/1000,
               after_latest_compute_ns=(t['layer_end']-max(x['end_ps'] for x in ci))/1000)
    assert t['dispatch_gate'] == max(t['weights_end'], t['reroute_end'])
    assert st[1][1] == t['layer_end']
    if ready:
        assert last == t['weights_end']
    row['dispatch_gate_constraint'] = ('weight_and_reroute_tie' if t['weights_end']==t['reroute_end'] else
                                        'weight_ready' if t['weights_end']>t['reroute_end'] else 'reroute')
    return row

def main():
    if not __debug__ or os.environ.get('PYTHONOPTIMIZE'):
        raise RuntimeError('Assertions must remain enabled; unset PYTHONOPTIMIZE and do not use -O')
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--private', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--baseline', type=Path, default=H.parent/'qwen-roofline-compute/results')
    p.add_argument('--source-provenance', type=Path, default=H/'source-provenance.json')
    a = p.parse_args()
    private, out, baseline = a.private.resolve(), a.out.resolve(), a.baseline.resolve()
    real = private/'real-3136'
    ledger, sa, proof = j(real/'ledger.json'), j(private/'stage-a/status.json'), j(real/'baseline-reuse.json')
    units=j(private/'model-unit/status.json')
    assert units['status']=='PASS' and units['positive_cases']==16 and units['negative_cases']==6
    assert ledger['status']==sa['status']==proof['status']=='PASS'
    assert ledger['link_gbps']==3136 and ledger['baseline_link_gbps']==100
    assert [x['strategy'] for x in ledger['runs']]==MODES
    assert sa['small_case_runs']==32 and sa['native_fault_smoke_runs']==3
    assert sa['reference_100_comparisons']==16 and sa['reference_100_status']=='PASS'
    assert all(sa[k] is True for k in ['small_cases_pass','native_rate_probe_pass','fault_smoke_pass'])
    assert sa['link_gbps']==[100,3136] and sa['strategies']==MODES
    probe=j(private/'stage-a/native-rate-probe/console.txt')
    assert probe['status']=='PASS' and probe['rate_bps']==3136000000000 and probe['resolution']=='PS'
    assert [x['bytes'] for x in probe['serialization']]==[1,40,64,159,160,161,1024,4096]
    for sample in probe['serialization']:
        ideal=(sample['bytes']*8*10**12+probe['rate_bps']//2)//probe['rate_bps']
        assert sample['rounded_ideal_ps']==ideal and sample['actual_ps']>0 and abs(sample['actual_ps']-ideal)<=1
    assert [(x['bytes'],x['consumed_cells']) for x in probe['cell_boundaries']]==[(159,1),(160,1),(161,2)]
    link=probe['ordinary_link']
    assert link['propagation_ps']==20000 and link['upper_layer_processing_tested'] is False
    assert link['busy_guard_passed'] is True and link['final_port_idle'] is True
    assert [x['bytes'] for x in link['packets']]==[40,160]
    for packet in link['packets']:
        duration=packet['announced_completion_ps']-packet['send_ps']
        ideal=(packet['bytes']*8*10**12+probe['rate_bps']//2)//probe['rate_bps']
        assert duration>0 and abs(duration-ideal)<=1
        assert packet['observed_receive_ps']==packet['announced_completion_ps']+20000
    assert link['packets'][1]['send_ps']==link['packets'][0]['announced_completion_ps']
    assert sa['binary_identity']==ledger['binary_identity'] and sa['source_identity']==ledger['source_identity']
    for key in ['source_identity','binary_identity']:
        assert ledger[key] and all(sha(path)==digest for path,digest in ledger[key].items()), key
    assert sha(ledger['stage_a_path'])==ledger['stage_a_sha256']
    assert sha(ledger['baseline_evidence_path'])==ledger['baseline_evidence_sha256']==sha(baseline/'summary.json')
    assert all(sha(ledger['input_paths'][k])==v for k,v in ledger['input_identity'].items())
    accepted = j(baseline/'summary.json')
    assert accepted['status']=='PASS' and accepted['native_source_unchanged'] is True
    assert proof['accepted_commit']==COMMIT and proof['source_files_unchanged'] is True
    assert proof['accepted_summary_sha256']==sha(baseline/'summary.json')
    provenance = j(a.source_provenance)
    assert provenance['status']=='PASS' and provenance['accepted_commit']==COMMIT
    assert provenance['project_tracked_diff_empty'] is True and provenance['native_candidate_hashes_verified']==109
    assert provenance['private_source_identity_sha256']==proof['source_identity_sha256']
    native = next(Path(k).parents[2] for k in ledger['binary_identity'] if k.endswith('/libns3.44-unified-bus.so'))
    native_hashes = j(H.parent/'ultraep-multicast-integration/candidate-native-source-sha256.json')
    assert len(native_hashes)==109 and all(sha(native/k)==v for k,v in native_hashes.items())
    assert [x['strategy'] for x in proof['strategies']]==MODES
    for x in proof['strategies']:
        assert x['status']=='EXACT_HASH_MATCH'
        assert {k:v for k,v in x.items() if k!='status'}==next(y for y in accepted['planning_identity'] if y['strategy']==x['strategy'])
    for run in ledger['runs']:
        d = real/run['strategy']
        assert run['status']=='PASS' and j(d/'run-result.json')==run
        for key in ['simulator_host','postflight_host','independent_host','compute_host']:
            assert run[key]['status']=='PASS' and run[key]['guard'] is None
            assert j(d/key.replace('_','-')/'resource.json')==run[key]
        assert all(sha(d/k)==v for k,v in run['immutable_files'].items())
        assert j(d/'compute-validation.json')['status']==j(d/'validation.json')['status']=='PASS'
        assert run['summary']==j(d/'online-summary.json')
        # Equality of actual per-physical-expert work, not merely declared model rates.
        fields=['physical','expert','node','tokens','flops','weight_hbm_bytes','activation_hbm_bytes',
                'total_hbm_bytes','compute_ps','memory_ps','duration_ps','bottleneck']
        strip=lambda rs: sorted(tuple(x[k] for k in fields) for x in rs)
        assert strip(rows(d/'expert-compute.csv'))==strip(rows(baseline/'real'/run['strategy']/'expert-compute.csv'))
        assert j(d/'compute-model.json')==j(baseline/'real'/run['strategy']/'compute-model.json')
    assert len({x['summary']['combine_fnv1a64'] for x in ledger['runs']})==1
    out.mkdir(parents=True, exist_ok=False)
    def cp(source, name):
        target=out/name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source,target)
    def csvout(name, records):
        assert records
        with (out/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
    performance, compute, resources, communication = [], [], [], []
    correctness, multicast_aggregate, fanout_aggregate = [], [], []
    accepted_perf={x['strategy']:x for x in rows(baseline/'performance.csv') if x['model']=='roofline'}
    for rate, root, origin in [(100,baseline/'real','accepted '+COMMIT),(3136,real,'current measured run')]:
        for mode in MODES:
            d=root/mode; summary=j(d/'online-summary.json')
            m=dict(strategy=mode,**metrics(summary,d,rate,origin))
            if rate==100:
                for key in ['planner_ns','reroute_ns','weight_ns','dispatch_span_ns','compute_span_ns','compute_max_node_ns','combine_span_ns','layer_ns']:
                    assert m[key]==float(accepted_perf[mode][key]), 'Accepted CSV/summary mismatch: '+key
            performance.append(m)
            compute.append(dict(link_gbps=rate,strategy=mode,**aggregate(d)))
            packets=rows(d/'packet-counts.csv')
            source=[x for x in packets if int(x['node'])<64 and x['kind'] in ['weight_write','multicast_v2']]
            payload=sum(int(x['payload_bytes']) for x in rows(d/'multicast-stats.csv')) if mode=='multicast-v2' else summary['remote_bytes'][2]
            wire=sum(int(x['wire_bytes']) for x in source)
            communication.append(dict(link_gbps=rate,strategy=mode,all_host_weight_payload_bytes=payload,
                all_host_weight_wire_bytes=wire,weight_header_bytes=wire-payload,
                switch_down_weight_wire_bytes=sum(int(x['wire_bytes']) for x in packets if int(x['node'])==64 and x['kind']=='weight_write'),
                all_network_wire_bytes=sum(summary['byte_tx_per_node'])))
            if rate==100:
                transport=j(d/'transport-state-summary.json')
            else:
                states=rows(d/'pair-state.csv')
                transport=dict(status='PASS',transport_directions=len(states),
                    all_psn_windows_drained=all(x['send_una']==x['send_nxt'] for x in states),
                    all_ta_windows_drained=all(x['ta_una']==x['ta_nxt'] for x in states),
                    **{key:sum(int(x[col]) for x in states) for key,col in [('unacked','unacked'),('descriptors','descriptors'),('timers','timer'),('active_wqes','active_wqes')]},
                    note='Endpoint/pair identifiers and individual sequence values intentionally omitted; detailed source remains private.')
            assert transport['all_psn_windows_drained'] and transport['all_ta_windows_drained']
            assert not any(transport[k] for k in ['unacked','descriptors','timers','active_wqes'])
            net=rows(d/'network-resources.csv')
            endpoints={(int(x['node']),int(x['port'])):x for x in net}
            assert len(net)==128 and set(endpoints)=={(i,0) for i in range(64)}|{(64,i) for i in range(64)}
            for (node,port),x in endpoints.items():
                y=endpoints[(64,node) if node!=64 else (port,0)]
                assert int(x['consumed'])==int(y['returned'])==int(x['restored'])+int(y['pending'])
                assert int(x['peak_ingress_bytes'])<=1048576 and int(x['peak_egress_bytes'])<=524288
            totals={key:sum(int(x[key]) for x in net) for key in ['consumed','returned','restored','pending','blocked']}
            assert totals['consumed']==totals['returned']==totals['restored']+totals['pending']
            ports=defaultdict(int);feedback=defaultdict(int)
            for packet in packets:
                if int(packet['node'])==64:
                    ports[packet['port']]+=int(packet['packets'])
                    if packet['kind'] in ['transport_ack','transaction_response']:
                        feedback[packet['port']]+=int(packet['packets'])
            correctness.append(dict(link_gbps=rate,strategy=mode,status='PASS',
                completed_tokens=summary['completed_tokens'],assignments=summary['assignments'],
                remote_wqes=summary['remote_WQEs'],ta_count=summary['TA_count'],sender_completions=summary['sender_completions'],
                **{k:v for k,v in transport.items() if k not in ['status','note']},
                **{'total_credit_'+k:v for k,v in totals.items()},credit_conservation_pass=True,all_private_per_port_credit_checks_pass=True,all_private_transport_window_checks_pass=True,
                max_port_voq_bytes=max(int(x['peak_voq_out_bytes']) for x in net),
                max_port_ingress_bytes=max(int(x['peak_ingress_bytes']) for x in net),
                max_port_egress_bytes=max(int(x['peak_egress_bytes']) for x in net),
                max_switch_port_packets=max(ports.values()),max_switch_port_feedback_packets=max(feedback.values())))
            if mode=='multicast-v2':
                stats=rows(d/'multicast-stats.csv');life=j(d/'multicast-lifecycle.json')
                last=max(stats,key=lambda x:int(x['first_send_done_ps']))
                multicast_aggregate.append(dict(link_gbps=rate,status=life['status'],groups=len(stats),
                    **{k:sum(int(x[k]) for x in stats) for k in ['envelopes','native_singleton_packets','payload_bytes','wire_bytes','first_send_grants']},
                    **{k:life[k] for k in ['branches','native_retry_packets','injected_losses','pending_associations','invalidated_grants']},
                    max_association_peak=max(int(x['association_peak']) for x in stats),
                    min_group_association_limit=min(int(x['association_limit']) for x in stats),
                    earliest_group_admitted_ps=min(int(x['admitted_ps']) for x in stats),
                    latest_group_admitted_ps=max(int(x['admitted_ps']) for x in stats),
                    latest_first_send_done_ps=int(last['first_send_done_ps']),latest_first_send_fanout=int(last['fanout']),
                    final_weight_ready_ps=summary['timeline']['weights_end'],
                    final_ready_after_latest_first_send_ns=(summary['timeline']['weights_end']-int(last['first_send_done_ps']))/1000))
                for fanout in sorted({int(x['fanout']) for x in stats}):
                    subset=[x for x in stats if int(x['fanout'])==fanout]
                    cadence=[(int(x['first_send_done_ps'])-int(x['admitted_ps']))/1000/int(x['first_send_grants']) for x in subset]
                    fanout_aggregate.append(dict(link_gbps=rate,fanout=fanout,groups=len(subset),
                        min_first_send_ns_per_grant=min(cadence),max_first_send_ns_per_grant=max(cadence),
                        total_first_send_grants=sum(int(x['first_send_grants']) for x in subset)))
    for x in performance:
        peers=[z for z in performance if z['link_gbps']==x['link_gbps']]
        x['speedup_vs_nobal']=next(z for z in peers if z['strategy']=='no-balancing')['layer_ns']/x['layer_ns']
        x['weight_layer_fraction']=x['weight_ns']/x['layer_ns']
    for mode in MODES:
        a0,a1=[x for x in compute if x['strategy']==mode]
        assert {k:v for k,v in a0.items() if k!='link_gbps'}=={k:v for k,v in a1.items() if k!='link_gbps'}
    assert {x['tokens'] for x in compute}=={2048*8}
    assert {x['flops'] for x in compute}=={6*2048*8*4096*1536}
    assert len({x['activation_hbm_bytes'] for x in compute})==1
    comparisons=[]
    for rate in [100,3136]:
        pp={x['strategy']:x for x in performance if x['link_gbps']==rate}; mc=pp['multicast-v2']
        for mode in ['direct','chunk-streaming']:
            other=pp[mode]
            comparisons.append(dict(link_gbps=rate,reference_strategy=mode,multicast_weight_speedup=other['weight_ns']/mc['weight_ns'],
                multicast_layer_speedup=other['layer_ns']/mc['layer_ns'],weight_saved_ns=other['weight_ns']-mc['weight_ns'],
                layer_saved_ns=other['layer_ns']-mc['layer_ns'],post_gate_difference_ns=other['post_gate_ns']-mc['post_gate_ns']))
    for run in ledger['runs']:
        hc=host(run['simulator_host']); start=dt.datetime.fromisoformat(hc['start']); end=dt.datetime.fromisoformat(hc['end_utc'])
        overlaps=[]
        for other in ledger['runs']:
            if other is run: continue
            oh=host(other['simulator_host']); seconds=(min(end,dt.datetime.fromisoformat(oh['end_utc']))-max(start,dt.datetime.fromisoformat(oh['start']))).total_seconds()
            if seconds>0: overlaps.append(other['strategy']+':'+str(round(seconds,3))+'s')
        resources.append(dict(strategy=run['strategy'],start_utc=hc['start'],end_utc=hc['end_utc'],
            wall_seconds=hc['wall_seconds'],cpu_seconds=hc['user_cpu_seconds']+hc['system_cpu_seconds'],
            peak_rss_kib=hc['peak_rss_kib'],sampled_peak_tree_rss_bytes=hc['sampled_peak_tree_rss_bytes'],
            concurrent_overlap=';'.join(overlaps),guard=hc['guard']))
    bandwidth_effect=[]
    for mode in MODES:
        low=next(x for x in performance if x['link_gbps']==100 and x['strategy']==mode)
        high=next(x for x in performance if x['link_gbps']==3136 and x['strategy']==mode)
        bandwidth_effect.append(dict(strategy=mode,baseline_link_gbps=100,new_link_gbps=3136,
            baseline_weight_ns=low['weight_ns'],new_weight_ns=high['weight_ns'],
            weight_reduction_ns=low['weight_ns']-high['weight_ns'],
            weight_speedup=low['weight_ns']/high['weight_ns'] if high['weight_ns'] else None,
            weight_reduction_fraction=1-high['weight_ns']/low['weight_ns'] if low['weight_ns'] else None,
            baseline_layer_ns=low['layer_ns'],new_layer_ns=high['layer_ns'],
            layer_reduction_ns=low['layer_ns']-high['layer_ns'],
            layer_speedup=low['layer_ns']/high['layer_ns'],
            layer_reduction_fraction=1-high['layer_ns']/low['layer_ns']))
    csvout('bandwidth-effect.csv',bandwidth_effect)
    for name,rr in [('performance.csv',performance),('comparison.csv',comparisons),('compute-aggregate.csv',compute),('communication.csv',communication),('resources.csv',resources)]: csvout(name,rr)
    csvout('correctness-aggregate.csv',correctness)
    csvout('multicast-aggregate.csv',multicast_aggregate)
    csvout('multicast-fanout.csv',fanout_aggregate)
    cp(real/'baseline-reuse.json','baseline-reuse.json')
    dump(out/'source-provenance.json',{k:provenance[k] for k in ['status','accepted_commit','project_tracked_diff_empty','native_candidate_hashes_verified','private_source_identity_sha256','private_source_identity_entries']})
    cp(private/'model-unit/status.json','model-unit/status.json')
    assert j(real/'parallel-resource-record.json')['status']=='PASS'
    samples=j(real/'parallel-resource-samples.json'); assert samples
    dump(out/'host-pressure-summary.json',dict(samples=len(samples),min_host_available_bytes=min(x[1] for x in samples),
        max_cpu_percent=max(x[2] for x in samples),max_load1=max(x[3] for x in samples),
        note='System-wide pressure includes unrelated activity. Concurrent host wall/CPU is not a strict strategy benchmark.'))
    source_metadata=dict(source_identity_entries=len(ledger['source_identity']),
        source_identity_sha256=proof['source_identity_sha256'],
        accepted_native_manifest_reference='experiments/ultraep-multicast-integration/candidate-native-source-sha256.json',
        accepted_native_manifest_sha256=sha(H.parent/'ultraep-multicast-integration/candidate-native-source-sha256.json'))
    public_stage_a={k:sa[k] for k in ['status','link_gbps','strategies','small_cases_pass','native_rate_probe_pass','fault_smoke_pass','small_case_runs','native_fault_smoke_runs','reference_100_comparisons','reference_100_status','reference_100_comparison_kind']}
    public_stage_a.update(source_metadata)
    dump(out/'stage-a/status.json',public_stage_a)
    cp(private/'stage-a/native-rate-probe/console.txt','stage-a/native-rate-probe.json')
    small=j(private/'stage-a/results.json'); assert len(small)==32
    csvout('stage-a.csv',[dict(case=x['case'],strategy=x['strategy'],link_gbps=x['link_gbps'],status=x['status'],
        layer_latency_ps=x['summary']['layer_latency_ps'],output_hash=x['summary']['combine_fnv1a64']) for x in small])
    fault_rows=[]
    for fault in ['data-once','ack-once','invalidate-grant']:
        d=private/'stage-a/network/3136'/fault
        life=j(d/'multicast-lifecycle.json');trace=rows(d/'weight-packets.csv')
        validation=j(d/'validation.json');compute_validation=j(d/'compute-validation.json')
        assert life['status']==validation['status']==compute_validation['status']=='PASS'
        fault_rows.append(dict(case=fault,status='PASS',packet_records=len(trace),
            first_packet_ps=min(int(x['time_ps']) for x in trace),last_packet_ps=max(int(x['time_ps']) for x in trace),
            **{key:life[key] for key in ['envelopes','branches','native_retry_packets','injected_losses','pending_associations','invalidated_grants']}))
    csvout('synthetic-fault-summary.csv',fault_rows)
    # Explicit resource receipt allowlist: never copy command lines, logs or raw traces.
    receipts=[]
    for path in sorted(private.glob('native-*/resource.json'))+sorted((private/'build').glob('*-build/resource.json')):
        item=dict(stage=str(path.parent.relative_to(private)),**host(j(path)));receipts.append(item)
    dump(out/'build-receipts.json',receipts)
    dump(out/'summary.json',dict(status='PASS',baseline_commit=COMMIT,baseline_reuse=proof['reuse_basis'],
        current_real_runs=4,small_case_runs=32,native_fault_smoke_runs=3,source_unchanged=True,
        **source_metadata,binary_identity_entries=len(ledger['binary_identity']),
        binary_identity_sha256=hashlib.sha256(json.dumps(ledger['binary_identity'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
        input_identity=ledger['input_identity'],
        compute_work_exactly_unchanged=True,build_receipts=receipts,
        scope='One L37 / 2048-token / EP64 real workload; logical aggregate 3136 Gbps versus reused accepted 100 Gbps.'))
    print(json.dumps(comparisons,indent=2))

if __name__=='__main__':
    main()
