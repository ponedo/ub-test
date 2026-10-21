"""Export boundary-corrected outcomes after formal PASS and prefix-union verification."""
import argparse
import csv
import json
from pathlib import Path


def rows(path):
    with path.open(newline='') as stream:
        return [{key: int(value) if value.isdecimal() else value for key, value in row.items()}
                for row in csv.DictReader(stream)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    root = args.root
    if json.loads((root / 'ledger.json').read_text())['status'] != 'PASS':
        raise ValueError('Both formal cases must PASS')
    prefixes = json.loads((root / 'analysis/prefix-callback-union.json').read_text())
    output, proof = [], []
    for prefix in prefixes:
        mode, node, port = prefix['strategy'], prefix['node'], prefix['port']
        end = prefix['prefix_end_ps']
        case = root / mode
        tail = rows(case / 'diagnostic-weight-tail.csv')
        cohort = rows(case / 'diagnostic-weight-phase-cohorts.csv')
        if min(row['time_ps'] for row in tail) >= end:
            raise ValueError('Cutoff not completely retained')
        port_tail = [row for row in tail if row['node'] == node and row['port'] == port]
        after = {4: [], 23: [], 24: []}
        start = None
        for row in port_tail:
            if row['kind'] == 3:
                start = row
            elif row['kind'] in after and row['time_ps'] > end:
                if start is None:
                    raise ValueError('Outcome start missing')
                elapsed = row['time_ps'] - start['time_ps']
                if elapsed != 5000 or elapsed != start['aux0']:
                    raise ValueError('Unexpected actual callback duration')
                after[row['kind']].append(elapsed)
                start = None
        count_sum = service_sum = 0
        for metric, kind, name in [(10, 4, 'committed'), (9, 24, 'no_ingress'), (8, 23, 'rejected')]:
            selected = [row for row in cohort if row['node'] == node and row['port'] == port and row['metric'] == metric]
            total = sum(row['count'] for row in selected)
            count = total - len(after[kind])
            service = sum(row['sum'] for row in selected) - sum(after[kind])
            if service != count * 5000:
                raise ValueError('Prefix outcome service mismatch')
            output.append(dict(strategy=mode, node=node, port=port, prefix_end_ps=end, outcome=name,
                phase_end_cohort_count=total, retained_outcomes_strictly_after_cutoff=len(after[kind]),
                prefix_count=count, prefix_service_ps=service,
                semantics='End cohort minus complete retained outcomes strictly after last dequeue; no boundary-crossing callback'))
            count_sum += count
            service_sum += service
        if count_sum != prefix['prefix_callbacks'] or service_sum != prefix['prefix_allocation_service_ps']:
            raise ValueError('Prefix outcomes do not equal independently verified starts')
        proof.append(dict(strategy=mode, node=node, prefix_count=count_sum, prefix_service_ps=service_sum,
                          independently_verified_start_count=prefix['prefix_callbacks']))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)
    (root / 'analysis/prefix-outcome-reproduction-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
