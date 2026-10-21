"""Verify callback counts independently of the measured TX/allocation union."""
import csv
import json
from pathlib import Path
import sys


def rows(path):
    with path.open(newline='') as stream:
        return [{key: int(value) if value.isdecimal() else value
                 for key, value in row.items()} for row in csv.DictReader(stream)]


def main(root):
    if json.loads((root / 'ledger.json').read_text())['status'] != 'PASS':
        raise ValueError('Both formal cases must PASS before final collection')
    results = []
    for mode, nodes in [('chunk-streaming', [36, 50]), ('multicast-v2', [3])]:
        case = root / mode
        tail = rows(case / 'diagnostic-weight-tail.csv')
        cohorts = rows(case / 'diagnostic-weight-phase-cohorts.csv')
        prefixes = rows(case / 'diagnostic-source-last-send-partition.csv')
        for node in nodes:
            prefix = next(row for row in prefixes if row['node'] == node and row['port'] == 0)
            end = prefix['last_weight_native_send_ps']
            if min(row['time_ps'] for row in tail) >= end:
                raise ValueError('Tail is incomplete around the last-source-dequeue cutoff')
            starts = [row for row in tail if row['kind'] == 3 and row['node'] == node and row['port'] == 0]
            if any(row['time_ps'] < end < row['time_ps'] + row['aux0'] for row in starts):
                raise ValueError('Allocation crosses the prefix boundary; requires clipping')
            after = [row for row in starts if row['time_ps'] >= end]
            aggregate = [row for row in cohorts if row['metric'] == 2 and row['node'] == node and row['port'] == 0]
            count = sum(row['count'] for row in aggregate) - len(after)
            duration = sum(row['sum'] for row in aggregate) - sum(row['aux0'] for row in after)
            union = prefix['tx_busy_union_ps'] + prefix['allocator_pending_excluding_tx_ps']
            if duration != count * 5000 or duration != union:
                raise ValueError('Observed callback prefix does not match the independently measured union')
            results.append(dict(strategy=mode, node=node, port=0,
                prefix_start_ps=prefix['phase_start_ps'], prefix_end_ps=end,
                phase_start_cohort_callbacks=sum(row['count'] for row in aggregate),
                retained_starts_at_or_after_cutoff=len(after),
                prefix_callbacks=count, prefix_allocation_service_ps=duration,
                measured_tx_allocation_union_ps=union,
                uncovered_idle_ps=prefix['uncovered_idle_ps'],
                evidence='Observed start-cohort count minus complete retained suffix; no cutoff-crossing allocation',
                assumptions='Single pending callback per port; no pre-weight allocation (audited source/workload)',
                causal_limit='Resource union identity, not an intervention-derived callback-removal speedup'))
    output = root / 'analysis/prefix-callback-union.json'
    output.write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
