"""Independent finite hold lifecycle checks, not a claim of complete causal coverage."""
from collections import Counter, defaultdict
from support import *

def check_candidate(directory,enabled):
    directory=Path(directory)
    if not enabled:
        require(not (directory/'candidate-summary.json').exists() and not (directory/'candidate-holds.csv').exists(),'Disabled observer changed v1 surface')
        return dict(status='PASS',enabled=False)
    summary=read(directory/'candidate-summary.json');rows=phase_b.csv_rows(directory,'candidate-holds.csv')
    require(summary['status']=='PASS' and summary['enabled'] is True and summary['hold_ps']==5000,'Candidate policy/bound')
    require(summary['priority_data_eligibility']=='unknown-speculative-no-CC-probe','Missing UNKNOWN eligibility declaration')
    require(summary['scope']=='stage1-stage2-only' and summary['identical_realized_grants_claimed'] is False,'Candidate scope')
    require(summary['active_holds']==0 and summary['armed']==summary['released'],'Candidate leaked holds')
    require(summary['evidence_cap']==32768 and summary['hold_ledger_complete'] is True,'INCOMPLETE hold ledger')
    require(summary['pull_snapshot_limit_per_role_reason']==32,'Pull snapshot budget')
    require(summary['pull_decisions']==summary['pull_decisions_sampled']+summary['pull_decisions_omitted'],'Pull sample accounting')
    require(len(rows)==summary['evidence_rows'] and len(rows)<=32768,'INCOMPLETE candidate evidence')
    config=read(directory/'config.json');groups={g['group']:g for g in config['hybrid_groups']}
    snapshots=defaultdict(list)
    for r in rows:
        key=tuple(r[k] for k in ['time_ps','event','source','target','tp','hold_generation','selected_task','selected_ssn','selected_offset','selected_length'])
        snapshots[key].append(r)
        require(int(r['native_limited'])==-1,'Observer must not claim native CC certainty')
    armed={};released={};head_ids=set();max_duration=0;reasons=Counter();priority_arms=0;pulls=0;pull_samples=Counter();consumed={};max_consume_delay=0
    for rs in snapshots.values():
        r=rs[0];event=r['event'];time=int(r['time_ps']);g=int(r['group'])
        key=tuple(r[k] for k in ['source','target','tp','hold_generation'])
        identity=tuple(r[k] for k in ['source','target','tp','selected_task','selected_ssn','selected_offset','selected_length'])
        if event in ['arm','release','consumed']:
            require(g in groups,'Unknown held group');group=groups[g]
            require(group['graph_role'] in ['stage1','stage2'] and len(group['members'])>1,'Out-of-scope hold')
            require({(int(x['member_rank']),int(x['expected_task'])) for x in rs}=={(m['target'],m['task']) for m in group['members']},'Fixed member snapshot mismatch')
            require(len(rs)==len(group['members']),'Repeated or missing member snapshot')
            require(int(r['deadline_ps'])==int(r['armed_ps'])+5000,'Extended hold deadline')
        if event=='arm':
            require(key not in armed and identity not in head_ids,'Head rearmed')
            require(time==int(r['armed_ps']) and int(r['hold_active'])==1 and int(r['hold_spent'])==0,'Bad arm state')
            require(all(int(x['submitted'])==1 and int(x['consumed_bytes'])==int(r['selected_offset']) for x in rs),'Unsubmitted or unaligned hold')
            require(r['reason'] in ['submitted_aligned_absent_data_eligibility_unknown','priority_with_unknown_data_eligibility'],'Undeclared hold reason')
            priority_arms+=r['reason']=='priority_with_unknown_data_eligibility'
            armed[key]=(identity,time,int(r['deadline_ps']));head_ids.add(identity)
        elif event=='release':
            require(key in armed and key not in released,'Unmatched or duplicate release')
            ident,start,deadline=armed[key]
            require(identity==ident and start<=time<=deadline and int(r['released_ps'])==time,'Release identity/time mismatch')
            require(int(r['hold_active'])==0 and int(r['hold_spent'])==1,'Released head not spent')
            if r['reason']=='deadline':require(time==deadline,'Early/late expiry')
            max_duration=max(max_duration,time-start);released[key]=time;reasons[r['reason']]+=1
        elif event=='consumed':
            require(key in released and key not in consumed,'Missing release or duplicate held consumption')
            require(identity==armed[key][0] and time>=released[key],'Held consumption identity/order')
            max_consume_delay=max(max_consume_delay,time-released[key]);consumed[key]=time
        elif event=='pull':
            pulls+=1
            role=groups[g]['graph_role'] if g else 'native'
            pull_samples[role,r['reason']]+=1
            require(pull_samples[role,r['reason']]<=32,'Exceeded pull sample budget')
            # Priority may legitimately pull while its original hold remains active.
            if int(r['hold_active']):
                require(time<int(r['deadline_ps']),'Expired APP hold observed at pull')
                selected=[x for x in rs if int(x['member_rank'])==int(r['target'])]
                require(selected and any(int(x['cnp']) or int(x['ack']) or int(x['gbn']) for x in selected),'Nonpriority original pulled through hold')
        else:raise ValueError('Unknown candidate event '+event)
    require(pulls==summary['pull_decisions_sampled'],'Missing sampled pull snapshots')
    require(set(consumed)==set(armed) and len(consumed)==summary['held_heads_consumed'],'Missing actual held-head consumption')
    require(max_consume_delay==summary['max_release_to_consume_ps'],'Release-to-consume summary mismatch')
    require(len(armed)==summary['armed'] and set(armed)==set(released),'Missing arm/release evidence')
    require(max_duration==summary['max_app_hold_ps']<=5000,'Hold duration summary mismatch')
    require(reasons['deadline']==summary['expired'],'Expiry summary mismatch')
    require(summary['expired']+summary['early_releases']+summary['head_change_releases']==summary['released'],'Release counter partition')
    return dict(status='PASS',armed=len(armed),priority_unknown_arms=priority_arms,max_app_hold_ps=max_duration,release_reasons=dict(reasons),pull_snapshots=pulls,
                causal_admission='INCOMPLETE_UNLESS_SEPARATELY_DEMONSTRATED',
                unproven_by_this_checker=['expiry with no other wake','priority service timing and underlying CC outcome','stale callback inertness','named reason transition attribution','same-TP original order beyond frozen native checks'])
