"""Create narrowly scoped, UNPUBLISHED review candidates after v3 analysis PASS."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

MODES = ['chunk-streaming', 'multicast-v2']
PARTS = ['tx_busy_union_ps', 'allocator_pending_excluding_tx_ps', 'uncovered_idle_ps']
MAX32, MAX64 = 4294967295, 18446744073709551615


def load(path):
    return json.loads(path.read_text())


def rows(path):
    with path.open(newline='') as stream:
        return [{key: int(value) if value.isdecimal() else value for key, value in row.items()}
                for row in csv.DictReader(stream)]


def write_csv(path, data):
    if not data:
        raise ValueError('Empty candidate: ' + path.name)
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


def find_cycle(root):
    """Find a bounded v3 512-TA reconstruction, never infer from a held label."""
    tail = rows(root / 'multicast-v2/diagnostic-weight-tail.csv')
    local = [(i, row) for i, row in enumerate(tail) if row['node'] == 3]
    cutoff = load(root / 'analysis/analysis.json')['cases']['multicast-v2']['critical_transfers'][0]['last_native_send_ps']
    starts = [(i, row) for i, row in local if row['kind'] == 3 and row['port'] == 0 and row['time_ps'] < cutoff]
    tps = [198, 206, 245, 252]
    for left, right in reversed(list(zip(starts, starts[1:]))):
        begin = left[1]['time_ps'] + left[1]['aux0']
        end = right[1]['time_ps']
        if end <= begin:
            continue
        empty, response = {}, {}
        for tp in tps:
            empty_rows = [(i, row) for i, row in local if row['tp'] == tp and row['kind'] == 22 and row['time_ps'] <= begin]
            response_rows = [(i, row) for i, row in local if row['tp'] == tp and row['kind'] == 18 and row['time_ps'] <= begin]
            if empty_rows and response_rows:
                empty[tp], response[tp] = empty_rows[-1], response_rows[-1]
        if len(empty) != 4 or len(response) != 4:
            continue
        n = empty[198][1]['aux3']
        if not all(e[1]['aux0'] == 1 and e[1]['aux1'] == e[1]['aux3'] == n
                   and response[tp][1]['aux2'] == n - 512
                   and response[tp][1]['aux3'] == n - 513
                   and e[0] >= response[tp][0] for tp, e in empty.items()):
            continue
        # A later admission would invalidate an old empty snapshot.
        if any(row['kind'] == 11 and row['uid'] == MAX64 and row['tp'] in tps
               and empty[row['tp']][0] < i and row['time_ps'] < end for i, row in local):
            continue
        before = [(i, row) for i, row in local if row['kind'] == 17 and row['tp'] == 198
                  and row['time_ps'] == end and row['aux2'] == n - 512]
        after = [(i, row) for i, row in local if row['kind'] == 18 and row['tp'] == 198
                 and row['time_ps'] == end and row['aux2'] == n - 511]
        if not before or not after:
            continue
        enqueue = [(i, row) for i, row in local if row['kind'] == 11 and row['tp'] == 198
                   and row['uid'] == MAX64 and row['time_ps'] == end and i > after[0][0]]
        if not enqueue:
            continue
        advanced = [(i, row) for i, row in local if row['kind'] == 22 and row['tp'] == 198
                    and row['time_ps'] == end and row['aux3'] == n + 1 and i > enqueue[0][0]]
        if not advanced:
            continue
        selected = [(i, row, 'previous successful TA-response receive') for i, row in response.values()]
        selected += [(i, row, 'native TP observed empty') for i, row in empty.values()]
        selected += [(before[0][0], before[0][1], 'next TA response before processing'),
                     (after[0][0], after[0][1], 'next TA response after processing'),
                     (enqueue[0][0], enqueue[0][1], 'new WQE-segment admission after TA response'),
                     (advanced[0][0], advanced[0][1], 'admitted packet count advances'),
                     (left[0], left[1], 'actual allocation starts before gap'),
                     (right[0], right[1], 'actual allocation starts after gap')]
        output = []
        for i, row, label in sorted(selected):
            entry = dict(observer='v3', time_ps=row['time_ps'], event=label,
                         member={198: 5, 206: 13, 245: 52, 252: 59}.get(row['tp'], ''),
                         tp_snd_next='', tp_snd_una='', reverse_tp_recv_next='',
                         tp_admitted_packet_count='', observed_empty='', allocation_duration_ps='')
            if row['kind'] == 22:
                entry.update(tp_snd_next=row['aux1'], tp_snd_una=row['aux2'],
                             tp_admitted_packet_count=row['aux3'], observed_empty=row['aux0'])
            elif row['kind'] in (11, 17, 18):
                entry.update(tp_snd_next=row['aux0'], tp_snd_una=row['aux1'])
                if row['kind'] in (17, 18):
                    entry['reverse_tp_recv_next'] = row['aux2']
            else:
                entry['allocation_duration_ps'] = row['aux0']
            output.append(entry)
        return output, dict(observer='v3', allocation_gap_start_ps=begin, allocation_gap_end_ps=end,
                            reconstructed_outstanding_tas=512,
                            interpretation='Audited reconstruction, not directly sampled Jetty SSNs; bounded cycle only')
    raise ValueError('No complete audited v3 Jetty cycle retained; do not infer missing evidence')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--out',type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if load(root / 'ledger.json')['status'] != 'PASS':
        raise ValueError('Both formal cases must PASS')
    analysis = load(root / 'analysis/analysis.json')
    resources = load(root / 'analysis/same-resource-comparison.json')
    for mode in MODES:
        if analysis['cases'][mode]['voq_interval_quality']['observer'] != 'ordered_FIFO':
            raise ValueError('Require validated v3 FIFO analysis')
    out = args.out.resolve() if args.out else root.parent / 'public-candidates'
    out.mkdir(exist_ok=True)
    chunk = analysis['cases']['chunk-streaming']['critical_transfers'][0]
    multicast = analysis['cases']['multicast-v2']['critical_transfers'][0]
    accounting = []
    for key in PARTS + ['post_dequeue_to_ready_ps']:
        a = chunk['prefix_accounting_candidates'][0][key] if key in PARTS else chunk[key]
        b = multicast['prefix_accounting_candidates'][0][key] if key in PARTS else multicast[key]
        accounting.append(dict(component=key, chunk_ps=a, multicast_ps=b, delta_ps=b-a,
            evidence='exact disjoint resource accounting', causal_limit='Uncovered idle cause not fully classified; columns are not intervention effects'))
    write_csv(out / 'gap-accounting.csv', accounting)
    write_csv(out / 'prefix-callback-union.csv', load(root / 'analysis/prefix-callback-union.json'))
    timeline = []
    for mode in MODES:
        for task in analysis['cases'][mode]['critical_transfers']:
            timeline.append(dict(strategy=mode, **{key: task[key] for key in ['task', 'expert', 'source', 'target', 'physical', 'bytes', 'submit_ps', 'first_native_send_ps', 'last_native_send_ps', 'last_received_ps', 'receiver_ready_ps', 'sender_complete_ps']},
                                 dependencies='none', evidence='actual terminal full-expert receiver dependency'))
    write_csv(out / 'weight-timeline.csv', timeline)
    observations = [dict(**row, semantics='Mutually exclusive first-failing observations; held spans are NOT continuous waits')
                    for row in analysis['cases']['multicast-v2']['critical_group_allready_observations']]
    write_csv(out / 'allready-group8.csv', observations)
    cohorts, partitions, outcomes = [], [], []
    for resource in resources['resources']:
        node, port = resource['node'], resource['port']
        for mode, result in resource['strategies'].items():
            for row in result['weight_phase_cohorts']:
                if row['metric'] in (0, 3, 4, 5, 6, 7) and row['class'] in (0, 1):
                    cohorts.append(dict(strategy=mode, **row, metric_name={0:'VOQ residence ps',3:'egress wait ps',4:'serialization ps',5:'wire bytes',6:'received bytes',7:'explicit TX delay ps'}[row['metric']], mean=row['sum']/row['count'] if row['count'] else 0,
                                        interpretation='Selected same physical port; overlapping event cohort, not wall time'))
                if row['metric'] in (2, 8, 9, 10):
                    outcomes.append(dict(strategy=mode, **row,
                        outcome={2:'scheduled start',8:'revalidation rejected',9:'no ingress',10:'successful commit'}[row['metric']],
                        interpretation='Start and end cohorts differ at boundaries; do not add to disjoint occupancy'))
            for scope, key in [('weight_phase', 'weight_phase_partition'), ('source_own_last_dequeue', 'source_own_last_dequeue_partition')]:
                row = result[key]
                if row:
                    partitions.append(dict(strategy=mode, node=node, port=port, scope=scope,
                        start_ps=row['phase_start_ps'], end_ps=row.get('phase_end_ps',row.get('last_weight_native_send_ps')),
                        **{key:row[key] for key in PARTS}, total_ps=row['total_ps'],
                        interpretation='Same resource; phase end differs by strategy and can include post-source-completion idle'))
    write_csv(out / 'same-resource-selected-aggregates.csv', cohorts)
    write_csv(out / 'same-resource-partitions.csv', partitions)
    write_csv(out / 'allocation-outcomes.csv', outcomes)
    selected = []
    for mode in MODES:
        mapping = {}
        def packet_label(uid):
            if uid in (0, MAX64):return ''
            return mapping.setdefault(uid, 'packet_' + str(len(mapping)+1))
        for row in rows(root / ('analysis/' + mode + '-selected-final-packet-timeline.csv')):
            clean = {key: row[key] for key in ['time_ps','kind_name','node','port','task','group','sequence','aux0','aux1','tp','aux2','aux3','reason']}
            clean = {key: '' if value == MAX32 else value for key,value in clean.items()}
            selected.append(dict(strategy=mode, **clean, packet_ref=packet_label(row['uid']),parent_packet_ref=packet_label(row['parent_uid'])))
    intervals = []
    for mode in MODES:
        tail = rows(root / mode / 'diagnostic-weight-tail.csv')
        for task in analysis['cases'][mode]['critical_transfers']:
            for measured in task['packet_chain']['measured_packet_intervals_not_additive']:
                if measured['type'] != 'allocation_selection':
                    continue
                matching = [(i, row) for i, row in enumerate(tail)
                            if row['node'] == measured['node'] and row['port'] == measured['port']
                            and row['kind'] == 4 and row['time_ps'] == measured['end_ps']]
                if len(matching) != 1:
                    raise ValueError('Final commit not uniquely retained')
                index, commit = matching[0]
                starts = [row for row in tail[:index] if row['kind'] == 3
                          and row['node'] == measured['node'] and row['port'] == measured['port']]
                if not starts:
                    raise ValueError('Final callback start absent')
                start = starts[-1]
                duration = commit['time_ps'] - start['time_ps']
                if duration != start['aux0']:
                    raise ValueError('Final callback duration mismatch')
                intervals.append(dict(strategy=mode, task=task['task'], node=measured['node'],
                    port=measured['port'], grant_start_ps=start['time_ps'],
                    successful_commit_ps=commit['time_ps'], elapsed_ps=duration,
                    evidence='Actual physical-port callback start and successful outcome',
                    limitation='Not necessarily queue-selection start; overlaps VOQ residence'))
    write_csv(out / 'final-allocation-intervals.csv', intervals)
    cycle, cycle_provenance = find_cycle(root)
    if len(cycle)>30 or len(selected)+len(cycle)>200:
        raise ValueError('Selected event budget exceeded')
    write_csv(out / 'selected-critical-events.csv', selected)
    write_csv(out / 'selected-jetty-512-cycle.csv', cycle)
    manifest = dict(review_status='UNPUBLISHED_PUBLIC_CANDIDATES_REQUIRE_ROOT_REVIEW',
                    selected_event_rows=len(selected)+len(cycle), cycle_provenance=cycle_provenance,
                    scope='Aggregate plus narrowly selected terminal/Jetty cycle events only; no raw pointer identities or full node/expert dumps',
                    files={path.name:dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),rows=len(rows(path))) for path in sorted(out.glob('*.csv'))})
    (out/'candidate-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    (out / 'README.md').write_text("""# Unpublished, selected evidence candidates

These files require root review before publication. They contain aggregates for
six selected physical resources and bounded event excerpts, not full per-node,
per-expert or raw-packet histories. Queue pointer identities are omitted. Packet
references are local ordinals within each strategy, not unique fragment IDs.

All times and durations use picoseconds unless a column says otherwise. Classes
0, 1 and 2 mean stage-2 weight, ACK/transaction response and other traffic.
Native cohort metric names are supplied explicitly. A full residence whose end
falls within the weight phase is not clipped phase occupancy. Service-start and
outcome-end cohorts have different boundary membership. Their sums overlap and
must not be added as wall time.

The gap-accounting and prefix-callback-union tables are exact interval/count
identities, not estimates of the speedup from an unperformed intervention.
AllReady rows contain mutually exclusive first-failing observations; held spans
are not continuous waits. The Jetty cycle is an audited reconstruction from TP
counter events, not a direct Jetty SSN sample, and does not classify total idle.
The candidate manifest explicitly identifies its observer version.

Selected critical events retain native auxiliary fields for source-level audit.
Their meaning is event-specific: TX-start aux0 is serialization plus explicit
delay duration, aux1 is busy duration, and aux2 is explicit delay; grant-start
aux0 is requested allocation duration; allocation-select aux0 is input port
and aux1 priority; VOQ aux0 is post-operation depth. Do not interpret the
auxiliary columns as a common quantity across event kinds. Packet occurrences
were traced backward from the final receive, not grouped solely by reused UID.
""")
    print(json.dumps(manifest,indent=2))


if __name__ == '__main__':
    main()
